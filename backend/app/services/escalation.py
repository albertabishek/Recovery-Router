"""
AI-powered escalation engine.
Analyzes attempt history and makes real decisions about next recovery action.
No hardcoded rotation — the AI decides based on what actually happened.
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.config import settings
from app.database import get_supabase
from app.redis_client import get_redis
from app.services.ai_client import ai_call
from postgrest.exceptions import APIError
from app.services.payment_links import generate_payment_link
from app.services.messenger import send_message

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
QUIET_START_HOUR = 21  # 9 PM IST
QUIET_END_HOUR = 9     # 9 AM IST


def _is_quiet_hours(now_utc: datetime | None = None) -> bool:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(IST)
    return now.hour >= QUIET_START_HOUR or now.hour < QUIET_END_HOUR


def _next_permitted_time() -> datetime:
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    if now_ist.hour >= QUIET_START_HOUR:
        next_day = now_ist + timedelta(days=1)
        wake = next_day.replace(hour=QUIET_END_HOUR, minute=0, second=0, microsecond=0)
    else:
        wake = now_ist.replace(hour=QUIET_END_HOUR, minute=0, second=0, microsecond=0)
    return wake.astimezone(timezone.utc)

ESCALATION_PROMPT = """You are the escalation decision agent for a payment recovery system. A customer hasn't completed their payment despite previous recovery attempts.

Your job: analyze what happened in previous attempts and decide the BEST next move. You will be given the event's max_attempts — the system already computed how many attempts this event deserves based on amount, probability, and failure type. Respect that budget.

## Decision framework

1. LOOK at previous attempts AND blocked/failed channels:
   - What channel was used? Did it succeed in delivering?
   - If WhatsApp was sent but customer didn't act → try email with more detail or SMS.
   - If email was sent but not opened → try WhatsApp or SMS for immediacy.
   - If delivery failed (provider error) → SWITCH to a different channel, don't retry the same one.
   - Check "blocked_channels" — these hit a cooldown/rate limit. ALWAYS pick a different channel.
   - Check "failed_channels" — delivery failed on these. Prefer a different channel.
   - If a "backup_plan" is provided, follow it when the primary channel didn't work.

2. CONSIDER the event context:
   - High amount (>5000) + multiple attempts → the customer is hesitating, not forgetting. Address their concern.
   - UPI timeout → high recovery chance, keep trying with different channels.
   - Card expired → customer needs to update their card. Email is best.
   - Insufficient funds → give them more time between attempts.

3. ADJUST tone:
   - After 0-1 attempts: friendly, helpful
   - After 2 attempts: direct, acknowledge it's a follow-up
   - After 3+ attempts: honest, final chance

4. WHEN TO GIVE UP:
   - ONLY give up if attempt_count >= max_attempts (the budget is already computed for you)
   - OR if ALL previous delivery attempts failed (bad contact info — no channel works)
   - Do NOT give up just because probability is low or amount is small — the max_attempts budget already accounts for that
   - NEVER give up on the first escalation (attempt_count == 1). The customer deserves at least one follow-up on a different channel.

## Output format
{
  "action": "send" | "give_up",
  "channel": "whatsapp" | "email" | "sms",
  "tone": "friendly" | "firm" | "urgent" | "final",
  "reasoning": "<2-3 sentences explaining your decision based on what actually happened>"
}"""

ESCALATION_SCHEMA = {
    "action": {"type": "str", "allowed": ["send", "give_up"], "default": "send"},
    "channel": {"type": "str", "allowed": ["whatsapp", "email", "sms"], "default": "email"},
    "tone": {"type": "str", "allowed": ["friendly", "firm", "urgent", "final"], "default": "firm"},
}


def _acquire_event_lock(event_id: int, ttl: int = 300) -> bool:
    r = get_redis()
    return bool(r.set(f"lock:event:{event_id}", "1", nx=True, ex=ttl))


def _release_event_lock(event_id: int):
    r = get_redis()
    r.delete(f"lock:event:{event_id}")


def run_escalation(events: list[dict]) -> list[dict]:
    """Process escalation for a batch of events."""
    if not events:
        return []

    sb = get_supabase()
    results = []

    for event in events:
        if not _acquire_event_lock(event["id"]):
            results.append({"event_id": event["id"], "action": "skipped_locked"})
            continue

        try:
            fresh = sb.table("recovery_events").select(
                "status,attempt_count,max_attempts,escalation_level,delivery_failure_count"
            ).eq("id", event["id"]).limit(1).execute()
            if not fresh.data or fresh.data[0].get("status") != "pending":
                logger.warning(
                    "Event %d: skipped (status=%s after lock)",
                    event["id"], fresh.data[0].get("status") if fresh.data else "NOT_FOUND",
                )
                results.append({"event_id": event["id"], "action": "skipped_not_pending"})
                continue
            event.update(fresh.data[0])

            attempts = _get_attempt_history(sb, event["id"])
            logger.info(
                "Event %d: attempt_count=%d/%d, %d attempts in history",
                event["id"], event.get("attempt_count", 0),
                event.get("max_attempts", 5), len(attempts),
            )

            dfc = (event.get("delivery_failure_count", 0) or 0)
            max_att = event.get("max_attempts") if event.get("max_attempts") is not None else 5
            if dfc > max_att:
                has_any_sent = any(
                    a.get("outcome") == "sent"
                    for a in attempts
                    if a.get("channel_used") not in ("payment_link", "system")
                )
                if not has_any_sent:
                    logger.warning(
                        "Event %d: delivery_failure_count=%d > max_attempts=%d, no successful sends — exhausting",
                        event["id"], dfc, max_att,
                    )
                    _mark_exhausted(
                        sb, event,
                        f"All delivery attempts failed ({dfc} consecutive failures, no message ever delivered)",
                    )
                    results.append({"event_id": event["id"], "action": "exhausted_unreachable"})
                    continue

            decision = _get_escalation_decision(event, attempts)
            logger.info(
                "Event %d: AI decision=%s channel=%s reasoning=%s",
                event["id"], decision.get("action"), decision.get("channel"),
                (decision.get("reasoning") or "")[:120],
            )

            if decision.get("action") == "give_up":
                attempt_count = event.get("attempt_count", 0)
                max_attempts = event.get("max_attempts") if event.get("max_attempts") is not None else 5
                if attempt_count < max_attempts:
                    logger.warning(
                        "Event %d: give_up blocked — attempt_count=%d < max_attempts=%d, forcing send",
                        event["id"], attempt_count, max_attempts,
                    )
                    blocked_chs = {
                        a.get("channel_used") for a in attempts
                        if a.get("channel_used") != "payment_link"
                        and a.get("outcome") in ("blocked", "failed")
                    }
                    last_ch = attempts[-1].get("channel_used") if attempts else None
                    decision = {
                        "action": "send",
                        "channel": _pick_next_channel(last_ch, event, avoid=blocked_chs),
                        "tone": "firm" if attempt_count <= 2 else "urgent",
                        "reasoning": f"Safety override: give_up blocked because {max_attempts - attempt_count} attempts remain.",
                    }
                else:
                    logger.warning(
                        "Event %d: EXHAUSTING via give_up (attempt_count=%d/%d)",
                        event["id"], attempt_count, max_attempts,
                    )
                    _mark_exhausted(sb, event, decision.get("reasoning", ""))
                    results.append({"event_id": event["id"], "action": "exhausted"})
                    continue

            channel = decision.get("channel", "email")

            if _is_quiet_hours():
                wake_at = _next_permitted_time()
                sb.table("recovery_events").update({
                    "next_action_at": wake_at.isoformat(),
                    "current_strategy": "quiet_hours_rescheduled",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", event["id"]).eq("status", "pending").execute()
                logger.info(
                    "Event %d: quiet hours — rescheduled to %s",
                    event["id"], wake_at.isoformat(),
                )
                results.append({"event_id": event["id"], "action": "rescheduled_quiet_hours"})
                continue

            recovery_window_ends = _parse_datetime(event.get("recovery_window_ends"))

            link = generate_payment_link(
                amount=float(event.get("amount", 0)),
                currency=event.get("currency", "INR"),
                customer_name=event.get("customer_name", "Customer"),
                customer_email=event.get("customer_email"),
                customer_phone=event.get("customer_phone"),
                order_id=event.get("order_id"),
                event_type=event.get("event_type", "payment_failure"),
                failure_category=event.get("failure_category", "unknown"),
                event_id=event["id"],
                recovery_window_ends=recovery_window_ends,
            )

            if not link.get("short_url"):
                logger.error("Event %d: payment link creation failed, rescheduling in 15m", event["id"])
                now = datetime.now(timezone.utc)
                sb.table("recovery_events").update({
                    "next_action_at": (now + timedelta(minutes=15)).isoformat(),
                    "updated_at": now.isoformat(),
                }).eq("id", event["id"]).eq("status", "pending").execute()
                results.append({"event_id": event["id"], "action": "link_failed"})
                continue

            try:
                next_number, idem_key = _reserve_attempt(sb, event, channel, decision, link)
            except APIError as e:
                if e.json().get("code") == "23505":
                    logger.info("Escalation already reserved for event %d", event["id"])
                    results.append({"event_id": event["id"], "action": "already_processed"})
                    continue
                raise

            send_result = send_message(
                channel=channel,
                customer_name=event.get("customer_name", "Customer"),
                customer_email=event.get("customer_email"),
                customer_phone=event.get("customer_phone"),
                amount=float(event.get("amount", 0)),
                currency=event.get("currency", "INR"),
                failure_category=event.get("failure_category", "unknown"),
                payment_link_url=link.get("short_url", ""),
                reasoning=decision.get("reasoning", ""),
                attempt_number=event.get("attempt_count", 0),
                personalization_hint=event.get("personalization_hint"),
            )

            _finalize_attempt(sb, idem_key, channel, send_result, link, event)

            if send_result.get("success", False):
                _update_event_state(sb, event, decision)
            else:
                is_hard_failure = send_result.get("error") != "Cooldown active"
                now = datetime.now(timezone.utc)
                fail_update = {
                    "next_action_at": (now + timedelta(minutes=15)).isoformat(),
                    "updated_at": now.isoformat(),
                }
                if is_hard_failure:
                    fail_update["delivery_failure_count"] = (
                        (event.get("delivery_failure_count", 0) or 0) + 1
                    )
                sb.table("recovery_events").update(
                    fail_update
                ).eq("id", event["id"]).eq("status", "pending").execute()

            results.append({
                "event_id": event["id"],
                "action": "sent" if send_result.get("success", False) else "send_failed",
                "channel": channel,
                "success": send_result.get("success", False),
            })
        finally:
            _release_event_lock(event["id"])

    return results


def _get_attempt_history(sb, event_id: int) -> list[dict]:
    """Fetch previous recovery attempts for context."""
    res = (
        sb.table("recovery_attempts")
        .select("attempt_number,channel_used,outcome,notes,created_at")
        .eq("recovery_event_id", event_id)
        .order("attempt_number", desc=False)
        .limit(10)
        .execute()
    )
    return res.data or []


def _get_escalation_decision(event: dict, attempts: list[dict]) -> dict:
    """Get AI escalation decision based on event + attempt history."""
    attempt_count = event.get("attempt_count", 0)
    max_attempts = event.get("max_attempts") if event.get("max_attempts") is not None else 5

    if attempt_count >= max_attempts:
        return {"action": "give_up", "channel": "none", "tone": "final",
                "reasoning": f"Maximum attempts reached ({max_attempts}). Budget exhausted for this event."}

    attempt_summary = []
    blocked_channels = set()
    failed_channels = set()
    for a in attempts:
        if a.get("channel_used") == "payment_link":
            continue
        if a.get("outcome") == "blocked":
            blocked_channels.add(a.get("channel_used"))
            continue
        if a.get("outcome") == "failed":
            failed_channels.add(a.get("channel_used"))
        attempt_summary.append({
            "number": a.get("attempt_number"),
            "channel": a.get("channel_used"),
            "outcome": a.get("outcome"),
            "notes": (a.get("notes") or "")[:100],
        })

    user_msg = json.dumps({
        "event_type": event.get("event_type"),
        "amount": event.get("amount"),
        "currency": event.get("currency", "INR"),
        "failure_category": event.get("failure_category"),
        "recovery_probability": event.get("recovery_probability"),
        "attempt_count": attempt_count,
        "max_attempts": max_attempts,
        "attempts_remaining": max_attempts - attempt_count,
        "previous_attempts": attempt_summary,
        "blocked_channels": list(blocked_channels),
        "failed_channels": list(failed_channels),
        "recommended_channel": event.get("recommended_channel"),
        "backup_plan": event.get("alternative_action"),
        "has_email": bool(event.get("customer_email")),
        "has_phone": bool(event.get("customer_phone")),
    })

    result = ai_call(
        system_prompt=ESCALATION_PROMPT,
        user_message=user_msg,
        response_schema=ESCALATION_SCHEMA,
        temperature=0.15,
        max_tokens=250,
    )

    if result:
        if result.get("action") == "give_up" and attempt_count < max_attempts:
            outreach_attempts = [
                a for a in attempts
                if a.get("channel_used") != "payment_link"
                and a.get("outcome") != "blocked"
            ]
            failed_channels = {
                a.get("channel_used") for a in outreach_attempts
                if a.get("outcome") == "failed"
            }
            all_channels = {"whatsapp", "email", "sms"}
            available = all_channels - failed_channels
            has_contact = set()
            if event.get("customer_phone"):
                has_contact |= {"whatsapp", "sms"}
            if event.get("customer_email"):
                has_contact.add("email")
            untried_channels = available & has_contact

            all_truly_exhausted = (
                outreach_attempts
                and all(a.get("outcome") == "failed" for a in outreach_attempts)
                and not untried_channels
            )
            if not all_truly_exhausted or attempt_count == 0:
                logger.info(
                    "Event %d: AI said give_up at attempt %d/%d but budget remains — overriding to send (untried: %s)",
                    event["id"], attempt_count, max_attempts, untried_channels or "none, retrying",
                )
                blocked_chs = {
                    a.get("channel_used") for a in attempts
                    if a.get("channel_used") != "payment_link"
                    and a.get("outcome") in ("blocked", "failed")
                }
                last_channel = attempts[-1].get("channel_used") if attempts else None
                next_channel = _pick_next_channel(last_channel, event, avoid=blocked_chs)
                result = {
                    "action": "send",
                    "channel": next_channel,
                    "tone": "firm" if attempt_count <= 2 else "urgent",
                    "reasoning": f"Override: AI suggested give_up but {max_attempts - attempt_count} attempts remain. Switching channel.",
                }
        return result

    channel_rotation = ["whatsapp", "email", "sms", "whatsapp", "email"]
    return {
        "action": "send",
        "channel": channel_rotation[min(attempt_count, 4)],
        "tone": "firm" if attempt_count <= 2 else "urgent",
        "reasoning": f"Fallback: AI unavailable, rotating channels (attempt {attempt_count + 1}/{max_attempts})",
    }


def _pick_next_channel(last_channel: str | None, event: dict, avoid: set | None = None) -> str:
    """Pick a different channel from the last one used, avoiding blocked/failed channels."""
    has_phone = bool(event.get("customer_phone"))
    has_email = bool(event.get("customer_email"))
    avoid = avoid or set()

    preferred = []
    if has_phone and "whatsapp" not in avoid:
        preferred.append("whatsapp")
    if has_email and "email" not in avoid:
        preferred.append("email")
    if has_phone and "sms" not in avoid:
        preferred.append("sms")

    for ch in preferred:
        if ch != last_channel:
            return ch

    if preferred:
        return preferred[0]

    return "email" if has_email else "whatsapp"


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _reserve_attempt(sb, event, channel, decision, link):
    max_res = (
        sb.table("recovery_attempts")
        .select("attempt_number")
        .eq("recovery_event_id", event["id"])
        .order("attempt_number", desc=True)
        .limit(1)
        .execute()
    )
    next_number = (max_res.data[0]["attempt_number"] + 1) if max_res.data else 1
    idem_key = f"{event['id']}:escalation:{next_number}"
    sb.table("recovery_attempts").insert({
        "recovery_event_id": event["id"],
        "attempt_number": next_number,
        "channel_used": channel,
        "action_taken": f"{decision.get('tone', 'firm')} escalation via {channel}",
        "outcome": "reserved",
        "notes": decision.get("reasoning", ""),
        "idempotency_key": idem_key,
        "metadata": {"payment_link_url": link.get("short_url")},
    }).execute()
    return next_number, idem_key


def _finalize_attempt(sb, idem_key, channel, send_result, link, event):
    channel_used = send_result.get("channel_used") or channel
    outcome = "sent" if send_result.get("success") else (
        "blocked" if send_result.get("error") == "Cooldown active" else "failed"
    )
    try:
        sb.table("recovery_attempts").update({
            "channel_used": channel_used,
            "message_id": send_result.get("message_id", ""),
            "outcome": outcome,
            "metadata": {
                "payment_link_id": link.get("id"),
                "payment_link_url": link.get("short_url"),
                "escalation_level": event.get("escalation_level", 0) + 1,
                "send_error": send_result.get("error"),
                "degraded_from": send_result.get("degraded_from"),
                "degradation_path": send_result.get("degradation_path", []),
                "ai_personalized": True,
            },
        }).eq("idempotency_key", idem_key).execute()
    except Exception:
        logger.warning("Failed to finalize attempt %s", idem_key)


RETRY_DELAY_HOURS = {
    "upi_timeout": 1,
    "gateway_error": 1,
    "bank_downtime": 2,
    "card_expired": 6,
    "insufficient_funds": 8,
    "user_cancelled": 12,
    "recently_overdue": 24,
    "moderately_overdue": 48,
    "long_overdue": 48,
    "high_intent_abandonment": 2,
}


def _update_event_state(sb, event, decision):
    now = datetime.now(timezone.utc)
    category = event.get("failure_category", "")
    delay_hours = RETRY_DELAY_HOURS.get(category, 4)
    new_attempt_count = event.get("attempt_count", 0) + 1
    new_level = event.get("escalation_level", 0) + 1
    max_attempts = event.get("max_attempts") if event.get("max_attempts") is not None else 5

    if new_attempt_count >= max_attempts:
        sb.table("recovery_events").update({
            "status": "exhausted",
            "attempt_count": new_attempt_count,
            "last_attempt_at": now.isoformat(),
            "escalation_level": new_level,
            "current_strategy": "max_attempts_reached",
            "skip_reason": f"All {max_attempts} recovery attempts used",
            "next_action_at": None,
            "recovery_window_ends": None,
            "updated_at": now.isoformat(),
        }).eq("id", event["id"]).eq("status", "pending").execute()
        logger.info("Event %d: exhausted after %d/%d attempts", event["id"], new_attempt_count, max_attempts)
        return

    stage_map = {1: "first_contact_sent", 2: "follow_up_sent", 3: "escalated"}
    strategy = stage_map.get(new_level, f"escalation_level_{new_level}")

    sb.table("recovery_events").update({
        "attempt_count": new_attempt_count,
        "last_attempt_at": now.isoformat(),
        "escalation_level": new_level,
        "current_strategy": strategy,
        "next_action_at": (now + timedelta(hours=delay_hours)).isoformat(),
        "updated_at": now.isoformat(),
    }).eq("id", event["id"]).eq("status", "pending").execute()


def _mark_exhausted(sb, event, reason: str = ""):
    max_att = event.get("max_attempts") if event.get("max_attempts") is not None else 5
    exhausted_reason = reason or f"All {max_att} recovery attempts used"
    res = sb.table("recovery_events").update({
        "status": "exhausted",
        "current_strategy": "exhausted",
        "skip_reason": exhausted_reason,
        "next_action_at": None,
        "recovery_window_ends": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", event["id"]).eq("status", "pending").execute()
    if res.data:
        logger.info("Event %d marked as exhausted: %s", event["id"], exhausted_reason)
    else:
        logger.warning("Event %d: exhaustion skipped — status already changed", event["id"])

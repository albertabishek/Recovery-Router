"""
AI-powered escalation engine.
Analyzes attempt history and makes real decisions about next recovery action.
No hardcoded rotation — the AI decides based on what actually happened.
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.database import get_supabase
from app.redis_client import get_redis
from app.services.ai_client import ai_call
from app.services.payment_links import generate_payment_link
from app.services.messenger import send_message

logger = logging.getLogger(__name__)

ESCALATION_PROMPT = """You are the escalation decision agent for a payment recovery system. A customer hasn't completed their payment despite previous recovery attempts.

Your job: analyze what happened in previous attempts and decide the BEST next move. You will be given the event's max_attempts — the system already computed how many attempts this event deserves based on amount, probability, and failure type. Respect that budget.

## Decision framework

1. LOOK at previous attempts:
   - What channel was used? Did it succeed in delivering?
   - If WhatsApp was sent but customer didn't act → try email with more detail or SMS.
   - If email was sent but not opened → try WhatsApp or SMS for immediacy.
   - If delivery failed (provider error) → try the same channel again or switch.

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
    "action": {"type": "str", "allowed": ["send", "give_up"], "default": "give_up"},
    "channel": {"type": "str", "allowed": ["whatsapp", "email", "sms"], "default": "email"},
    "tone": {"type": "str", "allowed": ["friendly", "firm", "urgent", "final"], "default": "firm"},
}


def _acquire_event_lock(event_id: int, ttl: int = 120) -> bool:
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
            attempts = _get_attempt_history(sb, event["id"])
            decision = _get_escalation_decision(event, attempts)

            if decision.get("action") == "give_up":
                _mark_exhausted(sb, event, decision.get("reasoning", ""))
                results.append({"event_id": event["id"], "action": "exhausted"})
                continue

            channel = decision.get("channel", "email")
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

            _log_attempt(sb, event, channel, decision, send_result, link)
            _update_event_state(sb, event, decision)

            results.append({
                "event_id": event["id"],
                "action": "sent",
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
    max_attempts = event.get("max_attempts", 5) or 5

    if attempt_count >= max_attempts:
        return {"action": "give_up", "channel": "none", "tone": "final",
                "reasoning": f"Maximum attempts reached ({max_attempts}). Budget exhausted for this event."}

    attempt_summary = []
    for a in attempts:
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
        "recommended_channel": event.get("recommended_channel"),
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
            all_failed = attempts and all(
                a.get("outcome") == "failed" for a in attempts
            )
            if not all_failed:
                logger.info(
                    "Event %d: AI said give_up at attempt %d/%d but budget remains — overriding to send",
                    event["id"], attempt_count, max_attempts,
                )
                last_channel = attempts[-1].get("channel_used") if attempts else None
                next_channel = _pick_next_channel(last_channel, event)
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


def _pick_next_channel(last_channel: str | None, event: dict) -> str:
    """Pick a different channel from the last one used."""
    has_phone = bool(event.get("customer_phone"))
    has_email = bool(event.get("customer_email"))
    rotation = {
        "whatsapp": "email" if has_email else "sms",
        "email": "whatsapp" if has_phone else "sms",
        "sms": "email" if has_email else "whatsapp",
    }
    return rotation.get(last_channel, "email" if has_email else "whatsapp")


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _log_attempt(sb, event, channel, decision, send_result, link):
    channel_used = send_result.get("channel_used") or channel
    sb.table("recovery_attempts").insert({
        "recovery_event_id": event["id"],
        "attempt_number": event.get("attempt_count", 0) + 1,
        "channel_used": channel_used,
        "action_taken": f"{decision.get('tone', 'firm')} escalation via {channel_used}",
        "message_id": send_result.get("message_id", ""),
        "outcome": "sent" if send_result.get("success") else "failed",
        "notes": decision.get("reasoning", ""),
        "metadata": {
            "payment_link_id": link.get("id"),
            "payment_link_url": link.get("short_url"),
            "escalation_level": event.get("escalation_level", 0) + 1,
            "send_error": send_result.get("error"),
            "degraded_from": send_result.get("degraded_from"),
            "degradation_path": send_result.get("degradation_path", []),
            "ai_personalized": True,
        },
    }).execute()


def _update_event_state(sb, event, decision):
    now = datetime.now(timezone.utc)
    sb.table("recovery_events").update({
        "attempt_count": event.get("attempt_count", 0) + 1,
        "last_attempt_at": now.isoformat(),
        "escalation_level": event.get("escalation_level", 0) + 1,
        "current_strategy": decision.get("tone", "firm"),
        "next_action_at": (now + timedelta(hours=4)).isoformat(),
        "updated_at": now.isoformat(),
    }).eq("id", event["id"]).execute()


def _mark_exhausted(sb, event, reason: str = ""):
    exhausted_reason = reason or f"All {event.get('max_attempts', 5)} attempts used"
    sb.table("recovery_events").update({
        "status": "exhausted",
        "current_strategy": "exhausted",
        "skip_reason": exhausted_reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", event["id"]).execute()
    logger.info("Event %d marked as exhausted: %s", event["id"], exhausted_reason)

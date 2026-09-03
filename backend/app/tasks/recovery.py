import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import httpx
from celery.exceptions import Retry
from postgrest.exceptions import APIError
from app.celery_app import celery_app
from app.models import RecoveryEventInput
from app.database import get_supabase
from app.redis_client import get_redis
from app.services.classifier import classify_event
from app.services.router import route_action, compute_max_attempts
from app.services.payment_links import generate_payment_link
from app.services.messenger import send_message

IST = ZoneInfo("Asia/Kolkata")
QUIET_START_HOUR = 21
QUIET_END_HOUR = 9


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

TRANSIENT_ERRORS = (
    ConnectionError, TimeoutError, OSError,
    httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError,
)

logger = logging.getLogger(__name__)

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


def _check_durable_dedup(sb, event: RecoveryEventInput) -> dict | None:
    """DB-level dedup: check if an event with the same identifiers already exists.
    Returns {"id": ..., "match": ...} if duplicate found, None otherwise.
    Skips TEST_ prefixed IDs (simulator events are intentionally non-unique).
    """
    if event.payment_id and not event.payment_id.startswith("pay_TEST_"):
        res = sb.table("recovery_events").select("id").eq(
            "payment_id", event.payment_id
        ).limit(1).execute()
        if res.data:
            return {"id": res.data[0]["id"], "match": f"payment_id={event.payment_id}"}

    if event.order_id and not event.order_id.startswith("order_TEST_"):
        res = sb.table("recovery_events").select("id").eq(
            "order_id", event.order_id
        ).limit(1).execute()
        if res.data:
            return {"id": res.data[0]["id"], "match": f"order_id={event.order_id}"}

    if event.invoice_id:
        res = sb.table("recovery_events").select("id").eq(
            "invoice_id", event.invoice_id
        ).limit(1).execute()
        if res.data:
            return {"id": res.data[0]["id"], "match": f"invoice_id={event.invoice_id}"}

    return None


@celery_app.task(bind=True, max_retries=3, acks_late=True)
def process_recovery_event(self, event_data: dict) -> dict:
    """Merged pipeline: Classify -> Route -> Generate Link -> Send -> Log.
    Single atomic Celery task per event."""
    try:
        event = RecoveryEventInput(**event_data)

        classification = classify_event(event)

        sb = get_supabase()
        now = datetime.now(timezone.utc)
        recovery_window_ends = now + timedelta(hours=72)

        max_attempts = compute_max_attempts(
            amount=event.amount,
            recovery_probability=classification.recovery_probability,
            failure_category=classification.failure_category,
        )

        insert_data = {
            "event_type": event.event_type,
            "payment_id": event.payment_id,
            "order_id": event.order_id,
            "invoice_id": event.invoice_id,
            "amount": event.amount,
            "currency": event.currency,
            "method": event.method,
            "error_code": event.error_code,
            "error_description": event.error_description,
            "customer_email": event.customer_email,
            "customer_phone": event.customer_phone,
            "customer_name": event.customer_name,
            "cart_value": event.cart_value,
            "items_in_cart": event.items_in_cart,
            "days_overdue": event.days_overdue,
            "leak_type": classification.leak_type,
            "failure_category": classification.failure_category,
            "recovery_probability": classification.recovery_probability,
            "recommended_action": classification.recommended_action,
            "recommended_channel": classification.recommended_channel,
            "recommended_timing": classification.recommended_timing,
            "reasoning": classification.reasoning,
            "alternative_action": classification.alternative_action,
            "skip_reason": classification.skip_reason,
            "status": "pending",
            "recovery_window_ends": recovery_window_ends.isoformat(),
            "next_action_at": (now + timedelta(hours=RETRY_DELAY_HOURS.get(classification.failure_category, 4))).isoformat(),
            "source": event_data.get("source", "api"),
            "razorpay_raw": event_data.get("razorpay_raw", False),
            "fallback_classification": classification.fallback_used,
            "max_attempts": max_attempts,
        }

        dup = _check_durable_dedup(sb, event)
        if dup:
            logger.info("Durable dedup: event already exists (id=%d, matched on %s)",
                        dup["id"], dup["match"])
            return {"status": "duplicate", "event_id": dup["id"],
                    "reason": f"DB-level dedup: {dup['match']}"}

        res = sb.table("recovery_events").insert(insert_data).execute()
        if not res.data:
            raise ValueError("Failed to insert recovery event — empty response from Supabase")
        event_id = res.data[0]["id"]

        action = route_action(classification)

        if action.action == "no_action":
            sb.table("recovery_events").update({
                "status": "no_action_needed",
                "skip_reason": action.skip_reason,
                "next_action_at": None,
                "recovery_window_ends": None,
                "updated_at": now.isoformat(),
            }).eq("id", event_id).execute()

            return {"status": "no_action", "event_id": event_id, "reason": action.skip_reason}

        if action.delay_seconds > 0:
            sb.table("recovery_events").update({
                "next_action_at": (now + timedelta(seconds=action.delay_seconds)).isoformat(),
                "updated_at": now.isoformat(),
            }).eq("id", event_id).execute()

            _send_delayed.apply_async(
                args=[event_id, action.channel, event_data],
                countdown=action.delay_seconds,
            )

            return {
                "status": "delayed",
                "event_id": event_id,
                "channel": action.channel,
                "delay_seconds": action.delay_seconds,
            }

        if _is_quiet_hours():
            wake_at = _next_permitted_time()
            sb.table("recovery_events").update({
                "next_action_at": wake_at.isoformat(),
                "current_strategy": "quiet_hours_rescheduled",
                "updated_at": now.isoformat(),
            }).eq("id", event_id).execute()
            logger.info("Event %d: quiet hours — rescheduled initial send to %s", event_id, wake_at.isoformat())
            return {"status": "rescheduled_quiet_hours", "event_id": event_id, "wake_at": wake_at.isoformat()}

        idem_key = f"{event_id}:initial:1"
        try:
            sb.table("recovery_attempts").insert({
                "recovery_event_id": event_id,
                "attempt_number": 1,
                "channel_used": action.channel,
                "action_taken": f"{classification.recommended_action} via {action.channel}",
                "outcome": "reserved",
                "notes": classification.reasoning,
                "idempotency_key": idem_key,
            }).execute()
        except APIError as e:
            if e.json().get("code") == "23505":
                logger.info("Idempotency hit: %s already reserved/sent", idem_key)
                return {"status": "already_processed", "event_id": event_id}
            raise

        link_amount = event.cart_value if (event.cart_value and event.amount <= 0) else event.amount
        link = generate_payment_link(
            amount=link_amount,
            currency=event.currency,
            customer_name=event.customer_name or "Customer",
            customer_email=event.customer_email,
            customer_phone=event.customer_phone,
            order_id=event.order_id,
            event_type=event.event_type,
            failure_category=classification.failure_category,
            event_id=event_id,
            recovery_window_ends=recovery_window_ends,
        )

        if not link.get("short_url"):
            logger.error("Event %d: payment link creation failed, skipping outreach", event_id)
            sb.table("recovery_attempts").update({
                "outcome": "failed",
                "notes": "Payment link creation failed",
            }).eq("idempotency_key", idem_key).execute()
            sb.table("recovery_events").update({
                "current_strategy": "link_creation_failed",
                "next_action_at": (now + timedelta(minutes=15)).isoformat(),
                "updated_at": now.isoformat(),
            }).eq("id", event_id).execute()
            return {"status": "link_failed", "event_id": event_id}

        send_result = send_message(
            channel=action.channel,
            customer_name=event.customer_name or "Customer",
            customer_email=event.customer_email,
            customer_phone=event.customer_phone,
            amount=event.amount,
            currency=event.currency,
            failure_category=classification.failure_category,
            payment_link_url=link.get("short_url", ""),
            reasoning=classification.reasoning,
            personalization_hint=classification.personalization_hint,
        )

        channel_used = send_result.get("channel_used") or action.channel
        outcome = "sent" if send_result.get("success") else (
            "blocked" if send_result.get("error") == "Cooldown active" else "failed"
        )
        try:
            sb.table("recovery_attempts").update({
                "channel_used": channel_used,
                "action_taken": f"{classification.recommended_action} via {channel_used}",
                "message_id": send_result.get("message_id", ""),
                "outcome": outcome,
                "metadata": {
                    "payment_link_id": link.get("id"),
                    "payment_link_url": link.get("short_url"),
                    "send_error": send_result.get("error"),
                    "degraded_from": send_result.get("degraded_from"),
                    "degradation_path": send_result.get("degradation_path", []),
                    "ai_personalized": True,
                },
            }).eq("idempotency_key", idem_key).execute()
        except Exception:
            logger.warning("Failed to finalize attempt %s", idem_key)

        send_succeeded = send_result.get("success", False)
        delay_hours = RETRY_DELAY_HOURS.get(classification.failure_category, 4)

        if send_succeeded:
            if 1 >= max_attempts:
                update_data = {
                    "status": "exhausted",
                    "attempt_count": 1,
                    "last_attempt_at": now.isoformat(),
                    "escalation_level": 1,
                    "current_strategy": "max_attempts_reached",
                    "skip_reason": f"All {max_attempts} recovery attempts used",
                    "next_action_at": None,
                    "recovery_window_ends": None,
                    "updated_at": now.isoformat(),
                }
            else:
                update_data = {
                    "attempt_count": 1,
                    "last_attempt_at": now.isoformat(),
                    "escalation_level": 1,
                    "current_strategy": "first_contact_sent",
                    "next_action_at": (now + timedelta(hours=delay_hours)).isoformat(),
                    "updated_at": now.isoformat(),
                }
        else:
            is_hard_failure = send_result.get("error") != "Cooldown active"
            retry_minutes = 15
            update_data = {
                "current_strategy": "first_contact_failed",
                "next_action_at": (now + timedelta(minutes=retry_minutes)).isoformat(),
                "updated_at": now.isoformat(),
            }
            if is_hard_failure:
                update_data["delivery_failure_count"] = 1

        sb.table("recovery_events").update(update_data).eq("id", event_id).eq("status", "pending").execute()

        return {
            "status": "sent" if send_succeeded else "send_failed",
            "event_id": event_id,
            "channel": channel_used,
            "degraded_from": send_result.get("degraded_from"),
            "success": send_succeeded,
        }

    except TRANSIENT_ERRORS as exc:
        logger.warning("process_recovery_event transient error (will retry): %s", exc)
        backoff = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)
    except Exception as exc:
        logger.error("process_recovery_event permanent failure: %s", exc, exc_info=True)
        try:
            sb = get_supabase()
            sb.table("recovery_attempts").insert({
                "recovery_event_id": event_data.get("event_id") or 0,
                "attempt_number": 0,
                "channel_used": "system",
                "action_taken": "Task permanent failure",
                "outcome": "failed",
                "notes": f"Permanent error: {str(exc)[:500]}",
                "metadata": {"task": "process_recovery_event", "permanent_failure": True},
            }).execute()
        except Exception:
            pass
        return {"status": "permanent_failure", "error": str(exc)}


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def handle_recovery_retry_failure(self, data: dict) -> dict:
    """When a customer's payment fails on a recovery link we sent, log it on the parent event
    instead of creating a duplicate recovery event."""
    try:
        sb = get_supabase()
        r = get_redis()
        parent_id = data["parent_event_id"]
        now = datetime.now(timezone.utc)

        lock_key = f"lock:event:{parent_id}"
        if not r.set(lock_key, "1", nx=True, ex=60):
            logger.info("Event %s locked, retrying retry-failure log", parent_id)
            raise self.retry(countdown=5)

        try:
            res = sb.table("recovery_events").select("*").eq("id", parent_id).limit(1).execute()
            if not res.data:
                logger.warning("Parent event %s not found for retry failure", parent_id)
                return {"status": "parent_not_found", "parent_id": parent_id}

            parent = res.data[0]
            if parent["status"] not in ("pending", "paused", "exhausted"):
                logger.info("Parent event %s status=%s, skipping retry log", parent_id, parent['status'])
                return {"status": "parent_not_active", "parent_id": parent_id}

            error_desc = data.get("error_description") or ""

            is_cancellation = any(kw in error_desc.lower() for kw in [
                "cancelled", "canceled", "user aborted", "customer cancel",
            ])

            max_res = (
                sb.table("recovery_attempts")
                .select("attempt_number")
                .eq("recovery_event_id", parent_id)
                .order("attempt_number", desc=True)
                .limit(1)
                .execute()
            )
            next_number = (max_res.data[0]["attempt_number"] + 1) if max_res.data else 1

            sb.table("recovery_attempts").insert({
                "recovery_event_id": parent_id,
                "attempt_number": next_number,
                "channel_used": "payment_link",
                "action_taken": (
                    f"Customer attempted payment via {data.get('method', 'unknown')} "
                    f"but {'cancelled' if is_cancellation else 'failed'}"
                ),
                "outcome": "failed",
                "notes": f"Error: {data.get('error_code')}: {error_desc}",
                "idempotency_key": f"{parent_id}:retry_failure:{next_number}",
                "metadata": {
                    "payment_id": data.get("payment_id"),
                    "order_id": data.get("order_id"),
                    "method": data.get("method"),
                    "error_code": data.get("error_code"),
                    "is_cancellation": is_cancellation,
                    "is_customer_retry": True,
                },
            }).execute()

            sb.table("recovery_events").update({
                "last_attempt_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }).eq("id", parent_id).in_("status", ["pending", "paused", "exhausted"]).execute()

            logger.info(
                "Retry failure logged on event %s: cancellation=%s",
                parent_id, is_cancellation
            )
            return {
                "status": "logged",
                "parent_id": parent_id,
                "attempt_number": next_number,
                "is_cancellation": is_cancellation,
            }
        finally:
            r.delete(lock_key)
    except Retry:
        raise
    except TRANSIENT_ERRORS as exc:
        logger.warning("handle_recovery_retry_failure transient error: %s", exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    except Exception as exc:
        logger.error("handle_recovery_retry_failure permanent failure: %s", exc, exc_info=True)
        return {"status": "permanent_failure", "error": str(exc)}


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def _send_delayed(self, event_id: int, channel: str, event_data: dict):
    """Execute a delayed send for an event that was classified with a timing delay."""
    try:
        event = RecoveryEventInput(**event_data)
        sb = get_supabase()
        r = get_redis()
        now = datetime.now(timezone.utc)

        lock_key = f"lock:event:{event_id}"
        if not r.set(lock_key, "delayed", nx=True, ex=300):
            logger.info("Delayed send: event %d locked by another process, skipping", event_id)
            return {"status": "skipped_locked", "event_id": event_id}

        try:
            ev_res = sb.table("recovery_events").select("*").eq("id", event_id).limit(1).execute()
            if not ev_res.data:
                logger.warning("Delayed send: event %s not found", event_id)
                return {"status": "not_found", "event_id": event_id}

            ev = ev_res.data[0]
            if ev.get("status") != "pending":
                logger.info("Delayed send: event %s status=%s, skipping", event_id, ev['status'])
                return {"status": "skipped", "event_id": event_id}

            if (ev.get("attempt_count", 0) or 0) > 0:
                logger.info("Delayed send: event %d already has %d attempts (escalation handled it), skipping",
                            event_id, ev["attempt_count"])
                return {"status": "skipped_already_sent", "event_id": event_id}

            if _is_quiet_hours():
                wake_at = _next_permitted_time()
                sb.table("recovery_events").update({
                    "next_action_at": wake_at.isoformat(),
                    "current_strategy": "quiet_hours_rescheduled",
                    "updated_at": now.isoformat(),
                }).eq("id", event_id).eq("status", "pending").execute()
                logger.info("Delayed send event %d: quiet hours — rescheduled to %s", event_id, wake_at.isoformat())
                return {"status": "rescheduled_quiet_hours", "event_id": event_id}

            recovery_window_ends = None
            if ev.get("recovery_window_ends"):
                try:
                    recovery_window_ends = datetime.fromisoformat(ev["recovery_window_ends"])
                except (ValueError, TypeError):
                    pass

            max_res = (
                sb.table("recovery_attempts")
                .select("attempt_number")
                .eq("recovery_event_id", event_id)
                .order("attempt_number", desc=True)
                .limit(1)
                .execute()
            )
            next_number = (max_res.data[0]["attempt_number"] + 1) if max_res.data else 1
            idem_key = f"{event_id}:delayed:{next_number}"

            try:
                sb.table("recovery_attempts").insert({
                    "recovery_event_id": event_id,
                    "attempt_number": next_number,
                    "channel_used": channel,
                    "action_taken": f"delayed_send via {channel}",
                    "outcome": "reserved",
                    "notes": f"Delayed send (originally scheduled for {channel})",
                    "idempotency_key": idem_key,
                }).execute()
            except APIError as e:
                if e.json().get("code") == "23505":
                    logger.info("Idempotency hit: %s already reserved/sent", idem_key)
                    return {"status": "already_processed", "event_id": event_id}
                raise

            link = generate_payment_link(
                amount=event.amount,
                currency=event.currency,
                customer_name=event.customer_name or "Customer",
                customer_email=event.customer_email,
                customer_phone=event.customer_phone,
                order_id=event.order_id,
                event_type=event.event_type,
                failure_category=ev.get("failure_category", "unknown"),
                event_id=event_id,
                recovery_window_ends=recovery_window_ends,
            )

            if not link.get("short_url"):
                logger.error("Delayed send event %d: payment link creation failed, rescheduling", event_id)
                sb.table("recovery_attempts").update({
                    "outcome": "failed",
                    "notes": "Payment link creation failed",
                }).eq("idempotency_key", idem_key).execute()
                sb.table("recovery_events").update({
                    "current_strategy": "link_creation_failed",
                    "next_action_at": (now + timedelta(minutes=15)).isoformat(),
                    "updated_at": now.isoformat(),
                }).eq("id", event_id).eq("status", "pending").execute()
                return {"status": "link_failed", "event_id": event_id}

            send_result = send_message(
                channel=channel,
                customer_name=event.customer_name or "Customer",
                customer_email=event.customer_email,
                customer_phone=event.customer_phone,
                amount=event.amount,
                currency=event.currency,
                failure_category=ev.get("failure_category", "unknown"),
                payment_link_url=link.get("short_url", ""),
                reasoning=ev.get("reasoning", ""),
                personalization_hint=ev.get("personalization_hint"),
            )

            channel_used = send_result.get("channel_used") or channel
            outcome = "sent" if send_result.get("success") else (
                "blocked" if send_result.get("error") == "Cooldown active" else "failed"
            )
            try:
                sb.table("recovery_attempts").update({
                    "channel_used": channel_used,
                    "action_taken": f"delayed_send via {channel_used}",
                    "message_id": send_result.get("message_id", ""),
                    "outcome": outcome,
                    "metadata": {
                        "payment_link_id": link.get("id"),
                        "payment_link_url": link.get("short_url"),
                        "send_error": send_result.get("error"),
                        "degraded_from": send_result.get("degraded_from"),
                        "degradation_path": send_result.get("degradation_path", []),
                        "ai_personalized": True,
                    },
                }).eq("idempotency_key", idem_key).execute()
            except Exception:
                logger.warning("Failed to finalize attempt %s", idem_key)

            send_succeeded = send_result.get("success", False)
            delay_hours = RETRY_DELAY_HOURS.get(ev.get("failure_category", ""), 4)

            if send_succeeded:
                max_att = ev.get("max_attempts") if ev.get("max_attempts") is not None else 5
                if 1 >= max_att:
                    sb.table("recovery_events").update({
                        "status": "exhausted",
                        "attempt_count": 1,
                        "last_attempt_at": now.isoformat(),
                        "escalation_level": 1,
                        "current_strategy": "max_attempts_reached",
                        "skip_reason": f"All {max_att} recovery attempts used",
                        "next_action_at": None,
                        "recovery_window_ends": None,
                        "updated_at": now.isoformat(),
                    }).eq("id", event_id).eq("status", "pending").execute()
                else:
                    sb.table("recovery_events").update({
                        "attempt_count": 1,
                        "last_attempt_at": now.isoformat(),
                        "escalation_level": 1,
                        "current_strategy": "first_contact_sent",
                        "next_action_at": (now + timedelta(hours=delay_hours)).isoformat(),
                        "updated_at": now.isoformat(),
                    }).eq("id", event_id).eq("status", "pending").execute()
            else:
                is_hard_failure = send_result.get("error") != "Cooldown active"
                delayed_fail_update = {
                    "current_strategy": "first_contact_failed",
                    "next_action_at": (now + timedelta(minutes=15)).isoformat(),
                    "updated_at": now.isoformat(),
                }
                if is_hard_failure:
                    delayed_fail_update["delivery_failure_count"] = 1
                sb.table("recovery_events").update(
                    delayed_fail_update
                ).eq("id", event_id).eq("status", "pending").execute()

            return {
                "status": "sent" if send_succeeded else "send_failed",
                "event_id": event_id,
                "channel": channel_used,
                "success": send_succeeded,
            }
        finally:
            r.delete(lock_key)

    except TRANSIENT_ERRORS as exc:
        logger.warning("_send_delayed transient error for event %d: %s", event_id, exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    except Exception as exc:
        logger.error("_send_delayed permanent failure for event %d: %s", event_id, exc, exc_info=True)
        return {"status": "permanent_failure", "event_id": event_id, "error": str(exc)}

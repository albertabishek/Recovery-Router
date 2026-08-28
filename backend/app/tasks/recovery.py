import logging
from datetime import datetime, timedelta, timezone
from app.celery_app import celery_app
from app.models import RecoveryEventInput
from app.database import get_supabase
from app.services.classifier import classify_event
from app.services.router import route_action, compute_max_attempts
from app.services.payment_links import generate_payment_link
from app.services.messenger import send_message

logger = logging.getLogger(__name__)


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
            "next_action_at": now.isoformat(),
            "source": event_data.get("source", "api"),
            "razorpay_raw": event_data.get("razorpay_raw", False),
            "fallback_classification": classification.fallback_used,
            "max_attempts": max_attempts,
        }

        res = sb.table("recovery_events").insert(insert_data).execute()
        if not res.data:
            raise ValueError("Failed to insert recovery event — empty response from Supabase")
        event_id = res.data[0]["id"]

        action = route_action(classification)

        if action.action == "no_action":
            sb.table("recovery_events").update({
                "status": "no_action_needed",
                "skip_reason": action.skip_reason,
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

        sb.table("recovery_attempts").insert({
            "recovery_event_id": event_id,
            "attempt_number": 1,
            "channel_used": channel_used,
            "action_taken": f"{classification.recommended_action} via {channel_used}",
            "message_id": send_result.get("message_id", ""),
            "outcome": "sent" if send_result.get("success") else "failed",
            "notes": classification.reasoning,
            "metadata": {
                "payment_link_id": link.get("id"),
                "payment_link_url": link.get("short_url"),
                "send_error": send_result.get("error"),
                "degraded_from": send_result.get("degraded_from"),
                "degradation_path": send_result.get("degradation_path", []),
                "ai_personalized": True,
            },
        }).execute()

        update_data = {
            "attempt_count": 1,
            "last_attempt_at": now.isoformat(),
            "next_action_at": (now + timedelta(hours=4)).isoformat(),
            "updated_at": now.isoformat(),
        }
        sb.table("recovery_events").update(update_data).eq("id", event_id).execute()

        return {
            "status": "sent",
            "event_id": event_id,
            "channel": channel_used,
            "degraded_from": send_result.get("degraded_from"),
            "success": send_result.get("success", False),
        }

    except Exception as exc:
        logger.error(f"process_recovery_event failed: {exc}")
        backoff = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=backoff)


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def handle_recovery_retry_failure(self, data: dict) -> dict:
    """When a customer's payment fails on a recovery link we sent, log it on the parent event
    instead of creating a duplicate recovery event."""
    try:
        sb = get_supabase()
        parent_id = data["parent_event_id"]
        now = datetime.now(timezone.utc)

        res = sb.table("recovery_events").select("*").eq("id", parent_id).limit(1).execute()
        if not res.data:
            logger.warning(f"Parent event {parent_id} not found for retry failure")
            return {"status": "parent_not_found", "parent_id": parent_id}

        parent = res.data[0]
        if parent["status"] not in ("pending", "no_action_needed"):
            logger.info(f"Parent event {parent_id} status={parent['status']}, skipping retry log")
            return {"status": "parent_not_active", "parent_id": parent_id}

        attempt_count = (parent.get("attempt_count") or 0) + 1
        error_desc = data.get("error_description") or ""
        max_attempts = parent.get("max_attempts") or 3

        is_cancellation = any(kw in error_desc.lower() for kw in [
            "cancelled", "canceled", "user aborted", "customer cancel",
        ])

        sb.table("recovery_attempts").insert({
            "recovery_event_id": parent_id,
            "attempt_number": attempt_count,
            "channel_used": "payment_link",
            "action_taken": (
                f"Customer attempted payment via {data.get('method', 'unknown')} "
                f"but {'cancelled' if is_cancellation else 'failed'}"
            ),
            "outcome": "failed",
            "notes": f"Error: {data.get('error_code')}: {error_desc}",
            "metadata": {
                "payment_id": data.get("payment_id"),
                "order_id": data.get("order_id"),
                "method": data.get("method"),
                "error_code": data.get("error_code"),
                "is_cancellation": is_cancellation,
            },
        }).execute()

        update_data = {
            "attempt_count": attempt_count,
            "last_attempt_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if is_cancellation and attempt_count >= max_attempts:
            update_data["status"] = "exhausted"
            update_data["skip_reason"] = "Customer cancelled payment on recovery link"
            update_data["current_strategy"] = "exhausted"
        elif is_cancellation:
            update_data["next_action_at"] = (now + timedelta(hours=24)).isoformat()
        else:
            update_data["next_action_at"] = (now + timedelta(hours=4)).isoformat()

        sb.table("recovery_events").update(update_data).eq("id", parent_id).execute()

        logger.info(
            f"Retry failure logged on event {parent_id}: attempt #{attempt_count}, "
            f"cancellation={is_cancellation}"
        )
        return {
            "status": "logged",
            "parent_id": parent_id,
            "attempt_count": attempt_count,
            "is_cancellation": is_cancellation,
        }
    except Exception as exc:
        logger.error(f"handle_recovery_retry_failure failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2, acks_late=True)
def _send_delayed(self, event_id: int, channel: str, event_data: dict):
    """Execute a delayed send for an event that was classified with a timing delay."""
    try:
        event = RecoveryEventInput(**event_data)
        sb = get_supabase()
        now = datetime.now(timezone.utc)

        ev_res = sb.table("recovery_events").select("*").eq("id", event_id).limit(1).execute()
        if not ev_res.data:
            logger.warning(f"Delayed send: event {event_id} not found")
            return {"status": "not_found", "event_id": event_id}

        ev = ev_res.data[0]
        if ev.get("status") != "pending":
            logger.info(f"Delayed send: event {event_id} status={ev['status']}, skipping")
            return {"status": "skipped", "event_id": event_id}

        recovery_window_ends = None
        if ev.get("recovery_window_ends"):
            try:
                recovery_window_ends = datetime.fromisoformat(ev["recovery_window_ends"])
            except (ValueError, TypeError):
                pass

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

        sb.table("recovery_attempts").insert({
            "recovery_event_id": event_id,
            "attempt_number": 1,
            "channel_used": channel_used,
            "action_taken": f"delayed_send via {channel_used}",
            "message_id": send_result.get("message_id", ""),
            "outcome": "sent" if send_result.get("success") else "failed",
            "notes": f"Delayed send (originally scheduled for {channel})",
            "metadata": {
                "payment_link_id": link.get("id"),
                "payment_link_url": link.get("short_url"),
                "send_error": send_result.get("error"),
                "degraded_from": send_result.get("degraded_from"),
                "degradation_path": send_result.get("degradation_path", []),
                "ai_personalized": True,
            },
        }).execute()

        sb.table("recovery_events").update({
            "attempt_count": 1,
            "last_attempt_at": now.isoformat(),
            "next_action_at": (now + timedelta(hours=4)).isoformat(),
            "updated_at": now.isoformat(),
        }).eq("id", event_id).execute()

        return {
            "status": "sent",
            "event_id": event_id,
            "channel": channel_used,
            "success": send_result.get("success", False),
        }

    except Exception as exc:
        logger.error(f"_send_delayed failed for event {event_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

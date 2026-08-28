import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException
from app.config import settings
from app.models import WebhookResponse
from app.utils.normalizer import normalize_webhook
from app.utils.dedup import is_duplicate, get_dedup_identifier
from app.utils.rate_limiter import check_rate_limit
from app.tasks.recovery import process_recovery_event, handle_recovery_retry_failure
from app.services.recovery_tracker import process_payment_captured
from app.database import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhooks"])


def _verify_razorpay_signature(raw_body: bytes, signature: str) -> bool:
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        return True
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/recovery-router", response_model=WebhookResponse)
async def recovery_router_webhook(request: Request):
    """Entry point for all recovery events (payment failures, cart abandonment, invoices)."""
    if not check_rate_limit("webhook:recovery-router", max_requests=100, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    raw_body = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not _verify_razorpay_signature(raw_body, sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    body = await request.json()

    identifier = get_dedup_identifier(body)
    if identifier and is_duplicate(body.get("event_type", "event"), identifier):
        return WebhookResponse(status="duplicate", message="Event already processed")

    try:
        event = normalize_webhook(body)
    except Exception as e:
        logger.error(f"Payload normalization failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload format")

    event_data = event.model_dump()
    if body.get("event") == "payment.failed":
        event_data["razorpay_raw"] = True
    event_data["source"] = body.get("source", "api")

    if body.get("event") == "payment.failed":
        parent_id = _find_parent_recovery_event(body)
        if parent_id:
            entity = body.get("payload", {}).get("payment", {}).get("entity", {})
            try:
                handle_recovery_retry_failure.delay({
                    "parent_event_id": parent_id,
                    "payment_id": entity.get("id"),
                    "order_id": entity.get("order_id"),
                    "error_code": entity.get("error_code"),
                    "error_description": entity.get("error_description") or entity.get("error_reason"),
                    "method": entity.get("method"),
                    "customer_email": entity.get("email"),
                    "customer_phone": entity.get("contact"),
                })
            except Exception as e:
                logger.error(f"Failed to dispatch retry failure task: {e}")
                raise HTTPException(status_code=503, detail="Service temporarily unavailable")
            return WebhookResponse(status="accepted", message="Recovery retry failure logged on parent event")

    try:
        process_recovery_event.delay(event_data)
    except Exception as e:
        logger.error(f"Failed to dispatch Celery task: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    return WebhookResponse(status="accepted", message="Event queued for processing")


@router.post("/recovery-tracker", response_model=WebhookResponse)
async def recovery_tracker_webhook(request: Request):
    """Feedback loop: mark events as recovered when payment is captured."""
    if not check_rate_limit("webhook:recovery-tracker", max_requests=100, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    raw_body = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not _verify_razorpay_signature(raw_body, sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    body = await request.json()

    event_type = body.get("event", "")
    if event_type not in ("payment.captured", "payment_link.paid"):
        return WebhookResponse(status="ignored", message=f"Unhandled event type: {event_type}")

    result = process_payment_captured(body)

    return WebhookResponse(
        status=result.get("status", "unknown"),
        message=f"Tracker result: {result.get('status')}",
        event_id=result.get("event_id"),
    )


def _find_parent_recovery_event(body: dict) -> int | None:
    """Check if this payment.failed webhook is from a recovery link we sent.

    Returns the parent recovery_event_id if found, None otherwise.
    Two-pass lookup:
      1. Check payment entity notes for source=recovery_router (set by checkout page)
      2. Check recovery_attempts metadata for matching order_id (belt-and-suspenders)
    """
    entity = body.get("payload", {}).get("payment", {}).get("entity", {})
    notes = entity.get("notes") or {}
    order_id = entity.get("order_id")

    if notes.get("source") == "recovery_router" and order_id:
        logger.info(f"Webhook has recovery_router notes, order={order_id}")

    if not order_id:
        return None

    try:
        sb = get_supabase()
        res = sb.table("recovery_attempts").select("recovery_event_id").filter(
            "metadata->>payment_link_id", "eq", order_id
        ).limit(1).execute()
        if res.data:
            parent_id = res.data[0]["recovery_event_id"]
            logger.info(f"Webhook order {order_id} belongs to recovery event {parent_id}")
            return parent_id
    except Exception as e:
        logger.warning(f"Failed to check for parent recovery event: {e}")

    return None

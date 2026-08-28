from app.models import RecoveryEventInput


def normalize_webhook(body: dict) -> RecoveryEventInput:
    """Normalize both raw Razorpay payment.failed webhooks and custom format payloads."""
    if body.get("event") == "payment.failed":
        return _normalize_razorpay_raw(body)
    return RecoveryEventInput(**body)


def _normalize_razorpay_raw(body: dict) -> RecoveryEventInput:
    """Extract fields from Razorpay's nested payment.failed webhook payload."""
    entity = body.get("payload", {}).get("payment", {}).get("entity", {})
    error = entity.get("error_meta", {})

    return RecoveryEventInput(
        event_type="payment_failure",
        payment_id=entity.get("id"),
        order_id=entity.get("order_id"),
        amount=(entity.get("amount", 0) or 0) / 100,
        currency=entity.get("currency", "INR"),
        method=entity.get("method"),
        error_code=entity.get("error_code") or error.get("reason"),
        error_description=entity.get("error_description")
        or entity.get("error_reason"),
        customer_email=entity.get("email"),
        customer_phone=entity.get("contact"),
        customer_name=entity.get("notes", {}).get("customer_name", "Unknown"),
    )

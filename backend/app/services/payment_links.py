import json
import secrets
import logging
import httpx
from datetime import datetime
from app.config import settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

FALLBACK_URL = f"{settings.FRONTEND_URL or 'http://localhost:5173'}"
RZP_BASE = "https://api.razorpay.com/v1"
CHECKOUT_TOKEN_TTL = 86400


def _rzp_auth():
    return (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)


def _store_checkout_context(order_id: str, customer_name: str, customer_email: str | None, customer_phone: str | None) -> str:
    """Store customer details in Redis and return a lookup token."""
    r = get_redis()
    token = secrets.token_urlsafe(24)
    data = json.dumps({
        "order_id": order_id,
        "name": customer_name or "Customer",
        "email": customer_email or "",
        "phone": customer_phone or "",
    })
    r.set(f"checkout:{token}", data, ex=CHECKOUT_TOKEN_TTL)
    return token


def get_checkout_context(token: str) -> dict | None:
    """Retrieve customer details from Redis by checkout token."""
    r = get_redis()
    data = r.get(f"checkout:{token}")
    if not data:
        return None
    return json.loads(data)


def generate_payment_link(
    amount: float,
    currency: str,
    customer_name: str,
    customer_email: str | None,
    customer_phone: str | None,
    order_id: str | None,
    event_type: str,
    failure_category: str,
    event_id: int,
    recovery_window_ends: datetime | None,
) -> dict:
    """Create a Razorpay order and return a checkout URL.

    Uses the Orders API (no test-mode limit) + our hosted checkout page
    instead of Payment Links API (30-link test-mode limit).
    Customer PII is stored server-side in Redis, referenced by token.
    """
    if amount <= 0:
        logger.warning("Skipping payment link: amount=%s", amount)
        return {"id": None, "short_url": FALLBACK_URL, "status": "skipped"}

    amount_paise = int(amount * 100)

    payload = {
        "amount": amount_paise,
        "currency": currency,
        "notes": {
            "source": "recovery_router",
            "event_type": event_type,
            "failure_category": failure_category,
            "recovery_event_id": str(event_id),
            "original_order_id": order_id or "",
        },
    }

    try:
        resp = httpx.post(
            f"{RZP_BASE}/orders",
            auth=_rzp_auth(),
            json=payload,
            timeout=10,
        )

        if resp.status_code in (200, 201):
            data = resp.json()
            rzp_order_id = data["id"]
            token = _store_checkout_context(
                rzp_order_id, customer_name, customer_email, customer_phone,
            )
            checkout_url = f"{settings.API_BASE_URL}/pay/{rzp_order_id}?t={token}"
            logger.info("Order created: %s", rzp_order_id)
            return {
                "id": rzp_order_id,
                "short_url": checkout_url,
                "status": "created",
            }

        logger.error("Razorpay Orders API error: %d %s", resp.status_code, resp.text[:200])
        return {"id": None, "short_url": FALLBACK_URL, "status": "api_error"}

    except Exception as e:
        logger.error("Payment link generation failed: %s", e)
        return {"id": None, "short_url": FALLBACK_URL, "status": "error"}

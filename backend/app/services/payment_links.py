import logging
import httpx
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

FALLBACK_URL = "https://rzp.io/i/recovery"
RZP_BASE = "https://api.razorpay.com/v1"


def _rzp_auth():
    return (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)


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
    """
    if amount <= 0:
        logger.warning(f"Skipping payment link: amount={amount}")
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
            checkout_url = (
                f"{settings.API_BASE_URL}/pay/{rzp_order_id}"
                f"?name={_url_encode(customer_name or 'Customer')}"
                f"&email={_url_encode(customer_email or '')}"
                f"&phone={_url_encode(customer_phone or '')}"
            )
            logger.info(f"Order created: {rzp_order_id} -> {checkout_url}")
            return {
                "id": rzp_order_id,
                "short_url": checkout_url,
                "status": "created",
            }

        logger.error(f"Razorpay Orders API error: {resp.status_code} {resp.text[:200]}")
        return {"id": None, "short_url": FALLBACK_URL, "status": "api_error"}

    except Exception as e:
        logger.error(f"Payment link generation failed: {e}")
        return {"id": None, "short_url": FALLBACK_URL, "status": "error"}


def _url_encode(s: str) -> str:
    from urllib.parse import quote
    return quote(str(s), safe="")

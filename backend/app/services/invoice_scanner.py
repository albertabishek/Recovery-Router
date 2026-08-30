import logging
import math
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.database import get_supabase

logger = logging.getLogger(__name__)


def fetch_overdue_invoices() -> list[dict]:
    """Fetch issued invoices from Razorpay and convert to recovery event format."""
    try:
        items = []
        skip = 0
        page_size = 100
        while True:
            resp = httpx.get(
                "https://api.razorpay.com/v1/invoices",
                params={"type": "invoice", "status": "issued", "count": page_size, "skip": skip},
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("Razorpay invoice API error: %d", resp.status_code)
                break
            batch = resp.json().get("items", [])
            items.extend(batch)
            if len(batch) < page_size:
                break
            skip += page_size
        events = []

        all_ids = [inv.get("id") for inv in items if inv.get("id")]
        tracked_ids = _already_tracked_batch(all_ids) if all_ids else set()

        for inv in items:
            invoice_id = inv.get("id")
            if invoice_id in tracked_ids:
                continue

            due_date = inv.get("due_date") or inv.get("date")
            if due_date:
                days_overdue = math.floor(
                    (datetime.now(timezone.utc).timestamp() - due_date) / 86400
                )
                if days_overdue < 1:
                    continue
            else:
                continue

            customer = inv.get("customer_details", {})
            events.append({
                "event_type": "invoice_overdue",
                "invoice_id": invoice_id,
                "order_id": inv.get("order_id"),
                "amount": (inv.get("amount", 0) or 0) / 100,
                "currency": inv.get("currency", "INR"),
                "customer_name": customer.get("name", "Unknown"),
                "customer_email": customer.get("email"),
                "customer_phone": customer.get("contact"),
                "days_overdue": days_overdue,
            })

        logger.info("Found %d new overdue invoices", len(events))
        return events

    except Exception as e:
        logger.error("Invoice scan failed: %s", e)
        return []


def _already_tracked_batch(invoice_ids: list[str]) -> set[str]:
    """Check which invoices are already in recovery_events (single query)."""
    if not invoice_ids:
        return set()
    sb = get_supabase()
    res = sb.table("recovery_events").select("invoice_id").in_("invoice_id", invoice_ids).execute()
    return {row["invoice_id"] for row in (res.data or [])}

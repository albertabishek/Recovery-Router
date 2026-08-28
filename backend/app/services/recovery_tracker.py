import logging
from datetime import datetime, timezone
from app.database import get_supabase

logger = logging.getLogger(__name__)


def process_payment_captured(body: dict) -> dict:
    """Handle payment.captured or payment_link.paid webhook.
    Ghost recovery fix: only mark recovered if attempt_count > 0.

    Matching strategy (tries each in order until a hit):
      1. notes.recovery_event_id  — set when we generated the payment link
      2. payment_link reference_id — our order_id stored as reference_id
      3. order_id on the recovery event
      4. payment_id on the recovery event
    """
    event_type = body.get("event", "")
    entity = body.get("payload", {}).get("payment", {}).get("entity", {})
    plink_entity = body.get("payload", {}).get("payment_link", {}).get("entity", {})

    payment_id = entity.get("id")
    order_id = entity.get("order_id")
    amount = (entity.get("amount", 0) or 0) / 100
    method = entity.get("method")
    notes = entity.get("notes") or plink_entity.get("notes") or {}
    reference_id = plink_entity.get("reference_id") or entity.get("reference_id")

    recovery_event_id = notes.get("recovery_event_id")

    if not order_id and not payment_id and not recovery_event_id and not reference_id:
        return {"status": "ignored", "reason": "No identifiers found"}

    sb = get_supabase()
    res = None

    if recovery_event_id:
        res = sb.table("recovery_events").select("*").eq("id", int(recovery_event_id)).eq("status", "pending").limit(1).execute()

    if (not res or not res.data) and reference_id:
        res = sb.table("recovery_events").select("*").eq("order_id", reference_id).eq("status", "pending").limit(1).execute()

    if (not res or not res.data) and order_id:
        res = sb.table("recovery_events").select("*").eq("order_id", order_id).eq("status", "pending").limit(1).execute()

    if (not res or not res.data) and payment_id:
        res = sb.table("recovery_events").select("*").eq("payment_id", payment_id).eq("status", "pending").limit(1).execute()

    if not res.data:
        logger.info(f"No pending recovery event for order_id={order_id}, payment_id={payment_id}")
        return {"status": "no_match", "reason": "No pending recovery event found"}

    event = res.data[0]

    if event.get("attempt_count", 0) == 0:
        upd = sb.table("recovery_events").update({
            "status": "organic_recovery",
            "recovered_at": datetime.now(timezone.utc).isoformat(),
            "recovered_amount": amount,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", event["id"]).eq("status", "pending").execute()

        if not upd.data:
            logger.warning(f"Event {event['id']} already processed (race avoided)")
            return {"status": "already_processed", "event_id": event["id"]}

        logger.info(f"Organic recovery logged for event {event['id']} (0 attempts made)")
        return {"status": "organic_recovery", "event_id": event["id"]}

    upd = sb.table("recovery_events").update({
        "status": "recovered",
        "recovered_at": datetime.now(timezone.utc).isoformat(),
        "recovered_amount": amount,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", event["id"]).eq("status", "pending").execute()

    if not upd.data:
        logger.warning(f"Event {event['id']} already processed (race avoided)")
        return {"status": "already_processed", "event_id": event["id"]}

    logger.info(f"Recovery confirmed for event {event['id']} after {event['attempt_count']} attempts")
    return {
        "status": "recovered",
        "event_id": event["id"],
        "attempts_made": event["attempt_count"],
        "amount": amount,
    }



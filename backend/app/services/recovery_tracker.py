import logging
from datetime import datetime, timezone
from app.database import get_supabase

logger = logging.getLogger(__name__)


def process_payment_captured(body: dict) -> dict:
    """Handle payment.captured or payment_link.paid webhook.
    Ghost recovery fix: only mark recovered if attempt_count > 0.

    Reconciliation checks:
      - Payment entity status must be "captured"
      - Currency must match the recovery event
      - Captured amount must be within 1% tolerance of event amount
      - Payment ID must not already be attributed to another recovery

    Matching strategy (tries each in order until a hit):
      1. notes.recovery_event_id  — set when we generated the payment link
      2. payment_link reference_id — our order_id stored as reference_id
      3. order_id on the recovery event (skip fake TEST_ ids)
      4. payment_id on the recovery event (skip fake TEST_ ids)
    """
    event_type = body.get("event", "")
    entity = body.get("payload", {}).get("payment", {}).get("entity", {})
    plink_entity = body.get("payload", {}).get("payment_link", {}).get("entity", {})

    payment_id = entity.get("id")
    order_id = entity.get("order_id")
    amount = (entity.get("amount", 0) or 0) / 100
    currency = entity.get("currency", "INR")
    method = entity.get("method")
    entity_status = entity.get("status", "")
    notes = entity.get("notes") or plink_entity.get("notes") or {}
    reference_id = plink_entity.get("reference_id") or entity.get("reference_id")

    recovery_event_id = notes.get("recovery_event_id")

    logger.info(
        "Recovery tracker: event=%s payment_id=%s order_id=%s "
        "recovery_event_id=%s reference_id=%s amount=%.2f currency=%s "
        "entity_status=%s method=%s",
        event_type, payment_id, order_id,
        recovery_event_id, reference_id, amount, currency,
        entity_status, method,
    )

    if entity_status and entity_status != "captured":
        logger.warning(
            "Reconciliation rejected: entity status is '%s', expected 'captured' "
            "(payment_id=%s)", entity_status, payment_id,
        )
        return {"status": "rejected", "reason": f"Payment status is '{entity_status}', not 'captured'"}

    if not order_id and not payment_id and not recovery_event_id and not reference_id:
        return {"status": "ignored", "reason": "No identifiers found"}

    sb = get_supabase()

    if payment_id:
        already = None
        try:
            already = sb.table("recovery_events").select("id").eq(
                "recovered_payment_id", payment_id
            ).limit(1).execute()
        except Exception:
            pass
        if not already or not already.data:
            already = sb.table("recovery_events").select("id").eq(
                "payment_id", payment_id
            ).in_("status", ["recovered", "organic_recovery"]).limit(1).execute()
        if already and already.data:
            logger.warning(
                "Double-attribution blocked: payment_id=%s already attributed to event %d",
                payment_id, already.data[0]["id"],
            )
            return {"status": "duplicate_attribution", "reason": "Payment already attributed to a recovery",
                    "existing_event_id": already.data[0]["id"]}

    res = None
    match_method = None

    recoverable_statuses = ["pending", "paused", "exhausted"]

    if recovery_event_id:
        res = sb.table("recovery_events").select("*").eq("id", int(recovery_event_id)).in_("status", recoverable_statuses).limit(1).execute()
        if res and res.data:
            match_method = "notes.recovery_event_id"

    if (not res or not res.data) and reference_id:
        res = sb.table("recovery_events").select("*").eq("order_id", reference_id).in_("status", recoverable_statuses).limit(1).execute()
        if res and res.data:
            match_method = "reference_id"

    if (not res or not res.data) and order_id:
        res = sb.table("recovery_events").select("*").eq("order_id", order_id).in_("status", recoverable_statuses).limit(1).execute()
        if res and res.data:
            match_method = "order_id"

    if (not res or not res.data) and payment_id:
        res = sb.table("recovery_events").select("*").eq("payment_id", payment_id).in_("status", recoverable_statuses).limit(1).execute()
        if res and res.data:
            match_method = "payment_id"

    if not res or not res.data:
        logger.info("No recoverable event for order_id=%s, payment_id=%s", order_id, payment_id)
        return {"status": "no_match", "reason": "No recoverable event found"}

    event = res.data[0]

    event_currency = event.get("currency", "INR")
    if currency and event_currency and currency.upper() != event_currency.upper():
        logger.warning(
            "Reconciliation rejected: currency mismatch — captured %s vs event %s "
            "(event_id=%d, payment_id=%s)",
            currency, event_currency, event["id"], payment_id,
        )
        return {"status": "rejected", "reason": f"Currency mismatch: captured {currency} vs event {event_currency}",
                "event_id": event["id"]}

    event_amount = float(event.get("amount", 0) or 0)
    if event_amount > 0 and amount > 0:
        tolerance = max(event_amount * 0.01, 1.0)
        if abs(amount - event_amount) > tolerance:
            logger.warning(
                "Reconciliation rejected: amount mismatch — captured %.2f vs event %.2f "
                "(tolerance=%.2f, event_id=%d, payment_id=%s)",
                amount, event_amount, tolerance, event["id"], payment_id,
            )
            return {"status": "rejected",
                    "reason": f"Amount mismatch: captured {amount:.2f} vs event {event_amount:.2f}",
                    "event_id": event["id"]}

    logger.info(
        "Recovery tracker MATCHED: event_id=%d match_method=%s "
        "event_status=%s attempt_count=%d reconciliation=passed",
        event["id"], match_method, event.get("status"), event.get("attempt_count", 0),
    )

    now = datetime.now(timezone.utc)

    fresh = sb.table("recovery_events").select("attempt_count").eq("id", event["id"]).limit(1).execute()
    actual_attempt_count = (fresh.data[0]["attempt_count"] if fresh.data else event.get("attempt_count", 0)) or 0

    sent_attempts = sb.table("recovery_attempts").select("id").eq(
        "recovery_event_id", event["id"]
    ).eq("outcome", "sent").limit(1).execute()
    has_successful_outreach = bool(sent_attempts.data)

    is_organic = actual_attempt_count == 0 and not has_successful_outreach

    if is_organic:
        update_data = {
            "status": "organic_recovery",
            "recovered_at": now.isoformat(),
            "recovered_amount": amount,
            "next_action_at": None,
            "updated_at": now.isoformat(),
        }
        if payment_id:
            update_data["recovered_payment_id"] = payment_id
        upd = sb.table("recovery_events").update(update_data).eq("id", event["id"]).in_("status", recoverable_statuses).execute()

        if not upd.data:
            logger.warning("Event %d already processed (race avoided)", event["id"])
            return {"status": "already_processed", "event_id": event["id"]}

        logger.info("Organic recovery: event %d (0 successful outreach, matched via %s)", event["id"], match_method)
        return {"status": "organic_recovery", "event_id": event["id"]}

    update_data = {
        "status": "recovered",
        "recovered_at": now.isoformat(),
        "recovered_amount": amount,
        "next_action_at": None,
        "updated_at": now.isoformat(),
    }
    if payment_id:
        update_data["recovered_payment_id"] = payment_id
    upd = sb.table("recovery_events").update(update_data).eq("id", event["id"]).in_("status", recoverable_statuses).execute()

    if not upd.data:
        logger.warning("Event %d already processed (race avoided)", event["id"])
        return {"status": "already_processed", "event_id": event["id"]}

    logger.info(
        "RECOVERED: event %d after %d attempts (matched via %s, amount=%.2f)",
        event["id"], event["attempt_count"], match_method, amount,
    )
    return {
        "status": "recovered",
        "event_id": event["id"],
        "attempts_made": event["attempt_count"],
        "amount": amount,
        "match_method": match_method,
    }

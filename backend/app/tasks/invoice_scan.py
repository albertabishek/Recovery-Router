import logging
from app.celery_app import celery_app
from app.services.invoice_scanner import fetch_overdue_invoices
from app.tasks.recovery import process_recovery_event

logger = logging.getLogger(__name__)


@celery_app.task
def scan_overdue_invoices() -> dict:
    """Periodic task (every 6h via Beat): poll Razorpay for overdue invoices."""
    invoices = fetch_overdue_invoices()

    dispatched = 0
    for inv in invoices:
        process_recovery_event.delay(inv)
        dispatched += 1

    logger.info("Invoice scan: found %d, dispatched %d", len(invoices), dispatched)
    return {"scanned": len(invoices), "dispatched": dispatched}

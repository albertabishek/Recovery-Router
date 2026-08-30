from celery import Celery
from app.config import settings

celery_app = Celery(
    "recovery_router",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    broker_transport_options={"visibility_timeout": 3600},
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    beat_schedule={
        "escalation-every-5min": {
            "task": "app.tasks.escalation.run_escalation_cycle",
            "schedule": settings.ESCALATION_INTERVAL_SECONDS,
        },
        "invoice-scan-every-6h": {
            "task": "app.tasks.invoice_scan.scan_overdue_invoices",
            "schedule": settings.INVOICE_SCAN_INTERVAL_SECONDS,
        },
    },
    timezone="UTC",
)

celery_app.conf.update(
    include=["app.tasks.recovery", "app.tasks.escalation", "app.tasks.invoice_scan"],
)

from datetime import timedelta
from app.models import ClassificationResult, ActionPlan

TIMING_MAP = {
    "immediate": timedelta(seconds=0),
    "5_minutes": timedelta(minutes=5),
    "30_minutes": timedelta(minutes=30),
    "1_hour": timedelta(hours=1),
    "4_hours": timedelta(hours=4),
}


def compute_max_attempts(
    amount: float,
    recovery_probability: float,
    failure_category: str,
) -> int:
    """Dynamic max attempts based on amount, probability, and failure reason."""
    if failure_category == "unrecoverable_decline":
        return 1
    if failure_category == "browse_only_abandonment":
        return 1
    if failure_category == "user_cancelled":
        return 2
    if recovery_probability <= 0.1:
        return 1

    if recovery_probability >= 0.7 and amount >= 5000:
        return 5
    if recovery_probability >= 0.5 and amount >= 2000:
        return 4
    if recovery_probability >= 0.3 or amount >= 1000:
        return 3

    return 2


def route_action(classification: ClassificationResult) -> ActionPlan:
    """Deterministic routing based on classification output."""
    if classification.recommended_channel == "none":
        return ActionPlan(
            action="no_action",
            skip_reason=classification.skip_reason or "No recovery action recommended",
        )

    delay = TIMING_MAP.get(classification.recommended_timing, timedelta(seconds=0))
    delay_secs = int(delay.total_seconds())

    if delay_secs == 0:
        return ActionPlan(
            action="send_now",
            channel=classification.recommended_channel,
        )

    return ActionPlan(
        action="send_delayed",
        channel=classification.recommended_channel,
        delay_seconds=delay_secs,
    )

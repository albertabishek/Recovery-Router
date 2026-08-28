import logging
from datetime import datetime, timezone
from app.celery_app import celery_app
from app.database import get_supabase
from app.redis_client import get_redis
from app.services.escalation import run_escalation

logger = logging.getLogger(__name__)

LOCK_KEY = "lock:escalation"
LOCK_TTL = 240


@celery_app.task
def run_escalation_cycle() -> dict:
    """Periodic task (every 5 min via Beat): fetch due events, escalate."""
    r = get_redis()

    if not r.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL):
        logger.info("Escalation cycle skipped — another run is in progress")
        return {"status": "skipped", "reason": "locked"}

    try:
        sb = get_supabase()
        now = datetime.now(timezone.utc).isoformat()

        res = (
            sb.table("recovery_events")
            .select("*")
            .eq("status", "pending")
            .lte("next_action_at", now)
            .order("recovery_probability", desc=True)
            .order("next_action_at", desc=False)
            .limit(50)
            .execute()
        )

        events = res.data or []
        if not events:
            return {"status": "idle", "processed": 0}

        actionable = []
        for e in events:
            if e.get("opted_out"):
                continue
            if e.get("recovery_window_ends"):
                try:
                    window_end = datetime.fromisoformat(e["recovery_window_ends"])
                    if window_end <= datetime.now(timezone.utc):
                        _mark_window_expired(sb, e)
                        continue
                except (ValueError, TypeError):
                    pass
            if (e.get("attempt_count", 0) or 0) >= (e.get("max_attempts", 5) or 5):
                continue
            if e.get("failure_category") == "unrecoverable_decline":
                continue
            if (e.get("recovery_probability") or 0) == 0:
                continue
            actionable.append(e)

        if not actionable:
            return {"status": "idle", "filtered_out": len(events), "processed": 0}

        results = run_escalation(actionable)

        logger.info(f"Escalation cycle: {len(actionable)} events processed")
        return {"status": "done", "processed": len(results), "results": results}

    finally:
        r.delete(LOCK_KEY)


def _mark_window_expired(sb, event):
    sb.table("recovery_events").update({
        "status": "exhausted",
        "current_strategy": "window_expired",
        "skip_reason": "72-hour recovery window expired without payment",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", event["id"]).execute()

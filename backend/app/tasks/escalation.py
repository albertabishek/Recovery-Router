import logging
from datetime import datetime, timedelta, timezone
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
            if (e.get("attempt_count", 0) or 0) >= (e.get("max_attempts") if e.get("max_attempts") is not None else 5):
                _mark_attempts_exhausted(sb, e)
                continue
            if e.get("failure_category") == "unrecoverable_decline":
                continue
            if (e.get("recovery_probability") or 0) == 0:
                continue
            actionable.append(e)

        if not actionable:
            return {"status": "idle", "filtered_out": len(events), "processed": 0}

        results = run_escalation(actionable)

        logger.info("Escalation cycle: %d events processed", len(actionable))
        return {"status": "done", "processed": len(results), "results": results}

    finally:
        r.delete(LOCK_KEY)


def _mark_window_expired(sb, event):
    attempt_count = event.get("attempt_count", 0) or 0
    max_attempts = event.get("max_attempts") if event.get("max_attempts") is not None else 5

    if attempt_count == 0 and max_attempts > 0:
        now = datetime.now(timezone.utc)
        sb.table("recovery_events").update({
            "status": "pending",
            "current_strategy": "retry_after_window",
            "skip_reason": None,
            "recovery_window_ends": (now + timedelta(hours=24)).isoformat(),
            "next_action_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }).eq("id", event["id"]).eq("status", "pending").execute()
        logger.info("Event %d: window expired but 0 attempts sent — extending window by 24h", event["id"])
        return

    res = sb.table("recovery_events").update({
        "status": "exhausted",
        "current_strategy": "window_expired",
        "skip_reason": "Recovery window expired without payment" if attempt_count > 0 else "No outreach attempts succeeded within recovery window",
        "next_action_at": None,
        "recovery_window_ends": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", event["id"]).eq("status", "pending").execute()
    if res.data:
        logger.info("Event %d: recovery window expired (attempts=%d)", event["id"], attempt_count)
    else:
        logger.warning("Event %d: window expiry skipped — status already changed", event["id"])


def _mark_attempts_exhausted(sb, event):
    max_att = event.get("max_attempts") if event.get("max_attempts") is not None else 5
    attempt_count = event.get("attempt_count", 0) or 0

    if attempt_count == 0 and max_att > 0:
        logger.info("Event %d: max_attempts=%d but attempt_count=0 — skipping exhaustion", event["id"], max_att)
        return

    res = sb.table("recovery_events").update({
        "status": "exhausted",
        "current_strategy": "max_attempts_reached",
        "skip_reason": f"Reached maximum {max_att} recovery attempts",
        "next_action_at": None,
        "recovery_window_ends": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", event["id"]).eq("status", "pending").execute()
    if res.data:
        logger.info("Event %d: max attempts (%d) exhausted", event["id"], max_att)
    else:
        logger.warning("Event %d: exhaustion skipped — status already changed", event["id"])

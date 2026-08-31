import json
import logging
from datetime import datetime, timezone
from app.database import get_supabase
from app.redis_client import get_redis
from app.models import AnalyticsResponse, AnalyticsSummary, AILift

logger = logging.getLogger(__name__)

CACHE_KEY = "cache:analytics"
CACHE_TTL = 120
BASELINE_RATE = 15.0


def compute_analytics(from_date: str | None = None, to_date: str | None = None) -> AnalyticsResponse:
    """Compute aggregate analytics. Cached in Redis for 30s."""
    r = get_redis()
    cache_key = CACHE_KEY
    if from_date or to_date:
        cache_key = f"{CACHE_KEY}:{from_date or ''}:{to_date or ''}"

    cached = r.get(cache_key)
    if cached:
        return AnalyticsResponse(**json.loads(cached))

    sb = get_supabase()
    events = []
    page_size = 1000
    offset = 0
    while True:
        query = sb.table("recovery_events").select(
            "id,event_type,status,amount,recovered_amount,attempt_count,"
            "recommended_channel,failure_category,created_at,recovered_at"
        )
        if from_date:
            query = query.gte("created_at", f"{from_date}T00:00:00")
        if to_date:
            query = query.lte("created_at", f"{to_date}T23:59:59")
        query = query.order("id").range(offset, offset + page_size - 1)
        res = query.execute()
        batch = res.data or []
        events.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    if not events:
        return AnalyticsResponse(
            summary=AnalyticsSummary(),
            ai_lift=AILift(),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    total = len(events)
    recovered = [e for e in events if e.get("status") == "recovered"]
    pending = [e for e in events if e.get("status") == "pending"]
    exhausted = [e for e in events if e.get("status") == "exhausted"]
    no_action = [e for e in events if e.get("status") == "no_action_needed"]
    organic = [e for e in events if e.get("status") == "organic_recovery"]

    total_amount = sum(float(e.get("amount", 0) or 0) for e in events)
    recovered_amount = sum(float(e.get("recovered_amount") or e.get("amount", 0) or 0) for e in recovered)
    pending_amount = sum(float(e.get("amount", 0) or 0) for e in pending)

    ai_recovery_count = len(recovered)
    recovery_rate = (ai_recovery_count / total * 100) if total > 0 else 0

    avg_attempts = 0.0
    if recovered:
        avg_attempts = sum(e.get("attempt_count", 0) for e in recovered) / len(recovered)

    avg_recovery_hours = 0.0
    recovery_times = []
    for e in recovered:
        created = e.get("created_at")
        rec_at = e.get("recovered_at")
        if created and rec_at:
            try:
                t1 = datetime.fromisoformat(created)
                t2 = datetime.fromisoformat(rec_at)
                hours = (t2 - t1).total_seconds() / 3600
                recovery_times.append(hours)
            except (ValueError, TypeError):
                pass
    if recovery_times:
        avg_recovery_hours = sum(recovery_times) / len(recovery_times)

    summary = AnalyticsSummary(
        total_events=total,
        recovered_count=len(recovered),
        pending_count=len(pending),
        exhausted_count=len(exhausted),
        no_action_count=len(no_action) + len(organic),
        recovery_rate_percent=round(recovery_rate, 1),
        total_amount=total_amount,
        recovered_amount=recovered_amount,
        pending_amount=pending_amount,
        avg_attempts_to_recover=round(avg_attempts, 1),
        avg_recovery_time_hours=round(avg_recovery_hours, 1),
    )

    baseline_recovered = total_amount * (BASELINE_RATE / 100)
    improvement = recovery_rate - BASELINE_RATE
    lift_mult = (recovery_rate / BASELINE_RATE) if BASELINE_RATE > 0 else 0
    additional = recovered_amount - baseline_recovered

    ai_lift = AILift(
        baseline_rate_percent=BASELINE_RATE,
        baseline_source="Industry reference: ~15% organic recovery via simple retries (Razorpay blog, observational — not a controlled baseline)",
        ai_recovery_rate_percent=round(recovery_rate, 1),
        improvement_points=round(improvement, 1),
        lift_multiplier=round(lift_mult, 2),
        additional_revenue_recovered=round(max(0, additional), 2),
    )

    by_event_type = _group_by(events, "event_type")
    by_channel = _group_by_channel(events)
    by_failure_category = _group_by(events, "failure_category")

    channel_ranking = sorted(
        by_channel.items(),
        key=lambda x: x[1].get("recovery_rate", 0),
        reverse=True,
    )
    channel_ranking = [{"channel": k, **v} for k, v in channel_ranking]

    result = AnalyticsResponse(
        summary=summary,
        ai_lift=ai_lift,
        by_event_type=by_event_type,
        by_channel=by_channel,
        channel_ranking=channel_ranking,
        by_failure_category=by_failure_category,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        r.set(cache_key, json.dumps(result.model_dump()), ex=CACHE_TTL)
    except Exception:
        pass

    return result


def _group_by(events: list, field: str) -> dict:
    groups = {}
    for e in events:
        key = e.get(field) or "unknown"
        if key not in groups:
            groups[key] = {"total": 0, "recovered": 0, "amount": 0, "recovered_amount": 0}
        groups[key]["total"] += 1
        groups[key]["amount"] += float(e.get("amount", 0) or 0)
        if e.get("status") == "recovered":
            groups[key]["recovered"] += 1
            groups[key]["recovered_amount"] += float(e.get("recovered_amount") or e.get("amount", 0) or 0)

    for key in groups:
        g = groups[key]
        g["recovery_rate"] = round((g["recovered"] / g["total"] * 100) if g["total"] > 0 else 0, 1)

    return groups


def _group_by_channel(events: list) -> dict:
    groups = {}
    for e in events:
        channel = e.get("recommended_channel") or "unknown"
        if channel not in groups:
            groups[channel] = {"total": 0, "recovered": 0, "amount": 0}
        groups[channel]["total"] += 1
        groups[channel]["amount"] += float(e.get("amount", 0) or 0)
        if e.get("status") == "recovered":
            groups[channel]["recovered"] += 1

    for key in groups:
        g = groups[key]
        g["recovery_rate"] = round((g["recovered"] / g["total"] * 100) if g["total"] > 0 else 0, 1)

    return groups

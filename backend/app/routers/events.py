import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from app.config import settings
from app.auth import require_auth
from app.models import SimulateRequest, WebhookResponse
from app.database import get_supabase
from app.tasks.recovery import process_recovery_event
from app.utils.rate_limiter import check_rate_limit
from app.services.payment_links import generate_payment_link

router = APIRouter(prefix="/api", tags=["events"], dependencies=[Depends(require_auth)])

def build_scenarios() -> dict:
    """Build scenario payloads. Called per request so amounts vary each time."""
    return {
        "upi_timeout": {
            "event_type": "payment_failure",
            "method": "upi",
            "error_code": "TIMEOUT",
            "error_description": "UPI payment timed out after 5 minutes",
            "amount": random.choice([499, 999, 1499, 2999, 4999]),
        },
        "card_expired": {
            "event_type": "payment_failure",
            "method": "card",
            "error_code": "CARD_EXPIRED",
            "error_description": "Card has expired",
            "amount": random.choice([1999, 3499, 5999, 8999]),
        },
        "insufficient_funds": {
            "event_type": "payment_failure",
            "method": "card",
            "error_code": "INSUFFICIENT_FUNDS",
            "error_description": "Insufficient funds in account",
            "amount": random.choice([2499, 4999, 7999, 12999]),
        },
        "bank_downtime": {
            "event_type": "payment_failure",
            "method": "netbanking",
            "error_code": "BANK_DOWNTIME",
            "error_description": "Bank server is temporarily unavailable",
            "amount": random.choice([999, 2499, 4999]),
        },
        "gateway_error": {
            "event_type": "payment_failure",
            "method": "upi",
            "error_code": "GATEWAY_ERROR",
            "error_description": "Payment gateway technical error",
            "amount": random.choice([799, 1599, 3999]),
        },
        "fraud_decline": {
            "event_type": "payment_failure",
            "method": "card",
            "error_code": "FRAUD_SUSPECTED",
            "error_description": "Transaction flagged as potentially fraudulent",
            "amount": random.choice([9999, 14999, 24999]),
        },
        "high_value_cart": {
            "event_type": "cart_abandonment",
            "cart_value": random.choice([2999, 5999, 9999, 14999]),
            "items_in_cart": random.randint(2, 8),
            "amount": 0,
        },
        "low_value_cart": {
            "event_type": "cart_abandonment",
            "cart_value": random.choice([99, 149, 199]),
            "items_in_cart": 1,
            "amount": 0,
        },
        "recent_invoice": {
            "event_type": "invoice_overdue",
            "days_overdue": random.randint(1, 7),
            "amount": random.choice([5000, 10000, 25000, 50000]),
        },
        "old_invoice": {
            "event_type": "invoice_overdue",
            "days_overdue": random.randint(31, 90),
            "amount": random.choice([15000, 30000, 75000]),
        },
    }


@router.get("/events")
async def list_events(
    status: str | None = Query(None),
    event_type: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List recovery events with optional filters."""
    if not check_rate_limit("api:events", max_requests=60, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    sb = get_supabase()
    query = sb.table("recovery_events").select("*", count="exact")

    if status:
        query = query.eq("status", status)
    if event_type:
        query = query.eq("event_type", event_type)
    if from_date:
        query = query.gte("created_at", f"{from_date}T00:00:00")
    if to_date:
        query = query.lte("created_at", f"{to_date}T23:59:59")

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    res = query.execute()

    return {
        "events": res.data or [],
        "total": res.count,
        "limit": limit,
        "offset": offset,
    }


@router.post("/simulate", response_model=WebhookResponse)
async def simulate_event(req: SimulateRequest):
    """Generate a test recovery event — always async via Celery."""
    if not check_rate_limit("api:simulate", max_requests=10, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    scenarios = build_scenarios()
    scenario = scenarios.get(req.scenario)
    if not scenario:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}. Available: {list(scenarios.keys())}")

    event_data = {
        **scenario,
        "event_type": scenario.get("event_type", req.event_type),
        "currency": "INR",
        "customer_email": req.customer_email or settings.TEST_CUSTOMER_EMAIL,
        "customer_phone": req.customer_phone or settings.TEST_CUSTOMER_PHONE,
        "customer_name": req.customer_name or "Test Customer",
        "payment_id": f"pay_TEST_{random.randint(10000, 99999)}",
        "order_id": f"order_TEST_{random.randint(10000, 99999)}",
        "source": "simulator",
    }

    if scenario.get("cart_value"):
        event_data["amount"] = scenario["cart_value"]

    process_recovery_event.delay(event_data)
    return WebhookResponse(status="accepted", message=f"Simulated {req.scenario} event queued for async processing")


@router.get("/events/counts")
async def event_counts(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
):
    """Get event counts by status in a single query."""
    if not check_rate_limit("api:events-counts", max_requests=60, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    sb = get_supabase()
    query = sb.table("recovery_events").select("status", count="exact")
    if from_date:
        query = query.gte("created_at", f"{from_date}T00:00:00")
    if to_date:
        query = query.lte("created_at", f"{to_date}T23:59:59")
    res = query.execute()
    events = res.data or []
    counts = {"all": len(events)}
    for e in events:
        s = e.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts


@router.get("/audit-logs")
async def list_audit_logs(
    event_id: int | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Fetch recovery attempts with full degradation path for audit trail."""
    if not check_rate_limit("api:audit-logs", max_requests=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    sb = get_supabase()
    query = sb.table("recovery_attempts").select("*", count="exact")

    if event_id:
        query = query.eq("recovery_event_id", event_id)
    if from_date:
        query = query.gte("created_at", f"{from_date}T00:00:00")
    if to_date:
        query = query.lte("created_at", f"{to_date}T23:59:59")

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    res = query.execute()

    return {
        "logs": res.data or [],
        "total": res.count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/events/{event_id}/trace")
async def event_trace(event_id: int):
    """Full trace for a single event: event data + all attempts + structured timeline."""
    sb = get_supabase()

    ev_res = sb.table("recovery_events").select("*").eq("id", event_id).limit(1).execute()
    if not ev_res.data:
        raise HTTPException(status_code=404, detail="Event not found")

    event = ev_res.data[0]

    attempts_res = sb.table("recovery_attempts").select("*").eq(
        "recovery_event_id", event_id
    ).order("attempt_number").execute()
    attempts = attempts_res.data or []

    timeline = _build_trace_timeline(event, attempts)

    return {
        "event": event,
        "attempts": attempts,
        "timeline": timeline,
    }


def _build_trace_timeline(event: dict, attempts: list[dict]) -> list[dict]:
    steps = []

    steps.append({
        "step": "event_received",
        "timestamp": event.get("created_at"),
        "detail": {
            "type": event.get("event_type"),
            "amount": event.get("amount"),
            "currency": event.get("currency", "INR"),
            "source": event.get("source"),
        },
    })

    if event.get("failure_category"):
        steps.append({
            "step": "classified",
            "timestamp": event.get("created_at"),
            "detail": {
                "category": event.get("failure_category"),
                "probability": event.get("recovery_probability"),
                "recommended_channel": event.get("recommended_channel"),
                "max_attempts": event.get("max_attempts"),
                "urgency": event.get("urgency"),
            },
        })

    for att in attempts:
        meta = att.get("metadata") or {}

        if meta.get("payment_link_url"):
            steps.append({
                "step": "payment_link_created",
                "timestamp": att.get("created_at"),
                "detail": {
                    "link_id": meta.get("payment_link_id"),
                    "url": meta.get("payment_link_url"),
                },
            })

        steps.append({
            "step": "outreach_attempt",
            "timestamp": att.get("created_at"),
            "detail": {
                "attempt_number": att.get("attempt_number"),
                "channel": att.get("channel_used"),
                "outcome": att.get("outcome"),
                "action": att.get("action_taken"),
                "reasoning": att.get("notes"),
                "degraded_from": meta.get("degraded_from"),
                "degradation_path": meta.get("degradation_path"),
                "error": meta.get("send_error"),
            },
        })

    status = event.get("status", "pending")
    if status in ("recovered", "organic_recovery"):
        steps.append({
            "step": "recovered",
            "timestamp": event.get("updated_at"),
            "detail": {
                "status": status,
                "payment_id": event.get("payment_id"),
            },
        })
    elif status == "exhausted":
        steps.append({
            "step": "exhausted",
            "timestamp": event.get("updated_at"),
            "detail": {
                "reason": event.get("skip_reason"),
                "strategy": event.get("current_strategy"),
                "attempts_made": event.get("attempt_count"),
            },
        })
    elif status == "cancelled":
        steps.append({
            "step": "cancelled",
            "timestamp": event.get("updated_at"),
            "detail": {
                "reason": event.get("skip_reason"),
            },
        })
    elif status == "pending" and event.get("next_action_at"):
        steps.append({
            "step": "next_action_scheduled",
            "timestamp": event.get("updated_at"),
            "detail": {
                "next_action_at": event.get("next_action_at"),
                "strategy": event.get("current_strategy"),
            },
        })

    return steps


class LiveCheckoutRequest(BaseModel):
    amount: float = 499
    customer_name: str = "Test Customer"
    customer_email: str = ""
    customer_phone: str = ""


@router.post("/live-checkout")
async def create_live_checkout(req: LiveCheckoutRequest):
    """Create a Razorpay test-mode order for live payment testing."""
    if not check_rate_limit("api:live-checkout", max_requests=5, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if req.amount < 1 or req.amount > 50000:
        raise HTTPException(status_code=400, detail="Amount must be between ₹1 and ₹50,000")

    import httpx
    amount_paise = int(req.amount * 100)

    try:
        resp = httpx.post(
            "https://api.razorpay.com/v1/orders",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json={
                "amount": amount_paise,
                "currency": "INR",
                "notes": {
                    "source": "recovery_router_simulator",
                    "test_mode": "true",
                    "customer_name": req.customer_name,
                    "customer_email": req.customer_email,
                    "customer_phone": req.customer_phone,
                },
            },
            timeout=10,
        )

        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Razorpay order creation failed: {resp.status_code}")

        order = resp.json()

        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "razorpay_key": settings.RAZORPAY_KEY_ID,
        }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Razorpay API error: {str(e)}")


class EventControlRequest(BaseModel):
    action: str


@router.patch("/events/{event_id}/control")
async def control_event(event_id: int, req: EventControlRequest):
    """Pause or resume recovery for a specific event."""
    sb = get_supabase()

    ev_res = sb.table("recovery_events").select("id,status").eq("id", event_id).limit(1).execute()
    if not ev_res.data:
        raise HTTPException(status_code=404, detail="Event not found")

    event = ev_res.data[0]
    current_status = event["status"]

    if req.action == "pause":
        if current_status != "pending":
            raise HTTPException(status_code=400, detail=f"Can only pause pending events (current: {current_status})")
        sb.table("recovery_events").update({
            "status": "paused",
            "current_strategy": "merchant_paused",
            "next_action_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", event_id).execute()
        return {"status": "paused", "message": f"Event #{event_id} recovery paused"}

    elif req.action == "resume":
        if current_status != "paused":
            raise HTTPException(status_code=400, detail=f"Can only resume paused events (current: {current_status})")
        sb.table("recovery_events").update({
            "status": "pending",
            "current_strategy": "resumed",
            "next_action_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", event_id).execute()
        return {"status": "resumed", "message": f"Event #{event_id} recovery resumed"}

    elif req.action == "cancel":
        terminal = ("recovered", "organic_recovery", "cancelled")
        if current_status in terminal:
            raise HTTPException(status_code=400, detail=f"Cannot cancel event in terminal status '{current_status}'")
        sb.table("recovery_events").update({
            "status": "cancelled",
            "current_strategy": "merchant_cancelled",
            "skip_reason": "Cancelled by merchant",
            "next_action_at": None,
            "recovery_window_ends": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", event_id).execute()
        return {"status": "cancelled", "message": f"Event #{event_id} recovery cancelled"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}. Use 'pause', 'resume', or 'cancel'")


@router.post("/migrate/fix-exhausted")
async def fix_exhausted_events():
    """One-time migration: backfill skip_reason and clear stale fields on old exhausted events."""
    sb = get_supabase()
    fixed = 0
    batch_size = 50
    offset = 0

    while True:
        res = (
            sb.table("recovery_events")
            .select("id,status,skip_reason,next_action_at,recovery_window_ends,attempt_count,max_attempts,current_strategy")
            .eq("status", "exhausted")
            .range(offset, offset + batch_size - 1)
            .execute()
        )

        if not res.data:
            break

        for event in res.data:
            update = {}
            needs_update = False

            if event.get("skip_reason") is None:
                max_att = event.get("max_attempts") if event.get("max_attempts") is not None else 5
                strategy = event.get("current_strategy", "")
                if strategy == "window_expired":
                    update["skip_reason"] = "72-hour recovery window expired without payment"
                else:
                    update["skip_reason"] = f"All {max_att} recovery attempts used without successful payment"
                needs_update = True

            if event.get("next_action_at") is not None:
                update["next_action_at"] = None
                needs_update = True

            if event.get("recovery_window_ends") is not None:
                update["recovery_window_ends"] = None
                needs_update = True

            if needs_update:
                update["updated_at"] = datetime.now(timezone.utc).isoformat()
                sb.table("recovery_events").update(update).eq("id", event["id"]).execute()
                fixed += 1

        if len(res.data) < batch_size:
            break
        offset += batch_size

    return {"status": "done", "fixed": fixed}


@router.post("/migrate/fix-premature-exhaustion")
async def fix_premature_exhaustion():
    """Fix events exhausted prematurely due to cooldown failures being counted as real failures."""
    sb = get_supabase()
    fixed_events = 0
    fixed_attempts = 0

    res = (
        sb.table("recovery_events")
        .select("id,status,attempt_count,max_attempts,current_strategy")
        .eq("status", "exhausted")
        .execute()
    )

    for event in (res.data or []):
        ac = event.get("attempt_count") or 0
        ma = event.get("max_attempts") if event.get("max_attempts") is not None else 5
        if ac >= ma:
            continue

        atts = (
            sb.table("recovery_attempts")
            .select("id,channel_used,outcome,metadata")
            .eq("recovery_event_id", event["id"])
            .execute()
        )

        for a in (atts.data or []):
            if a.get("channel_used") == "payment_link":
                continue
            meta = a.get("metadata") or {}
            if a.get("outcome") == "failed" and meta.get("send_error") == "Cooldown active":
                sb.table("recovery_attempts").update({"outcome": "blocked"}).eq("id", a["id"]).execute()
                fixed_attempts += 1

        has_successful = any(a.get("outcome") == "sent" for a in (atts.data or []) if a.get("channel_used") != "payment_link")
        now = datetime.now(timezone.utc)

        if has_successful:
            sb.table("recovery_events").update({
                "status": "pending",
                "current_strategy": "first_contact_sent",
                "skip_reason": None,
                "updated_at": now.isoformat(),
            }).eq("id", event["id"]).execute()
        else:
            sb.table("recovery_events").update({
                "status": "pending",
                "attempt_count": 0,
                "current_strategy": "first_contact_failed",
                "skip_reason": None,
                "next_action_at": (now + timedelta(minutes=15)).isoformat(),
                "updated_at": now.isoformat(),
            }).eq("id", event["id"]).execute()
        fixed_events += 1

    return {"status": "done", "fixed_events": fixed_events, "fixed_attempts": fixed_attempts}


@router.post("/debug/escalate/{event_id}")
async def debug_escalate_event(event_id: int):
    """Debug: manually trigger escalation for a single event and return full trace."""
    from app.services.escalation import run_escalation
    sb = get_supabase()
    ev = sb.table("recovery_events").select("*").eq("id", event_id).limit(1).execute()
    if not ev.data:
        raise HTTPException(status_code=404, detail="Event not found")
    event = ev.data[0]
    if event["status"] != "pending":
        return {"error": f"Event status is '{event['status']}', not 'pending'", "event": event}
    results = run_escalation([event])
    ev_after = sb.table("recovery_events").select("*").eq("id", event_id).limit(1).execute()
    atts = sb.table("recovery_attempts").select("*").eq("recovery_event_id", event_id).order("id", desc=False).execute()
    return {
        "escalation_result": results,
        "event_before": event,
        "event_after": ev_after.data[0] if ev_after.data else None,
        "attempts": atts.data,
    }


@router.post("/debug/test-update/{event_id}")
async def debug_test_update(event_id: int):
    """Debug: test if Supabase updates persist."""
    import time as _time
    sb = get_supabase()
    before = sb.table("recovery_events").select("id,status,updated_at").eq("id", event_id).limit(1).execute()
    now = datetime.now(timezone.utc)
    upd = sb.table("recovery_events").update({
        "status": "pending",
        "current_strategy": "debug_test",
        "skip_reason": None,
        "updated_at": now.isoformat(),
    }).eq("id", event_id).execute()
    read1 = sb.table("recovery_events").select("id,status").eq("id", event_id).limit(1).execute()
    _time.sleep(0.5)
    read2 = sb.table("recovery_events").select("id,status").eq("id", event_id).limit(1).execute()
    _time.sleep(2)
    read3 = sb.table("recovery_events").select("id,status").eq("id", event_id).limit(1).execute()
    return {
        "before": before.data[0] if before.data else None,
        "update_returned_status": upd.data[0]["status"] if upd.data else None,
        "read_0ms": read1.data[0]["status"] if read1.data else None,
        "read_500ms": read2.data[0]["status"] if read2.data else None,
        "read_2500ms": read3.data[0]["status"] if read3.data else None,
    }


@router.delete("/reset/all-data")
async def reset_all_data(confirm: str = Query(None)):
    """Delete all recovery data and reset ID sequences to start from 1."""
    if confirm != "yes-delete-everything":
        raise HTTPException(
            status_code=400,
            detail="Pass ?confirm=yes-delete-everything to confirm data deletion",
        )
    sb = get_supabase()

    atts = sb.table("recovery_attempts").select("id", count="exact").execute()
    evts = sb.table("recovery_events").select("id", count="exact").execute()
    att_count = atts.count or 0
    evt_count = evts.count or 0

    sb.table("recovery_attempts").delete().gte("id", 0).execute()
    sb.table("recovery_events").delete().gte("id", 0).execute()

    sb.rpc("reset_sequences", {}).execute()

    return {
        "status": "done",
        "deleted_attempts": att_count,
        "deleted_events": evt_count,
        "sequences_reset": True,
    }

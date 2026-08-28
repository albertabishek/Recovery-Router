import random
from fastapi import APIRouter, HTTPException, Query
from app.config import settings
from app.models import SimulateRequest, WebhookResponse
from app.database import get_supabase
from app.tasks.recovery import process_recovery_event
from app.utils.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api", tags=["events"])

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


@router.get("/audit-logs")
async def list_audit_logs(
    event_id: int | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Fetch recovery attempts with full degradation path for audit trail."""
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
    """Full trace for a single event: event data + all attempts + degradation paths."""
    sb = get_supabase()

    ev_res = sb.table("recovery_events").select("*").eq("id", event_id).limit(1).execute()
    if not ev_res.data:
        raise HTTPException(status_code=404, detail="Event not found")

    attempts_res = sb.table("recovery_attempts").select("*").eq(
        "recovery_event_id", event_id
    ).order("attempt_number").execute()

    return {
        "event": ev_res.data[0],
        "attempts": attempts_res.data or [],
    }

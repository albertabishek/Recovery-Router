import time
import httpx
import pytest

BASE = "http://localhost:8000"
API = f"{BASE}/api"

EMAILS = [
    "include1iostream2@gmail.com",
    "albertabishek369@gmail.com",
    "study1only2@gmail.com",
]
PHONES = ["+919042824369", "+918940715740"]

SCENARIOS = [
    ("payment_failure", "upi_timeout"),
    ("payment_failure", "card_expired"),
    ("payment_failure", "insufficient_funds"),
    ("payment_failure", "bank_downtime"),
    ("payment_failure", "gateway_error"),
    ("payment_failure", "fraud_decline"),
    ("cart_abandonment", "high_value_cart"),
    ("cart_abandonment", "low_value_cart"),
    ("invoice_overdue", "recent_invoice"),
    ("invoice_overdue", "old_invoice"),
]

EXPECTED = {
    "upi_timeout":        {"category": "upi_timeout",               "channel_in": ["whatsapp"],         "status": "pending",          "max_attempts_range": (2, 5), "prob_range": (0.6, 1.0)},
    "card_expired":       {"category": "card_expired",              "channel_in": ["email", "whatsapp"],"status": "pending",          "max_attempts_range": (2, 5), "prob_range": (0.3, 0.8)},
    "insufficient_funds": {"category": "insufficient_funds",        "channel_in": ["sms", "email", "whatsapp"], "status": "pending",  "max_attempts_range": (2, 5), "prob_range": (0.2, 0.85)},
    "bank_downtime":      {"category": "bank_downtime",             "channel_in": ["whatsapp", "sms"],  "status": "pending",          "max_attempts_range": (2, 5), "prob_range": (0.5, 1.0)},
    "gateway_error":      {"category": "gateway_error",             "channel_in": ["whatsapp", "sms"],  "status": "pending",          "max_attempts_range": (2, 5), "prob_range": (0.6, 1.0)},
    "fraud_decline":      {"category": "unrecoverable_decline",     "channel_in": ["none"],             "status": "no_action_needed", "max_attempts_range": (0, 0), "prob_range": (0.0, 0.1)},
    "high_value_cart":    {"category": ["high_intent_abandonment", "browse_only_abandonment"], "channel_in": ["whatsapp", "email", "none"], "status": ["pending", "no_action_needed"], "max_attempts_range": (0, 5), "prob_range": (0.0, 0.8)},
    "low_value_cart":     {"category": "browse_only_abandonment",   "channel_in": ["none"],             "status": "no_action_needed", "max_attempts_range": (0, 0), "prob_range": (0.0, 0.15)},
    "recent_invoice":     {"category": "recently_overdue",          "channel_in": ["whatsapp", "email"],"status": "pending",          "max_attempts_range": (2, 5), "prob_range": (0.4, 1.0)},
    "old_invoice":        {"category": "long_overdue",              "channel_in": ["email"],            "status": "pending",          "max_attempts_range": (1, 5), "prob_range": (0.05, 0.4)},
}


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE, timeout=30) as c:
        yield c


@pytest.fixture(scope="session")
def api(client):
    return client


def wait_for_celery(client, event_id, target_statuses=("pending", "no_action_needed", "exhausted", "recovered"), max_wait=45):
    """Poll until the event reaches one of the target statuses and has been processed."""
    for _ in range(max_wait):
        try:
            r = client.get(f"/api/events/{event_id}/trace")
            if r.status_code == 200:
                ev = r.json()["event"]
                status = ev.get("status")
                has_classification = bool(ev.get("failure_category"))
                if has_classification and status in target_statuses:
                    if status == "no_action_needed":
                        return ev
                    if status == "pending" and (ev.get("attempt_count", 0) > 0 or ev.get("recommended_timing") != "immediate"):
                        return ev
                    if status in ("exhausted", "recovered"):
                        return ev
        except Exception:
            pass
        time.sleep(1)
    r = client.get(f"/api/events/{event_id}/trace")
    return r.json()["event"] if r.status_code == 200 else None


def simulate_and_wait(client, event_type, scenario, customer=None, max_wait=60):
    """Fire a simulation and wait for it to be processed. Returns (event_id, event_data)."""
    before = client.get("/api/events", params={"limit": 1}).json().get("events", [])
    before_id = before[0]["id"] if before else 0

    body = {"event_type": event_type, "scenario": scenario}
    if customer:
        body.update(customer)
    for attempt in range(5):
        r = client.post("/api/simulate", json=body)
        if r.status_code == 429:
            time.sleep(3 * (attempt + 1))
            continue
        break
    assert r.status_code == 200, f"Simulate failed: {r.status_code} {r.text}"

    expected = EXPECTED.get(scenario, {})
    expected_category = expected.get("category")
    expected_cats = expected_category if isinstance(expected_category, list) else [expected_category] if expected_category else []

    new_events = []
    for _ in range(max_wait):
        time.sleep(1)
        try:
            events_r = client.get("/api/events", params={"limit": 10})
            events = events_r.json().get("events", [])
        except Exception:
            continue
        new_events = [e for e in events if e["id"] > before_id]
        for ev in new_events:
            if ev.get("failure_category") in expected_cats:
                event_id = ev["id"]
                final = wait_for_celery(client, event_id, max_wait=max_wait)
                return event_id, final
        if new_events and not expected_cats:
            event_id = new_events[0]["id"]
            final = wait_for_celery(client, event_id, max_wait=max_wait)
            return event_id, final

    if new_events:
        event_id = new_events[0]["id"]
        final = wait_for_celery(client, event_id, max_wait=10)
        return event_id, final

    pytest.fail(f"No new event created after simulating {scenario}")

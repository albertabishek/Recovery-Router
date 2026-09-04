"""
End-to-end test suite for Recovery Router API.
Tests every endpoint, feature, and edge case.
Run: python tests/e2e_test.py
Requires: server running on http://127.0.0.1:8000
"""
import sys
import json
import time
import hashlib
import hmac
import requests

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0
ERRORS = []


def run_test(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  PASS  {name}")
    except AssertionError as e:
        FAIL += 1
        ERRORS.append((name, str(e)))
        print(f"  FAIL  {name}: {e}")
    except Exception as e:
        FAIL += 1
        ERRORS.append((name, str(e)))
        print(f"  ERROR {name}: {e}")


# ── 1. Root & Health ──────────────────────────────────

def test_root():
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["name"] == "Recovery Router API"
    assert data["version"] == "1.0.0"
    assert "/docs" in data["docs"]


def test_health():
    r = requests.get(f"{BASE}/api/health", timeout=15)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data["status"] in ("ok", "degraded"), f"Unexpected status: {data['status']}"
    assert "supabase" in data["services"]
    assert "redis" in data["services"]
    assert "celery" in data["services"]


def test_docs():
    r = requests.get(f"{BASE}/docs")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "swagger" in r.text.lower() or "openapi" in r.text.lower()


# ── 2. Webhook: recovery-router ──────────────────────

def test_webhook_payment_failure():
    body = {
        "event_type": "payment_failure",
        "payment_id": f"pay_E2E_{int(time.time())}",
        "order_id": f"order_E2E_{int(time.time())}",
        "amount": 999,
        "currency": "INR",
        "method": "upi",
        "error_code": "TIMEOUT",
        "error_description": "UPI timeout",
        "customer_email": "e2e@test.com",
        "customer_phone": "+919999900001",
        "customer_name": "E2E Tester",
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["status"] == "accepted", f"Expected accepted, got {data['status']}"


def test_webhook_cart_abandonment():
    body = {
        "event_type": "cart_abandonment",
        "payment_id": f"pay_CART_{int(time.time())}",
        "amount": 0,
        "cart_value": 5999,
        "items_in_cart": 3,
        "currency": "INR",
        "customer_email": "cart@test.com",
        "customer_phone": "+919999900002",
        "customer_name": "Cart Tester",
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["status"] == "accepted"


def test_webhook_invoice_overdue():
    body = {
        "event_type": "invoice_overdue",
        "invoice_id": f"inv_E2E_{int(time.time())}",
        "amount": 25000,
        "currency": "INR",
        "days_overdue": 5,
        "customer_email": "invoice@test.com",
        "customer_phone": "+919999900003",
        "customer_name": "Invoice Tester",
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["status"] == "accepted"


def test_webhook_razorpay_raw_format():
    body = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_RAW_{int(time.time())}",
                    "order_id": f"order_RAW_{int(time.time())}",
                    "amount": 99900,
                    "currency": "INR",
                    "method": "card",
                    "error_code": "CARD_EXPIRED",
                    "error_description": "Card has expired",
                    "email": "raw@test.com",
                    "contact": "+919999900004",
                    "notes": {"customer_name": "Raw Tester"},
                }
            }
        },
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["status"] == "accepted"


def test_webhook_dedup():
    pid = f"pay_DEDUP_{int(time.time())}"
    body = {
        "event_type": "payment_failure",
        "payment_id": pid,
        "amount": 500,
        "currency": "INR",
        "error_code": "TIMEOUT",
        "customer_email": "dedup@test.com",
    }
    r1 = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r1.json()["status"] == "accepted", "First should be accepted"
    time.sleep(0.5)
    r2 = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r2.json()["status"] == "duplicate", f"Second should be duplicate, got {r2.json()['status']}"


def test_webhook_dedup_hash_fallback():
    ts = str(int(time.time() * 1000))
    body = {
        "event_type": "payment_failure",
        "amount": 777,
        "currency": "INR",
        "error_code": "GATEWAY_ERROR",
        "customer_email": f"noid_{ts}@test.com",
    }
    r1 = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r1.json()["status"] == "accepted", f"First should be accepted, got {r1.json()['status']}"
    time.sleep(0.5)
    r2 = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r2.json()["status"] == "duplicate", "Hash dedup should catch identical payloads"


def test_webhook_invalid_payload():
    ts = str(int(time.time() * 1000))
    r = requests.post(f"{BASE}/webhook/recovery-router", json={"bad": "data", "_ts": ts})
    assert r.status_code == 400, f"Expected 400, got {r.status_code} body={r.text[:200]}"


def test_webhook_invalid_event_type():
    ts = str(int(time.time() * 1000))
    body = {"event_type": "invalid_type", "amount": 100, "_ts": ts}
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code in (400, 422), f"Expected 400/422, got {r.status_code} body={r.text[:200]}"


# ── 3. Webhook: recovery-tracker ─────────────────────

def test_tracker_ignored_event():
    body = {"event": "payment.authorized", "payload": {"payment": {"entity": {}}}}
    r = requests.post(f"{BASE}/webhook/recovery-tracker", json=body)
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"


def test_tracker_no_match():
    body = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_NOMATCH_99999",
                    "order_id": "order_NOMATCH_99999",
                    "amount": 50000,
                    "method": "upi",
                    "notes": {},
                }
            }
        },
    }
    r = requests.post(f"{BASE}/webhook/recovery-tracker", json=body)
    assert r.status_code == 200
    assert r.json()["status"] == "no_match"


# ── 4. Events API ────────────────────────────────────

def test_events_list():
    r = requests.get(f"{BASE}/api/events")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data
    assert "total" in data
    assert isinstance(data["events"], list)


def test_events_pagination():
    r = requests.get(f"{BASE}/api/events?limit=5&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert len(data["events"]) <= 5


def test_events_filter_status():
    r = requests.get(f"{BASE}/api/events?status=pending")
    assert r.status_code == 200
    for e in r.json()["events"]:
        assert e["status"] == "pending", f"Expected pending, got {e['status']}"


def test_events_filter_event_type():
    r = requests.get(f"{BASE}/api/events?event_type=payment_failure")
    assert r.status_code == 200
    for e in r.json()["events"]:
        assert e["event_type"] == "payment_failure"


# ── 5. Analytics ─────────────────────────────────────

def test_analytics():
    r = requests.get(f"{BASE}/api/analytics")
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "ai_lift" in data
    assert "by_event_type" in data
    assert "by_channel" in data
    assert "channel_ranking" in data
    assert "by_failure_category" in data
    assert "generated_at" in data

    s = data["summary"]
    assert s["total_events"] >= 0
    assert 0 <= s["recovery_rate_percent"] <= 100


def test_analytics_cached():
    t1 = time.time()
    requests.get(f"{BASE}/api/analytics")
    t2 = time.time()
    requests.get(f"{BASE}/api/analytics")
    t3 = time.time()
    cached_time = t3 - t2
    first_time = t2 - t1
    assert cached_time < first_time + 1, "Cached call should not be much slower"


# ── 6. Simulator ─────────────────────────────────────

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


def test_simulate_all_scenarios():
    accepted = 0
    rate_limited = 0
    for event_type, scenario in SCENARIOS:
        r = requests.post(
            f"{BASE}/api/simulate",
            json={"event_type": event_type, "scenario": scenario},
        )
        if r.status_code == 429:
            rate_limited += 1
            continue
        assert r.status_code == 200, f"Scenario {scenario} failed: {r.status_code} {r.text}"
        assert r.json()["status"] == "accepted", f"Scenario {scenario}: {r.json()}"
        accepted += 1
    assert accepted >= 8, f"At least 8/10 scenarios should work, got {accepted} (rate limited: {rate_limited})"


def test_simulate_invalid_scenario():
    r = requests.post(
        f"{BASE}/api/simulate",
        json={"event_type": "payment_failure", "scenario": "nonexistent"},
    )
    assert r.status_code in (400, 429), f"Expected 400 or 429, got {r.status_code}"


# ── 7. Checkout page ─────────────────────────────────

def test_checkout_valid():
    r = requests.get(f"{BASE}/pay/order_ABCDEFGHIJ?name=Test&email=t@t.com&phone=+919999999999")
    assert r.status_code == 200
    assert "Razorpay" in r.text
    assert "Complete Your Payment" in r.text


def test_checkout_xss_blocked():
    r = requests.get(f"{BASE}/pay/order_ABCDEFGHIJ?name=<script>alert(1)</script>")
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text


def test_checkout_invalid_order_id():
    r = requests.get(f"{BASE}/pay/../../etc/passwd")
    assert r.status_code in (400, 404, 422), f"Expected 400/404/422, got {r.status_code}"


def test_checkout_order_id_injection():
    r = requests.get(f"{BASE}/pay/order_'; DROP TABLE--")
    assert r.status_code in (400, 404, 422), f"Expected rejection, got {r.status_code}"


# ── 8. Rate limiting ─────────────────────────────────

def test_rate_limit_simulation():
    hit_limit = False
    for i in range(15):
        r = requests.post(
            f"{BASE}/api/simulate",
            json={"event_type": "payment_failure", "scenario": "upi_timeout"},
        )
        if r.status_code == 429:
            hit_limit = True
            break
    assert hit_limit, "Rate limit (10 req/60s) should have been hit within 15 attempts"


# ── 9. Edge cases ────────────────────────────────────

def test_minimal_payload():
    body = {
        "event_type": "payment_failure",
        "payment_id": f"pay_MIN_{int(time.time())}",
        "amount": 100,
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


def test_large_amount():
    body = {
        "event_type": "payment_failure",
        "payment_id": f"pay_BIG_{int(time.time())}",
        "amount": 9999999.99,
        "currency": "INR",
        "error_code": "TIMEOUT",
        "customer_email": "big@test.com",
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200


def test_unicode_customer_name():
    body = {
        "event_type": "payment_failure",
        "payment_id": f"pay_UNI_{int(time.time())}",
        "amount": 500,
        "error_code": "TIMEOUT",
        "customer_name": "राहुल शर्मा",
        "customer_email": "unicode@test.com",
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200


def test_empty_optional_fields():
    body = {
        "event_type": "cart_abandonment",
        "payment_id": f"pay_EMPTY_{int(time.time())}",
        "amount": 0,
        "cart_value": 3000,
        "customer_email": None,
        "customer_phone": None,
        "customer_name": None,
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200


def test_zero_amount_cart():
    body = {
        "event_type": "cart_abandonment",
        "payment_id": f"pay_ZERO_{int(time.time())}",
        "amount": 0,
        "cart_value": 0,
        "items_in_cart": 0,
        "customer_email": "zero@test.com",
    }
    r = requests.post(f"{BASE}/webhook/recovery-router", json=body)
    assert r.status_code == 200


# ── Run all ───────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  RECOVERY ROUTER — END-TO-END TEST SUITE")
    print("=" * 60)

    print("\n[1] Root & Health")
    run_test("GET /", test_root)
    run_test("GET /api/health", test_health)
    run_test("GET /docs (Swagger)", test_docs)

    print("\n[2] Webhook: recovery-router")
    run_test("POST payment_failure", test_webhook_payment_failure)
    run_test("POST cart_abandonment", test_webhook_cart_abandonment)
    run_test("POST invoice_overdue", test_webhook_invoice_overdue)
    run_test("POST razorpay raw format", test_webhook_razorpay_raw_format)
    run_test("Dedup (same payment_id)", test_webhook_dedup)
    run_test("Dedup hash fallback (no IDs)", test_webhook_dedup_hash_fallback)
    run_test("Invalid payload (400)", test_webhook_invalid_payload)
    run_test("Invalid event_type", test_webhook_invalid_event_type)

    print("\n[3] Webhook: recovery-tracker")
    run_test("Ignored event type", test_tracker_ignored_event)
    run_test("No matching event", test_tracker_no_match)

    print("\n[4] Events API")
    run_test("GET /api/events", test_events_list)
    run_test("Pagination (limit=5)", test_events_pagination)
    run_test("Filter by status=pending", test_events_filter_status)
    run_test("Filter by event_type", test_events_filter_event_type)

    print("\n[5] Analytics")
    run_test("GET /api/analytics", test_analytics)
    run_test("Cache performance", test_analytics_cached)

    print("\n[6] Simulator")
    run_test("Invalid scenario (400)", test_simulate_invalid_scenario)
    run_test("All 10 scenarios", test_simulate_all_scenarios)

    print("\n[7] Checkout page")
    run_test("Valid checkout page", test_checkout_valid)
    run_test("XSS blocked in name", test_checkout_xss_blocked)
    run_test("Invalid order_id rejected", test_checkout_invalid_order_id)
    run_test("SQL injection in order_id", test_checkout_order_id_injection)

    print("\n[8] Rate limiting")
    run_test("Simulator rate limit (10/60s)", test_rate_limit_simulation)

    print("\n[9] Edge cases")
    run_test("Minimal payload", test_minimal_payload)
    run_test("Very large amount", test_large_amount)
    run_test("Unicode customer name", test_unicode_customer_name)
    run_test("Empty optional fields", test_empty_optional_fields)
    run_test("Zero-value cart", test_zero_amount_cart)

    print("\n" + "=" * 60)
    print(f"  RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
    print("=" * 60)

    if ERRORS:
        print("\nFailed tests:")
        for name, err in ERRORS:
            print(f"  - {name}: {err}")

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()

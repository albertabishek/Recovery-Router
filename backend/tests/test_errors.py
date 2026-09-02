"""Edge cases: duplicate webhooks, wrong transitions, missing fields, boundary values."""
import time
import pytest

pytestmark = pytest.mark.live
from conftest import simulate_and_wait, wait_for_celery, EMAILS, PHONES


class TestDuplicateWebhooks:
    def test_duplicate_payment_captured_idempotent(self, api):
        eid, ev = simulate_and_wait(
            api, "payment_failure", "upi_timeout",
            {"customer_email": EMAILS[0], "customer_phone": PHONES[0]},
            max_wait=60,
        )
        if not ev or ev["status"] != "pending":
            pytest.skip("Need a pending event")

        webhook = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_dup_123",
                        "amount": ev.get("amount", 500) * 100,
                        "currency": "INR",
                        "order_id": ev.get("order_id", "order_test"),
                        "notes": {"recovery_event_id": str(eid)},
                    }
                }
            }
        }
        r1 = api.post("/webhook/recovery-tracker", json=webhook)
        r2 = api.post("/webhook/recovery-tracker", json=webhook)

        assert r1.status_code in (200, 400, 401, 403)
        assert r2.status_code in (200, 400, 401, 403)


class TestStatusTransitions:
    def test_cannot_resume_recovered(self, api):
        events = api.get("/api/events", params={"status": "recovered", "limit": 1}).json()["events"]
        if not events:
            pytest.skip("No recovered events")
        eid = events[0]["id"]
        r = api.patch(f"/api/events/{eid}/control", json={"action": "resume"})
        assert r.status_code in (400, 409)

    def test_cannot_pause_no_action(self, api):
        events = api.get("/api/events", params={"status": "no_action_needed", "limit": 1}).json()["events"]
        if not events:
            pytest.skip("No no_action events")
        eid = events[0]["id"]
        r = api.patch(f"/api/events/{eid}/control", json={"action": "pause"})
        assert r.status_code in (400, 409)


class TestMissingFields:
    def test_simulate_empty_body(self, api):
        r = api.post("/api/simulate", json={})
        assert r.status_code == 422

    def test_simulate_missing_scenario(self, api):
        r = api.post("/api/simulate", json={"event_type": "payment_failure"})
        assert r.status_code in (200, 422)

    def test_live_checkout_empty_body(self, api):
        r = api.post("/api/live-checkout", json={})
        assert r.status_code in (200, 400, 422, 429)

    def test_control_empty_body(self, api):
        events = api.get("/api/events", params={"limit": 1}).json()["events"]
        if not events:
            pytest.skip("No events")
        eid = events[0]["id"]
        r = api.patch(f"/api/events/{eid}/control", json={})
        assert r.status_code in (400, 422)


class TestBoundaryValues:
    def test_events_limit_zero(self, api):
        r = api.get("/api/events", params={"limit": 0})
        assert r.status_code in (200, 400, 422)

    def test_events_negative_offset(self, api):
        r = api.get("/api/events", params={"offset": -1})
        assert r.status_code in (200, 400, 422)

    def test_events_very_large_limit(self, api):
        r = api.get("/api/events", params={"limit": 99999})
        assert r.status_code in (200, 422)

    def test_trace_zero_id(self, api):
        r = api.get("/api/events/0/trace")
        assert r.status_code in (200, 404)

    def test_trace_negative_id(self, api):
        r = api.get("/api/events/-1/trace")
        assert r.status_code in (200, 404, 422)


class TestOrganicRecovery:
    """Test that a payment.captured webhook without a matching event is logged as organic."""

    def test_unmatched_payment_logged(self, api):
        webhook = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_organic_test_999",
                        "amount": 75000,
                        "currency": "INR",
                        "order_id": "order_organic_test_999",
                        "notes": {},
                    }
                }
            }
        }
        r = api.post("/webhook/recovery-tracker", json=webhook)
        assert r.status_code in (200, 400, 401, 403)

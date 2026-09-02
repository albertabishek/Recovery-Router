"""End-to-end pipeline tests: simulate → classify → route → send → track."""
import time
import pytest

pytestmark = pytest.mark.live
from conftest import SCENARIOS, EXPECTED, simulate_and_wait, EMAILS, PHONES


class TestPipelineScenarios:
    """Fire each scenario and verify classification + routing outcomes."""

    @pytest.mark.parametrize("event_type,scenario", SCENARIOS, ids=[s[1] for s in SCENARIOS])
    def test_scenario_classification(self, api, event_type, scenario):
        customer = {
            "customer_name": "Pipeline Test",
            "customer_email": EMAILS[0],
            "customer_phone": PHONES[0],
        }
        event_id, ev = simulate_and_wait(api, event_type, scenario, customer, max_wait=60)
        assert ev is not None, f"Event {event_id} never processed for {scenario}"

        expected = EXPECTED[scenario]

        expected_cats = expected["category"] if isinstance(expected["category"], list) else [expected["category"]]
        assert ev["failure_category"] in expected_cats, (
            f"{scenario}: expected category in {expected_cats}, got {ev['failure_category']}"
        )

        actual_channel = ev.get("recommended_channel", "none")
        assert actual_channel in expected["channel_in"], (
            f"{scenario}: expected channel in {expected['channel_in']}, got {actual_channel}"
        )

        expected_statuses = expected["status"] if isinstance(expected["status"], list) else [expected["status"]]
        assert ev["status"] in expected_statuses, (
            f"{scenario}: expected status in {expected_statuses}, got {ev['status']}"
        )

        lo, hi = expected["max_attempts_range"]
        actual_max = ev.get("max_attempts") if ev.get("max_attempts") is not None else 5
        assert lo <= actual_max <= hi, (
            f"{scenario}: max_attempts={actual_max} not in [{lo},{hi}]"
        )

        plo, phi = expected["prob_range"]
        actual_prob = ev.get("recovery_probability", 0.5)
        assert plo <= actual_prob <= phi, (
            f"{scenario}: probability={actual_prob} not in [{plo},{phi}]"
        )


class TestNoActionPipeline:
    """Verify no_action events are handled correctly end-to-end."""

    def test_fraud_decline_no_action(self, api):
        eid, ev = simulate_and_wait(api, "payment_failure", "fraud_decline", max_wait=60)
        assert ev["status"] == "no_action_needed"
        assert ev.get("max_attempts") == 0 or ev.get("max_attempts") is None
        assert ev.get("attempt_count", 0) == 0
        assert ev.get("next_action_at") is None
        assert ev.get("recovery_window_ends") is None

    def test_low_value_cart_no_action(self, api):
        eid, ev = simulate_and_wait(api, "cart_abandonment", "low_value_cart", max_wait=60)
        assert ev["status"] == "no_action_needed"
        assert ev.get("attempt_count", 0) == 0


class TestPipelineAuditTrail:
    """Verify that processed events create audit log entries."""

    def test_pending_event_creates_attempt(self, api):
        eid, ev = simulate_and_wait(
            api, "payment_failure", "upi_timeout",
            {"customer_email": EMAILS[1], "customer_phone": PHONES[0]},
            max_wait=60,
        )
        if ev["status"] != "pending":
            pytest.skip("Event not in pending state")

        r = api.get(f"/api/events/{eid}/trace")
        trace = r.json()
        assert len(trace["attempts"]) >= 1
        first = trace["attempts"][0]
        assert first["attempt_number"] == 1
        assert first["channel_used"] in ("whatsapp", "email", "sms")


class TestPipelineRecoveryWindow:
    """Verify recovery window is set correctly for pending events."""

    def test_pending_has_recovery_window(self, api):
        eid, ev = simulate_and_wait(
            api, "payment_failure", "gateway_error",
            {"customer_email": EMAILS[2], "customer_phone": PHONES[1]},
            max_wait=60,
        )
        if ev["status"] != "pending":
            pytest.skip("Not pending")
        assert ev.get("recovery_window_ends") is not None


class TestPipelineDedup:
    """Verify that duplicate simulations create separate events."""

    def test_duplicate_simulations_distinct(self, api):
        before = api.get("/api/events", params={"limit": 1}).json()["events"]
        before_id = before[0]["id"] if before else 0

        r1 = api.post("/api/simulate", json={
            "event_type": "payment_failure", "scenario": "bank_downtime",
        })
        time.sleep(2)
        r2 = api.post("/api/simulate", json={
            "event_type": "payment_failure", "scenario": "bank_downtime",
        })
        assert r1.status_code in (200, 429)
        assert r2.status_code in (200, 429)

        if r1.status_code == 429 or r2.status_code == 429:
            pytest.skip("Rate limited — cannot test dedup")

        time.sleep(10)
        events = api.get("/api/events", params={"limit": 10}).json()["events"]
        new_events = [e for e in events if e["id"] > before_id]
        assert len(new_events) >= 2, f"Expected 2+ new events, got {len(new_events)}"

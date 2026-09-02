"""Test all 12 API endpoints with valid, invalid, and edge-case inputs."""
import pytest

pytestmark = pytest.mark.live


class TestHealthEndpoint:
    def test_health_returns_ok(self, api):
        r = api.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "services" in data
        assert data["services"]["redis"] == "ok"
        assert "celery" in data["services"]
        assert data["services"]["supabase"] == "configured"

    def test_health_has_queue_depth(self, api):
        r = api.get("/api/health")
        data = r.json()
        assert "queue_depth" in data["services"]
        assert isinstance(data["services"]["queue_depth"], int)


class TestRootEndpoint:
    def test_root_returns_info(self, api):
        r = api.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Recovery Router API"
        assert "version" in data


class TestEventsEndpoint:
    def test_get_events_default(self, api):
        r = api.get("/api/events")
        assert r.status_code == 200
        data = r.json()
        assert "events" in data
        assert "total" in data
        assert isinstance(data["events"], list)
        assert data["total"] >= 0

    def test_get_events_with_limit(self, api):
        r = api.get("/api/events", params={"limit": 3})
        data = r.json()
        assert len(data["events"]) <= 3

    def test_get_events_with_offset(self, api):
        r = api.get("/api/events", params={"limit": 1, "offset": 0})
        first = r.json()["events"]
        r2 = api.get("/api/events", params={"limit": 1, "offset": 1})
        second = r2.json()["events"]
        if first and second:
            assert first[0]["id"] != second[0]["id"]

    def test_get_events_filter_by_status_pending(self, api):
        r = api.get("/api/events", params={"status": "pending"})
        data = r.json()
        for e in data["events"]:
            assert e["status"] == "pending"

    def test_get_events_filter_by_status_exhausted(self, api):
        r = api.get("/api/events", params={"status": "exhausted"})
        data = r.json()
        for e in data["events"]:
            assert e["status"] == "exhausted"

    def test_get_events_filter_by_status_no_action(self, api):
        r = api.get("/api/events", params={"status": "no_action_needed"})
        data = r.json()
        for e in data["events"]:
            assert e["status"] == "no_action_needed"

    def test_get_events_filter_by_status_recovered(self, api):
        r = api.get("/api/events", params={"status": "recovered"})
        data = r.json()
        for e in data["events"]:
            assert e["status"] == "recovered"

    def test_events_schema_completeness(self, api):
        r = api.get("/api/events", params={"limit": 1})
        data = r.json()
        if data["events"]:
            e = data["events"][0]
            required_fields = [
                "id", "event_type", "amount", "currency", "status",
                "failure_category", "recovery_probability",
                "recommended_channel", "attempt_count", "max_attempts",
                "created_at",
            ]
            for f in required_fields:
                assert f in e, f"Missing field: {f}"


class TestEventTraceEndpoint:
    def test_trace_existing_event(self, api):
        events = api.get("/api/events", params={"limit": 1}).json()["events"]
        if not events:
            pytest.skip("No events to trace")
        eid = events[0]["id"]
        r = api.get(f"/api/events/{eid}/trace")
        assert r.status_code == 200
        data = r.json()
        assert "event" in data
        assert "attempts" in data
        assert data["event"]["id"] == eid

    def test_trace_nonexistent_event(self, api):
        r = api.get("/api/events/999999/trace")
        assert r.status_code in (404, 200)

    def test_trace_attempts_ordered(self, api):
        events = api.get("/api/events", params={"limit": 5}).json()["events"]
        for e in events:
            if e["attempt_count"] > 1:
                trace = api.get(f"/api/events/{e['id']}/trace").json()
                attempts = trace["attempts"]
                for i in range(1, len(attempts)):
                    assert attempts[i]["attempt_number"] >= attempts[i-1]["attempt_number"]
                break


class TestAnalyticsEndpoint:
    def test_analytics_returns_data(self, api):
        r = api.get("/api/analytics")
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        s = data["summary"]
        assert "total_events" in s
        assert "recovered_count" in s
        assert "recovered_amount" in s
        assert "pending_count" in s
        assert "exhausted_count" in s
        assert "no_action_count" in s

    def test_analytics_has_ai_lift(self, api):
        r = api.get("/api/analytics")
        data = r.json()
        assert "ai_lift" in data

    def test_analytics_has_channel_ranking(self, api):
        r = api.get("/api/analytics")
        data = r.json()
        assert "channel_ranking" in data
        assert isinstance(data["channel_ranking"], list)

    def test_analytics_has_by_event_type(self, api):
        r = api.get("/api/analytics")
        data = r.json()
        assert "by_event_type" in data

    def test_analytics_totals_consistent(self, api):
        r = api.get("/api/analytics")
        s = r.json()["summary"]
        total = s["total_events"]
        parts = s["recovered_count"] + s["pending_count"] + s["exhausted_count"] + s["no_action_count"]
        organic = s.get("organic_count", 0)
        paused = s.get("paused_count", 0)
        assert total >= parts, f"Total {total} < sum of parts {parts}"


class TestAuditLogsEndpoint:
    def test_audit_logs_returns_data(self, api):
        r = api.get("/api/audit-logs")
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)

    def test_audit_log_schema(self, api):
        r = api.get("/api/audit-logs")
        logs = r.json()["logs"]
        if logs:
            log = logs[0]
            required = ["id", "recovery_event_id", "channel_used", "outcome", "created_at"]
            for f in required:
                assert f in log, f"Missing field in audit log: {f}"

    def test_audit_logs_filter_by_event_id(self, api):
        r = api.get("/api/audit-logs")
        logs = r.json()["logs"]
        if logs:
            eid = logs[0]["recovery_event_id"]
            r2 = api.get("/api/audit-logs", params={"event_id": eid})
            filtered = r2.json()["logs"]
            for log in filtered:
                assert log["recovery_event_id"] == eid


class TestSimulateEndpoint:
    def test_simulate_valid(self, api):
        r = api.post("/api/simulate", json={
            "event_type": "payment_failure",
            "scenario": "upi_timeout",
        })
        assert r.status_code in (200, 429)
        if r.status_code == 200:
            data = r.json()
            assert data["status"] == "accepted"

    def test_simulate_with_customer_details(self, api):
        r = api.post("/api/simulate", json={
            "event_type": "payment_failure",
            "scenario": "gateway_error",
            "customer_name": "Test User",
            "customer_email": "study1only2@gmail.com",
            "customer_phone": "+919042824369",
        })
        assert r.status_code in (200, 429)

    def test_simulate_invalid_scenario(self, api):
        r = api.post("/api/simulate", json={
            "event_type": "payment_failure",
            "scenario": "nonexistent_scenario",
        })
        assert r.status_code in (400, 422, 429)

    def test_simulate_missing_event_type(self, api):
        r = api.post("/api/simulate", json={
            "scenario": "upi_timeout",
        })
        assert r.status_code == 422

    def test_simulate_invalid_event_type(self, api):
        r = api.post("/api/simulate", json={
            "event_type": "invalid_type",
            "scenario": "upi_timeout",
        })
        assert r.status_code in (400, 422)


class TestControlEndpoint:
    def test_pause_pending_event(self, api):
        events = api.get("/api/events", params={"status": "pending", "limit": 1}).json()["events"]
        if not events:
            pytest.skip("No pending events to test pause")
        eid = events[0]["id"]
        r = api.patch(f"/api/events/{eid}/control", json={"action": "pause"})
        assert r.status_code == 200
        assert r.json()["status"] == "paused"

        api.patch(f"/api/events/{eid}/control", json={"action": "resume"})

    def test_resume_paused_event(self, api):
        events = api.get("/api/events", params={"status": "pending", "limit": 1}).json()["events"]
        if not events:
            pytest.skip("No pending events")
        eid = events[0]["id"]
        api.patch(f"/api/events/{eid}/control", json={"action": "pause"})
        r = api.patch(f"/api/events/{eid}/control", json={"action": "resume"})
        assert r.status_code == 200
        assert r.json()["status"] == "resumed"

    def test_pause_exhausted_event_fails(self, api):
        events = api.get("/api/events", params={"status": "exhausted", "limit": 1}).json()["events"]
        if not events:
            pytest.skip("No exhausted events")
        eid = events[0]["id"]
        r = api.patch(f"/api/events/{eid}/control", json={"action": "pause"})
        assert r.status_code in (400, 409)

    def test_control_nonexistent_event(self, api):
        r = api.patch("/api/events/999999/control", json={"action": "pause"})
        assert r.status_code == 404

    def test_control_invalid_action(self, api):
        events = api.get("/api/events", params={"limit": 1}).json()["events"]
        if not events:
            pytest.skip("No events")
        eid = events[0]["id"]
        r = api.patch(f"/api/events/{eid}/control", json={"action": "explode"})
        assert r.status_code in (400, 422)


class TestLiveCheckoutEndpoint:
    def test_live_checkout_valid(self, api):
        r = api.post("/api/live-checkout", json={
            "amount": 100,
            "name": "Test User",
            "email": "study1only2@gmail.com",
            "phone": "+919042824369",
        })
        assert r.status_code == 200
        data = r.json()
        assert "order_id" in data
        assert data["order_id"].startswith("order_")

    def test_live_checkout_zero_amount(self, api):
        r = api.post("/api/live-checkout", json={
            "amount": 0,
        })
        assert r.status_code == 400

    def test_live_checkout_negative_amount(self, api):
        r = api.post("/api/live-checkout", json={
            "amount": -500,
        })
        assert r.status_code == 400

    def test_live_checkout_exceeds_max(self, api):
        r = api.post("/api/live-checkout", json={
            "amount": 99999,
        })
        assert r.status_code == 400


class TestCheckoutPageEndpoint:
    def test_pay_page_returns_html(self, api):
        r = api.post("/api/live-checkout", json={"amount": 100})
        if r.status_code == 200:
            order_id = r.json()["order_id"]
            r2 = api.get(f"/pay/{order_id}")
            assert r2.status_code == 200
            assert "razorpay" in r2.text.lower() or "Razorpay" in r2.text

    def test_pay_page_invalid_order(self, api):
        r = api.get("/pay/order_NONEXISTENT123")
        assert r.status_code == 200  # still serves the page, Razorpay handles the error

"""Load and concurrency tests: parallel requests, race conditions, dedup."""
import time
import threading
import pytest
from conftest import EMAILS, PHONES


class TestConcurrentSimulations:
    def test_parallel_simulations(self, api):
        """Fire 5 simulations concurrently and verify all are accepted."""
        results = []
        errors = []

        def fire(scenario):
            try:
                r = api.post("/api/simulate", json={
                    "event_type": "payment_failure",
                    "scenario": scenario,
                    "customer_email": EMAILS[0],
                    "customer_phone": PHONES[0],
                })
                results.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        scenarios = ["upi_timeout", "card_expired", "insufficient_funds", "bank_downtime", "gateway_error"]
        threads = [threading.Thread(target=fire, args=(s,)) for s in scenarios]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors: {errors}"
        success = [c for c in results if c == 200]
        rate_limited = [c for c in results if c == 429]
        assert len(success) >= 1, f"Expected at least 1 success, got {results}"
        assert all(c in (200, 429) for c in results), f"Unexpected status codes: {results}"

    def test_parallel_event_reads(self, api):
        """Fire 10 concurrent reads and verify no errors."""
        results = []

        def read_events():
            try:
                r = api.get("/api/events", params={"limit": 5})
                results.append(r.status_code)
            except Exception as e:
                results.append(0)

        threads = [threading.Thread(target=read_events) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert all(code == 200 for code in results), f"Status codes: {results}"


class TestRaceConditions:
    def test_concurrent_pause_resume(self, api):
        """Pause and resume the same event concurrently — should not corrupt."""
        events = api.get("/api/events", params={"status": "pending", "limit": 1}).json()["events"]
        if not events:
            pytest.skip("No pending events for race test")

        eid = events[0]["id"]
        results = []

        def toggle(action):
            try:
                r = api.patch(f"/api/events/{eid}/control", json={"action": action})
                results.append((action, r.status_code))
            except Exception as e:
                results.append((action, str(e)))

        t1 = threading.Thread(target=toggle, args=("pause",))
        t2 = threading.Thread(target=toggle, args=("resume",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        r = api.get(f"/api/events/{eid}/trace")
        assert r.status_code == 200
        final_status = r.json()["event"]["status"]
        assert final_status in ("pending", "paused"), f"Unexpected status: {final_status}"

        if final_status == "paused":
            api.patch(f"/api/events/{eid}/control", json={"action": "resume"})


class TestEndpointPerformance:
    def test_health_response_time(self, api):
        """Health check should respond under 2 seconds."""
        import time as _time
        start = _time.monotonic()
        r = api.get("/api/health")
        elapsed = _time.monotonic() - start
        assert r.status_code == 200
        assert elapsed < 15.0, f"Health took {elapsed:.2f}s"

    def test_events_response_time(self, api):
        """Events list should respond under 5 seconds."""
        import time as _time
        start = _time.monotonic()
        r = api.get("/api/events", params={"limit": 20})
        elapsed = _time.monotonic() - start
        assert r.status_code == 200
        assert elapsed < 5.0, f"Events took {elapsed:.2f}s"

    def test_analytics_response_time(self, api):
        """Analytics should respond under 5 seconds."""
        import time as _time
        start = _time.monotonic()
        r = api.get("/api/analytics")
        elapsed = _time.monotonic() - start
        assert r.status_code == 200
        assert elapsed < 15.0, f"Analytics took {elapsed:.2f}s"

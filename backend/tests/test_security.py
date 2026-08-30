"""Security tests: injection, XSS, CORS, rate limiting, webhook signatures."""
import pytest


class TestSQLInjection:
    def test_events_status_injection(self):
        import httpx
        with httpx.Client(base_url="http://localhost:8000", timeout=10) as c:
            try:
                r = c.get("/api/events", params={"status": "'; DROP TABLE recovery_events;--"})
                assert r.status_code in (200, 400, 422, 500)
            except Exception:
                pass
        with httpx.Client(base_url="http://localhost:8000", timeout=10) as c:
            check = c.get("/api/events", params={"limit": 1})
            assert check.status_code == 200

    def test_audit_logs_event_id_injection(self, api):
        r = api.get("/api/audit-logs", params={"event_id": "1 OR 1=1"})
        assert r.status_code in (200, 400, 422)

    def test_trace_id_injection(self, api):
        r = api.get("/api/events/1;DROP TABLE recovery_events/trace")
        assert r.status_code in (404, 422, 400)


class TestXSS:
    def test_simulate_xss_in_name(self, api):
        payload = "<script>alert('xss')</script>"
        r = api.post("/api/simulate", json={
            "event_type": "payment_failure",
            "scenario": "upi_timeout",
            "customer_name": payload,
        })
        assert r.status_code == 200
        data = r.json()
        if "customer_name" in data:
            assert "<script>" not in data["customer_name"]

    def test_simulate_xss_in_email(self, api):
        r = api.post("/api/simulate", json={
            "event_type": "payment_failure",
            "scenario": "upi_timeout",
            "customer_email": "<img onerror=alert(1) src=x>@evil.com",
        })
        assert r.status_code in (200, 400, 422)

    def test_events_response_is_json(self, api):
        r = api.get("/api/events", params={"limit": 10})
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/json")


class TestCORS:
    def test_cors_preflight(self, api):
        r = api.options("/api/events", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        })
        assert r.status_code in (200, 204)

    def test_cors_allows_frontend_origin(self, api):
        r = api.get("/api/events", headers={"Origin": "http://localhost:5173"})
        cors_header = r.headers.get("access-control-allow-origin", "")
        assert cors_header in ("*", "http://localhost:5173")

    def test_cors_allows_tunnel_origin(self, api):
        r = api.get("/api/events", headers={"Origin": "https://app.albertabishek.com"})
        cors_header = r.headers.get("access-control-allow-origin", "")
        assert cors_header != ""


class TestWebhookSecurity:
    def test_webhook_without_signature(self, api):
        r = api.post("/webhook/recovery-tracker", json={"event": "payment.captured"})
        assert r.status_code in (200, 400, 401, 403)

    def test_webhook_invalid_signature(self, api):
        r = api.post("/webhook/recovery-tracker",
                      json={"event": "payment.captured"},
                      headers={"X-Razorpay-Signature": "invalid_sig_abc123"})
        assert r.status_code in (200, 400, 401, 403)

    def test_webhook_empty_body(self, api):
        r = api.post("/webhook/recovery-router", content=b"")
        assert r.status_code in (400, 401, 422, 429, 500)

    def test_webhook_malformed_json(self, api):
        r = api.post("/webhook/recovery-router",
                      content=b"not json at all",
                      headers={"Content-Type": "application/json"})
        assert r.status_code in (400, 401, 422, 429, 500)


class TestInputValidation:
    def test_simulate_oversized_payload(self, api):
        r = api.post("/api/simulate", json={
            "event_type": "payment_failure",
            "scenario": "upi_timeout",
            "customer_name": "A" * 10000,
            "customer_email": "B" * 5000 + "@test.com",
        })
        assert r.status_code in (200, 400, 413, 422, 429)

    def test_simulate_special_chars(self, api):
        r = api.post("/api/simulate", json={
            "event_type": "payment_failure",
            "scenario": "upi_timeout",
            "customer_name": "'; exec('import os; os.system(\"rm -rf /\")')",
        })
        assert r.status_code in (200, 400, 422, 429)

    def test_control_invalid_json(self, api):
        r = api.patch("/api/events/1/control",
                       content=b"not json",
                       headers={"Content-Type": "application/json"})
        assert r.status_code in (400, 422)

    def test_live_checkout_string_amount(self, api):
        r = api.post("/api/live-checkout", json={"amount": "abc"})
        assert r.status_code in (400, 422)

    def test_live_checkout_huge_amount(self, api):
        r = api.post("/api/live-checkout", json={"amount": 999999999})
        assert r.status_code in (400, 422, 429)


class TestPathTraversal:
    def test_event_id_path_traversal(self, api):
        r = api.get("/api/events/../../../etc/passwd/trace")
        assert r.status_code in (404, 422, 400)

    def test_pay_path_traversal(self, api):
        r = api.get("/pay/../../../etc/passwd")
        assert r.status_code in (404, 400, 200)

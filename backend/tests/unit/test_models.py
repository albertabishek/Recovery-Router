"""Unit tests for models.py — Pydantic model validation."""
import pytest
from pydantic import ValidationError
from app.models import (
    RecoveryEventInput, ClassificationResult, ActionPlan,
    WebhookResponse, AnalyticsSummary, AILift, SimulateRequest,
    HealthResponse, EventListItem, AnalyticsResponse,
)


class TestRecoveryEventInput:
    def test_minimal_valid(self):
        e = RecoveryEventInput(event_type="payment_failure")
        assert e.amount == 0
        assert e.currency == "INR"
        assert e.customer_name == "Unknown"

    def test_all_fields(self):
        e = RecoveryEventInput(
            event_type="cart_abandonment",
            payment_id="pay_1", order_id="ord_1", invoice_id="inv_1",
            amount=999.50, currency="USD", method="card",
            error_code="TIMEOUT", error_description="Timed out",
            customer_email="t@t.com", customer_phone="+91999",
            customer_name="Test", cart_value=1500, items_in_cart=3,
            days_overdue=10,
        )
        assert e.event_type == "cart_abandonment"
        assert e.cart_value == 1500

    def test_invalid_event_type(self):
        with pytest.raises(ValidationError):
            RecoveryEventInput(event_type="invalid_type")

    def test_invoice_overdue_type(self):
        e = RecoveryEventInput(event_type="invoice_overdue", days_overdue=30)
        assert e.days_overdue == 30


class TestClassificationResult:
    def test_valid(self):
        r = ClassificationResult(
            leak_type="payment_failure",
            failure_category="upi_timeout",
            recovery_probability=0.8,
            recommended_action="retry",
            recommended_channel="whatsapp",
            recommended_timing="immediate",
            reasoning="UPI timed out",
        )
        assert r.fallback_used is False

    def test_probability_bounds(self):
        with pytest.raises(ValidationError):
            ClassificationResult(
                leak_type="payment_failure", failure_category="x",
                recovery_probability=1.5,
                recommended_action="x", recommended_channel="email",
                recommended_timing="immediate", reasoning="x",
            )

    def test_negative_probability(self):
        with pytest.raises(ValidationError):
            ClassificationResult(
                leak_type="payment_failure", failure_category="x",
                recovery_probability=-0.1,
                recommended_action="x", recommended_channel="email",
                recommended_timing="immediate", reasoning="x",
            )

    def test_invalid_channel(self):
        with pytest.raises(ValidationError):
            ClassificationResult(
                leak_type="payment_failure", failure_category="x",
                recovery_probability=0.5,
                recommended_action="x", recommended_channel="telegram",
                recommended_timing="immediate", reasoning="x",
            )

    def test_invalid_timing(self):
        with pytest.raises(ValidationError):
            ClassificationResult(
                leak_type="payment_failure", failure_category="x",
                recovery_probability=0.5,
                recommended_action="x", recommended_channel="email",
                recommended_timing="2_hours", reasoning="x",
            )


class TestActionPlan:
    def test_send_now(self):
        a = ActionPlan(action="send_now", channel="whatsapp")
        assert a.delay_seconds == 0

    def test_send_delayed(self):
        a = ActionPlan(action="send_delayed", channel="email", delay_seconds=300)
        assert a.delay_seconds == 300

    def test_no_action(self):
        a = ActionPlan(action="no_action", skip_reason="unrecoverable")
        assert a.channel is None

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            ActionPlan(action="retry")


class TestWebhookResponse:
    def test_basic(self):
        r = WebhookResponse(status="ok", message="Processed")
        assert r.event_id is None

    def test_with_event_id(self):
        r = WebhookResponse(status="ok", message="Created", event_id=42)
        assert r.event_id == 42


class TestAnalyticsSummary:
    def test_defaults(self):
        a = AnalyticsSummary()
        assert a.total_events == 0
        assert a.recovery_rate_percent == 0.0


class TestAILift:
    def test_defaults(self):
        a = AILift()
        assert a.baseline_rate_percent == 15.0


class TestSimulateRequest:
    def test_valid(self):
        s = SimulateRequest(event_type="payment_failure", scenario="card_expired")
        assert s.scenario == "card_expired"

    def test_invalid_event_type(self):
        with pytest.raises(ValidationError):
            SimulateRequest(event_type="bad")


class TestHealthResponse:
    def test_defaults(self):
        h = HealthResponse()
        assert h.status == "ok"
        assert h.version == "1.0.0"


class TestEventListItem:
    def test_minimal(self):
        e = EventListItem(
            id=1, event_type="payment_failure", amount=500,
            currency="INR", status="pending", created_at="2026-01-01T00:00:00Z",
        )
        assert e.attempt_count == 0
        assert e.recovered_at is None

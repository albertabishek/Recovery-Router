"""Unit tests for classifier.py — _sanitize, _fallback_classify, classify_event orchestration."""
import pytest
from unittest.mock import patch, MagicMock
from app.models import RecoveryEventInput, ClassificationResult
from app.services.classifier import _sanitize, _fallback_classify, classify_event, _ai_classify


class TestSanitize:
    def test_none_returns_none(self):
        assert _sanitize(None) is None

    def test_strips_control_chars(self):
        assert _sanitize("hello\x00world") == "helloworld"

    def test_truncates_to_max_len(self):
        assert len(_sanitize("a" * 500, max_len=200)) == 200

    def test_preserves_normal_text(self):
        assert _sanitize("Normal text 123") == "Normal text 123"

    def test_custom_max_len(self):
        assert _sanitize("abcdef", max_len=3) == "abc"

    def test_empty_string(self):
        assert _sanitize("") == ""


class TestFallbackClassify:
    def _make_event(self, **kwargs):
        defaults = {"event_type": "payment_failure", "amount": 499}
        defaults.update(kwargs)
        return RecoveryEventInput(**defaults)

    def test_timeout_error_code(self):
        r = _fallback_classify(self._make_event(error_code="TIMEOUT"))
        assert r.failure_category == "upi_timeout"
        assert r.recovery_probability == 0.80
        assert r.recommended_channel == "whatsapp"
        assert r.recommended_timing == "immediate"
        assert r.fallback_used is True

    def test_card_expired(self):
        r = _fallback_classify(self._make_event(error_code="CARD_EXPIRED"))
        assert r.failure_category == "card_expired"
        assert r.recommended_channel == "email"

    def test_fraud_unrecoverable(self):
        r = _fallback_classify(self._make_event(error_code="FRAUD"))
        assert r.failure_category == "unrecoverable_decline"
        assert r.recovery_probability == 0.0
        assert r.recommended_channel == "none"
        assert r.skip_reason is not None

    def test_insufficient_funds(self):
        r = _fallback_classify(self._make_event(error_code="INSUFFICIENT_FUNDS"))
        assert r.failure_category == "insufficient_funds"
        assert r.recommended_channel == "sms"
        assert r.recommended_timing == "4_hours"

    def test_cancelled_user(self):
        r = _fallback_classify(self._make_event(error_code="CANCELLED"))
        assert r.failure_category == "user_cancelled"
        assert r.recommended_timing == "1_hour"

    def test_gateway_error(self):
        r = _fallback_classify(self._make_event(error_code="GATEWAY_ERROR"))
        assert r.failure_category == "gateway_error"
        assert r.recovery_probability == 0.85

    def test_cart_abandonment_high_value(self):
        r = _fallback_classify(self._make_event(
            event_type="cart_abandonment", cart_value=500
        ))
        assert r.failure_category == "high_intent_abandonment"
        assert r.recommended_channel == "whatsapp"
        assert r.recommended_timing == "1_hour"

    def test_cart_abandonment_low_value(self):
        r = _fallback_classify(self._make_event(
            event_type="cart_abandonment", cart_value=50
        ))
        assert r.failure_category == "browse_only_abandonment"
        assert r.recommended_channel == "none"
        assert r.skip_reason is not None

    def test_invoice_recently_overdue(self):
        r = _fallback_classify(self._make_event(
            event_type="invoice_overdue", days_overdue=3
        ))
        assert r.failure_category == "recently_overdue"
        assert r.recovery_probability == 0.70

    def test_invoice_moderately_overdue(self):
        r = _fallback_classify(self._make_event(
            event_type="invoice_overdue", days_overdue=15
        ))
        assert r.failure_category == "moderately_overdue"

    def test_invoice_long_overdue(self):
        r = _fallback_classify(self._make_event(
            event_type="invoice_overdue", days_overdue=60
        ))
        assert r.failure_category == "long_overdue"
        assert r.recovery_probability == 0.15

    def test_error_description_fallback(self):
        r = _fallback_classify(self._make_event(
            error_code="UNKNOWN", error_description="Payment timed out due to TIMEOUT"
        ))
        assert r.failure_category == "upi_timeout"

    def test_unknown_error_defaults_to_gateway(self):
        r = _fallback_classify(self._make_event(error_code="SOMETHING_WEIRD"))
        assert r.failure_category == "gateway_error"
        assert r.recovery_probability == 0.5

    def test_bank_downtime(self):
        r = _fallback_classify(self._make_event(error_code="BANK_DOWNTIME"))
        assert r.failure_category == "bank_downtime"
        assert r.recommended_timing == "30_minutes"

    def test_network_error(self):
        r = _fallback_classify(self._make_event(error_code="NETWORK"))
        assert r.failure_category == "bank_downtime"

    def test_declined(self):
        r = _fallback_classify(self._make_event(error_code="DECLINED"))
        assert r.failure_category == "unrecoverable_decline"
        assert r.recovery_probability == 0.05


class TestClassifyEvent:
    def _make_event(self, **kwargs):
        defaults = {"event_type": "payment_failure", "amount": 499}
        defaults.update(kwargs)
        return RecoveryEventInput(**defaults)

    @patch("app.services.classifier._ai_classify")
    def test_uses_ai_when_available(self, mock_ai):
        mock_ai.return_value = ClassificationResult(
            leak_type="payment_failure", failure_category="upi_timeout",
            recovery_probability=0.9, recommended_action="retry",
            recommended_channel="whatsapp", recommended_timing="immediate",
            reasoning="AI says so", fallback_used=False,
        )
        r = classify_event(self._make_event())
        assert r.fallback_used is False
        assert r.failure_category == "upi_timeout"

    @patch("app.services.classifier._ai_classify", return_value=None)
    def test_falls_back_when_ai_returns_none(self, mock_ai):
        r = classify_event(self._make_event(error_code="TIMEOUT"))
        assert r.fallback_used is True
        assert r.failure_category == "upi_timeout"

    @patch("app.services.classifier._ai_classify", side_effect=Exception("API down"))
    def test_falls_back_on_ai_exception(self, mock_ai):
        r = classify_event(self._make_event(error_code="GATEWAY"))
        assert r.fallback_used is True
        assert r.failure_category == "gateway_error"


class TestAIClassify:
    def _make_event(self, **kwargs):
        defaults = {"event_type": "payment_failure", "amount": 499}
        defaults.update(kwargs)
        return RecoveryEventInput(**defaults)

    @patch("app.services.classifier.ai_call")
    def test_ai_success(self, mock_ai):
        mock_ai.return_value = {
            "leak_type": "payment_failure",
            "failure_category": "upi_timeout",
            "recovery_probability": 0.85,
            "recommended_action": "Send retry",
            "recommended_channel": "whatsapp",
            "recommended_timing": "immediate",
            "reasoning": "UPI timed out",
        }
        r = _ai_classify(self._make_event())
        assert r.failure_category == "upi_timeout"
        assert r.fallback_used is False

    @patch("app.services.classifier.ai_call", return_value=None)
    def test_ai_returns_none(self, mock_ai):
        assert _ai_classify(self._make_event()) is None

    @patch("app.services.classifier.ai_call")
    def test_ai_none_channel_sets_skip_reason(self, mock_ai):
        mock_ai.return_value = {
            "leak_type": "payment_failure",
            "failure_category": "unrecoverable_decline",
            "recovery_probability": 0.0,
            "recommended_action": "none",
            "recommended_channel": "none",
            "recommended_timing": "immediate",
            "reasoning": "Fraud detected",
        }
        r = _ai_classify(self._make_event())
        assert r.skip_reason == "Fraud detected"

    @patch("app.services.classifier.ai_call")
    def test_ai_fills_defaults(self, mock_ai):
        mock_ai.return_value = {
            "failure_category": "gateway_error",
            "recovery_probability": 0.8,
            "recommended_channel": "email",
            "recommended_timing": "5_minutes",
        }
        r = _ai_classify(self._make_event())
        assert r.leak_type == "payment_failure"
        assert r.recommended_action == "recover_via_email"
        assert r.reasoning == "AI classification"

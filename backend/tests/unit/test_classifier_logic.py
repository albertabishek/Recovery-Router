import pytest
from app.models import RecoveryEventInput
from app.services.classifier import _fallback_classify


class TestFallbackClassifyPaymentFailures:
    def test_upi_timeout(self):
        event = RecoveryEventInput(
            event_type="payment_failure",
            amount=499,
            error_code="TIMEOUT",
            error_description="Payment timed out",
            method="upi",
        )
        result = _fallback_classify(event)
        assert result.failure_category == "upi_timeout"
        assert result.recommended_channel == "whatsapp"
        assert result.recommended_timing == "immediate"
        assert result.recovery_probability == 0.80
        assert result.fallback_used is True

    def test_card_expired(self):
        event = RecoveryEventInput(
            event_type="payment_failure",
            amount=2000,
            error_code="CARD_EXPIRED",
        )
        result = _fallback_classify(event)
        assert result.failure_category == "card_expired"
        assert result.recommended_channel == "email"
        assert result.recovery_probability == 0.50

    def test_fraud_unrecoverable(self):
        event = RecoveryEventInput(
            event_type="payment_failure",
            amount=5000,
            error_code="FRAUD",
        )
        result = _fallback_classify(event)
        assert result.failure_category == "unrecoverable_decline"
        assert result.recommended_channel == "none"
        assert result.recovery_probability == 0.0

    def test_insufficient_funds(self):
        event = RecoveryEventInput(
            event_type="payment_failure",
            amount=1000,
            error_code="INSUFFICIENT_FUNDS",
        )
        result = _fallback_classify(event)
        assert result.failure_category == "insufficient_funds"
        assert result.recommended_channel == "sms"
        assert result.recommended_timing == "4_hours"

    def test_gateway_error(self):
        event = RecoveryEventInput(
            event_type="payment_failure",
            amount=500,
            error_code="GATEWAY_ERROR",
        )
        result = _fallback_classify(event)
        assert result.failure_category == "gateway_error"
        assert result.recommended_channel == "whatsapp"
        assert result.recommended_timing == "5_minutes"
        assert result.recovery_probability == 0.85

    def test_error_description_fallback(self):
        event = RecoveryEventInput(
            event_type="payment_failure",
            amount=1000,
            error_code="UNKNOWN_123",
            error_description="Bank server is temporarily unavailable (NETWORK error)",
        )
        result = _fallback_classify(event)
        assert result.failure_category == "bank_downtime"

    def test_cancelled_via_description(self):
        event = RecoveryEventInput(
            event_type="payment_failure",
            amount=1000,
            error_code="UNKNOWN",
            error_description="User cancelled the transaction",
        )
        result = _fallback_classify(event)
        assert result.failure_category == "user_cancelled"

    def test_unknown_error_defaults_to_gateway(self):
        event = RecoveryEventInput(
            event_type="payment_failure",
            amount=1000,
            error_code="XYZABC",
            error_description="Something completely unknown",
        )
        result = _fallback_classify(event)
        assert result.failure_category == "gateway_error"
        assert result.recovery_probability == 0.5


class TestFallbackClassifyCartAbandonment:
    def test_high_value_cart(self):
        event = RecoveryEventInput(
            event_type="cart_abandonment",
            amount=0,
            cart_value=500,
            items_in_cart=3,
        )
        result = _fallback_classify(event)
        assert result.failure_category == "high_intent_abandonment"
        assert result.recommended_channel == "whatsapp"
        assert result.recommended_timing == "1_hour"

    def test_low_value_cart(self):
        event = RecoveryEventInput(
            event_type="cart_abandonment",
            amount=0,
            cart_value=50,
        )
        result = _fallback_classify(event)
        assert result.failure_category == "browse_only_abandonment"
        assert result.recommended_channel == "none"


class TestFallbackClassifyInvoiceOverdue:
    def test_recently_overdue(self):
        event = RecoveryEventInput(
            event_type="invoice_overdue",
            amount=1000,
            days_overdue=3,
        )
        result = _fallback_classify(event)
        assert result.failure_category == "recently_overdue"
        assert result.recommended_channel == "whatsapp"
        assert result.recovery_probability == 0.70

    def test_moderately_overdue(self):
        event = RecoveryEventInput(
            event_type="invoice_overdue",
            amount=1000,
            days_overdue=15,
        )
        result = _fallback_classify(event)
        assert result.failure_category == "moderately_overdue"
        assert result.recommended_channel == "email"

    def test_long_overdue(self):
        event = RecoveryEventInput(
            event_type="invoice_overdue",
            amount=1000,
            days_overdue=45,
        )
        result = _fallback_classify(event)
        assert result.failure_category == "long_overdue"
        assert result.recovery_probability == 0.15

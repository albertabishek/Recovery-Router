"""Unit tests for message_generator.py — fallback messages, render_email_html, _safe_url, AI orchestration."""
import pytest
from unittest.mock import patch
from app.services.message_generator import (
    generate_personalized_messages, _fallback_messages,
    render_email_html, _safe_url,
)


class TestSafeUrl:
    def test_valid_https(self):
        assert "https://pay.razorpay.com/abc" in _safe_url("https://pay.razorpay.com/abc")

    def test_valid_http(self):
        assert "http://example.com" in _safe_url("http://example.com")

    def test_invalid_protocol_returns_hash(self):
        assert _safe_url("javascript:alert(1)") == "#"

    def test_empty_returns_hash(self):
        assert _safe_url("") == "#"

    def test_none_like_returns_hash(self):
        assert _safe_url("ftp://bad.com") == "#"

    def test_escapes_html_entities(self):
        result = _safe_url("https://example.com/?a=1&b=2")
        assert "&amp;" in result


class TestFallbackMessages:
    def test_first_attempt(self):
        r = _fallback_messages("Ravi", 499, "INR", "upi_timeout", 0)
        assert "Ravi" in r["whatsapp_text"]
        assert "499" in r["whatsapp_text"]
        assert "{link}" in r["whatsapp_text"]
        assert "{link}" in r["sms_text"]
        assert r["email_cta_text"] == "Complete Payment"

    def test_followup_attempt(self):
        r = _fallback_messages("Priya", 1000, "INR", "card_expired", 1)
        assert "reminder" in r["whatsapp_text"].lower()
        assert "pending" in r["sms_text"].lower()
        assert "Reminder" in r["email_subject"]

    def test_uses_currency_and_amount(self):
        r = _fallback_messages("Test", 5000, "USD", "gateway_error", 0)
        assert "USD" in r["sms_text"]
        assert "5,000" in r["sms_text"]

    def test_greeting_format(self):
        r = _fallback_messages("Alice", 100, "INR", "gateway_error", 0)
        assert r["email_greeting"] == "Hi Alice,"


class TestRenderEmailHtml:
    def test_contains_link(self):
        msgs = _fallback_messages("Test", 499, "INR", "upi_timeout", 0)
        html = render_email_html(msgs, "https://rzp.io/abc")
        assert "https://rzp.io/abc" in html

    def test_escapes_xss_in_subject(self):
        msgs = {"email_subject": "<script>alert(1)</script>",
                "email_greeting": "Hi", "email_body": "body",
                "email_cta_text": "Pay"}
        html = render_email_html(msgs, "https://pay.com")
        assert "<script>alert(1)</script>" not in html

    def test_unsafe_link_becomes_hash(self):
        msgs = _fallback_messages("Test", 100, "INR", "gateway_error", 0)
        html = render_email_html(msgs, "javascript:alert(1)")
        assert 'href="#"' in html

    def test_structure_has_recovery_router(self):
        msgs = _fallback_messages("Test", 100, "INR", "gateway_error", 0)
        html = render_email_html(msgs, "https://rzp.io/x")
        assert "Recovery Router" in html


class TestGeneratePersonalizedMessages:
    @patch("app.services.message_generator.ai_call")
    def test_uses_ai_when_available(self, mock_ai):
        mock_ai.return_value = {
            "whatsapp_text": "AI whatsapp",
            "sms_text": "AI sms",
            "email_subject": "AI subject",
            "email_greeting": "Hey",
            "email_body": "AI body",
            "email_cta_text": "Pay Now",
        }
        r = generate_personalized_messages(
            channel="whatsapp", customer_name="Test User",
            amount=499, currency="INR", failure_category="upi_timeout",
        )
        assert r["whatsapp_text"] == "AI whatsapp"

    @patch("app.services.message_generator.ai_call", return_value=None)
    def test_falls_back_when_ai_unavailable(self, mock_ai):
        r = generate_personalized_messages(
            channel="whatsapp", customer_name="Test User",
            amount=499, currency="INR", failure_category="upi_timeout",
        )
        assert "{link}" in r["whatsapp_text"]
        assert "Test" in r["whatsapp_text"]

    @patch("app.services.message_generator.ai_call", return_value=None)
    def test_none_name_uses_there(self, mock_ai):
        r = generate_personalized_messages(
            channel="email", customer_name=None,
            amount=100, currency="INR", failure_category="gateway_error",
        )
        assert "there" in r["whatsapp_text"]

    @patch("app.services.message_generator.ai_call", return_value=None)
    def test_full_name_uses_first_name(self, mock_ai):
        r = generate_personalized_messages(
            channel="email", customer_name="Ravi Kumar",
            amount=100, currency="INR", failure_category="gateway_error",
        )
        assert "Ravi" in r["whatsapp_text"]
        assert "Kumar" not in r["whatsapp_text"]

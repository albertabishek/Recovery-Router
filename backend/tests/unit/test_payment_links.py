"""Unit tests for generate_payment_link edge cases."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.payment_links import generate_payment_link
from datetime import datetime, timezone


class TestZeroAmountGuard:
    def test_skips_zero_amount(self):
        result = generate_payment_link(
            amount=0, currency="INR", customer_name="Test",
            customer_email=None, customer_phone=None,
            order_id=None, event_type="payment_failure",
            failure_category="unknown", event_id=1,
            recovery_window_ends=None,
        )
        assert result["status"] == "skipped"
        assert result["short_url"] is None

    def test_skips_negative_amount(self):
        result = generate_payment_link(
            amount=-100, currency="INR", customer_name="Test",
            customer_email=None, customer_phone=None,
            order_id=None, event_type="payment_failure",
            failure_category="unknown", event_id=1,
            recovery_window_ends=None,
        )
        assert result["status"] == "skipped"


class TestApiErrorHandling:
    @patch("app.services.payment_links.get_redis")
    @patch("app.services.payment_links.httpx.post")
    def test_handles_api_error_status(self, mock_post, mock_redis):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_post.return_value = mock_resp

        result = generate_payment_link(
            amount=499, currency="INR", customer_name="Test",
            customer_email="t@t.com", customer_phone="+919999999999",
            order_id="ord_1", event_type="payment_failure",
            failure_category="gateway_error", event_id=1,
            recovery_window_ends=None,
        )
        assert result["status"] == "api_error"
        assert result["short_url"] is None

    @patch("app.services.payment_links.httpx.post")
    def test_handles_network_exception(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")

        result = generate_payment_link(
            amount=499, currency="INR", customer_name="Test",
            customer_email=None, customer_phone=None,
            order_id=None, event_type="payment_failure",
            failure_category="unknown", event_id=1,
            recovery_window_ends=None,
        )
        assert result["status"] == "error"
        assert result["short_url"] is None


class TestSuccessfulCreation:
    @patch("app.services.payment_links._store_checkout_context", return_value="tok_abc123")
    @patch("app.services.payment_links.httpx.post")
    def test_creates_order_and_returns_url(self, mock_post, mock_store):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "order_rzp_abc"}
        mock_post.return_value = mock_resp

        result = generate_payment_link(
            amount=499, currency="INR", customer_name="Test",
            customer_email="t@t.com", customer_phone="+91999",
            order_id="orig_ord", event_type="payment_failure",
            failure_category="card_expired", event_id=42,
            recovery_window_ends=None,
        )
        assert result["status"] == "created"
        assert result["id"] == "order_rzp_abc"
        assert "order_rzp_abc" in result["short_url"]
        assert "tok_abc123" in result["short_url"]

    @patch("app.services.payment_links._store_checkout_context", return_value="tok_123")
    @patch("app.services.payment_links.httpx.post")
    def test_amount_converted_to_paise(self, mock_post, mock_store):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "order_1"}
        mock_post.return_value = mock_resp

        generate_payment_link(
            amount=499.50, currency="INR", customer_name="Test",
            customer_email=None, customer_phone=None,
            order_id=None, event_type="payment_failure",
            failure_category="unknown", event_id=1,
            recovery_window_ends=None,
        )
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["amount"] == 49950

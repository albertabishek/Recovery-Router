"""Unit tests for dedup.py — is_duplicate, get_dedup_identifier, _hash_payload."""
import pytest
from unittest.mock import patch, MagicMock
from app.utils.dedup import is_duplicate, get_dedup_identifier, _hash_payload


class TestHashPayload:
    def test_deterministic(self):
        body = {"a": 1, "b": "two"}
        assert _hash_payload(body) == _hash_payload(body)

    def test_starts_with_hash_prefix(self):
        assert _hash_payload({"x": 1}).startswith("hash_")

    def test_length_is_consistent(self):
        h = _hash_payload({"key": "value"})
        assert len(h) == 5 + 16  # "hash_" + 16 hex chars

    def test_different_payloads_differ(self):
        assert _hash_payload({"a": 1}) != _hash_payload({"a": 2})

    def test_key_order_irrelevant(self):
        assert _hash_payload({"a": 1, "b": 2}) == _hash_payload({"b": 2, "a": 1})


class TestGetDedupIdentifier:
    def test_payment_failed_event_uses_entity_id(self):
        body = {
            "event": "payment.failed",
            "payload": {"payment": {"entity": {"id": "pay_123"}}},
        }
        assert get_dedup_identifier(body) == "pay_123"

    def test_payment_failed_empty_id_falls_to_hash(self):
        body = {
            "event": "payment.failed",
            "payload": {"payment": {"entity": {"id": ""}}},
        }
        assert get_dedup_identifier(body).startswith("hash_")

    def test_uses_payment_id(self):
        assert get_dedup_identifier({"payment_id": "pay_abc"}) == "pay_abc"

    def test_uses_order_id(self):
        assert get_dedup_identifier({"order_id": "order_xyz"}) == "order_xyz"

    def test_uses_invoice_id(self):
        assert get_dedup_identifier({"invoice_id": "inv_1"}) == "inv_1"

    def test_priority_payment_over_order(self):
        assert get_dedup_identifier({"payment_id": "pay_1", "order_id": "ord_2"}) == "pay_1"

    def test_falls_to_hash_when_no_id(self):
        assert get_dedup_identifier({"foo": "bar"}).startswith("hash_")


class TestIsDuplicate:
    @patch("app.utils.dedup.get_redis")
    def test_first_call_not_duplicate(self, mock_redis_fn):
        mock_r = MagicMock()
        mock_r.set.return_value = True  # nx=True succeeds → key was new
        mock_redis_fn.return_value = mock_r
        assert is_duplicate("payment_failure", "pay_123") is False

    @patch("app.utils.dedup.get_redis")
    def test_second_call_is_duplicate(self, mock_redis_fn):
        mock_r = MagicMock()
        mock_r.set.return_value = False  # nx=True fails → key already exists
        mock_redis_fn.return_value = mock_r
        assert is_duplicate("payment_failure", "pay_123") is True

    @patch("app.utils.dedup.get_redis")
    def test_uses_correct_key_format(self, mock_redis_fn):
        mock_r = MagicMock()
        mock_r.set.return_value = True
        mock_redis_fn.return_value = mock_r
        is_duplicate("cart_abandonment", "cart_42")
        mock_r.set.assert_called_once_with("dedup:cart_abandonment:cart_42", "1", nx=True, ex=3600)

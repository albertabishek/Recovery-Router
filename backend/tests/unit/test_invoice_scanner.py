"""Unit tests for invoice_scanner.py — fetch_overdue_invoices, _already_tracked_batch."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.invoice_scanner import fetch_overdue_invoices, _already_tracked_batch
import time


class TestAlreadyTrackedBatch:
    @patch("app.services.invoice_scanner.get_supabase")
    def test_empty_list_returns_empty_set(self, mock_sb_fn):
        assert _already_tracked_batch([]) == set()

    @patch("app.services.invoice_scanner.get_supabase")
    def test_returns_tracked_ids(self, mock_sb_fn):
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"invoice_id": "inv_1"}, {"invoice_id": "inv_3"}]
        mock_sb.table().select().in_().execute.return_value = mock_result
        mock_sb_fn.return_value = mock_sb
        result = _already_tracked_batch(["inv_1", "inv_2", "inv_3"])
        assert result == {"inv_1", "inv_3"}

    @patch("app.services.invoice_scanner.get_supabase")
    def test_none_data_returns_empty(self, mock_sb_fn):
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = None
        mock_sb.table().select().in_().execute.return_value = mock_result
        mock_sb_fn.return_value = mock_sb
        result = _already_tracked_batch(["inv_1"])
        assert result == set()


class TestFetchOverdueInvoices:
    @patch("app.services.invoice_scanner._already_tracked_batch", return_value=set())
    @patch("app.services.invoice_scanner.httpx.get")
    def test_fetches_and_converts_invoices(self, mock_get, mock_tracked):
        now_ts = int(time.time())
        five_days_ago = now_ts - (5 * 86400)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [{
                "id": "inv_100",
                "amount": 50000,
                "currency": "INR",
                "due_date": five_days_ago,
                "customer_details": {
                    "name": "Test User",
                    "email": "test@test.com",
                    "contact": "+919999999999",
                },
            }]
        }
        mock_get.return_value = mock_resp

        events = fetch_overdue_invoices()
        assert len(events) == 1
        assert events[0]["event_type"] == "invoice_overdue"
        assert events[0]["amount"] == 500.0  # 50000 paise / 100
        assert events[0]["days_overdue"] >= 4

    @patch("app.services.invoice_scanner.httpx.get")
    def test_api_error_returns_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        events = fetch_overdue_invoices()
        assert events == []

    @patch("app.services.invoice_scanner.httpx.get", side_effect=Exception("Network error"))
    def test_exception_returns_empty(self, mock_get):
        events = fetch_overdue_invoices()
        assert events == []

    @patch("app.services.invoice_scanner._already_tracked_batch", return_value={"inv_tracked"})
    @patch("app.services.invoice_scanner.httpx.get")
    def test_skips_already_tracked(self, mock_get, mock_tracked):
        now_ts = int(time.time())
        five_days_ago = now_ts - (5 * 86400)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [{
                "id": "inv_tracked",
                "amount": 10000,
                "currency": "INR",
                "due_date": five_days_ago,
                "customer_details": {"name": "Tracked"},
            }]
        }
        mock_get.return_value = mock_resp

        events = fetch_overdue_invoices()
        assert len(events) == 0

    @patch("app.services.invoice_scanner._already_tracked_batch", return_value=set())
    @patch("app.services.invoice_scanner.httpx.get")
    def test_skips_not_yet_overdue(self, mock_get, mock_tracked):
        future_ts = int(time.time()) + 86400  # due tomorrow
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [{
                "id": "inv_future",
                "amount": 10000,
                "currency": "INR",
                "due_date": future_ts,
                "customer_details": {"name": "Future"},
            }]
        }
        mock_get.return_value = mock_resp

        events = fetch_overdue_invoices()
        assert len(events) == 0

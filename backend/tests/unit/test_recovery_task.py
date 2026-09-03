"""Unit tests for recovery.py — _check_durable_dedup, _is_quiet_hours, handle_recovery_retry_failure."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from app.tasks.recovery import _check_durable_dedup, _is_quiet_hours
from app.models import RecoveryEventInput


class TestCheckDurableDedup:
    def _make_event(self, **kwargs):
        defaults = {"event_type": "payment_failure", "amount": 499}
        defaults.update(kwargs)
        return RecoveryEventInput(**defaults)

    def test_payment_id_duplicate(self):
        sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": 42}]
        sb.table().select().eq().limit().execute.return_value = mock_result

        event = self._make_event(payment_id="pay_real_123")
        result = _check_durable_dedup(sb, event)
        assert result is not None
        assert result["id"] == 42
        assert "payment_id" in result["match"]

    def test_no_duplicate(self):
        sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        sb.table().select().eq().limit().execute.return_value = mock_result

        event = self._make_event(payment_id="pay_new")
        result = _check_durable_dedup(sb, event)
        assert result is None

    def test_skips_test_payment_id(self):
        sb = MagicMock()
        event = self._make_event(payment_id="pay_TEST_sim123")
        result = _check_durable_dedup(sb, event)
        assert result is None

    def test_skips_test_order_id(self):
        sb = MagicMock()
        event = self._make_event(order_id="order_TEST_sim456")
        result = _check_durable_dedup(sb, event)
        assert result is None

    def test_order_id_duplicate(self):
        sb = MagicMock()
        mock_result_empty = MagicMock()
        mock_result_empty.data = []
        mock_result_found = MagicMock()
        mock_result_found.data = [{"id": 99}]
        sb.table().select().eq().limit().execute.side_effect = [mock_result_empty, mock_result_found]

        event = self._make_event(payment_id="pay_new", order_id="order_real_789")
        result = _check_durable_dedup(sb, event)
        assert result is not None
        assert result["id"] == 99

    def test_invoice_id_duplicate(self):
        sb = MagicMock()
        mock_result_empty = MagicMock()
        mock_result_empty.data = []
        mock_result_found = MagicMock()
        mock_result_found.data = [{"id": 77}]
        sb.table().select().eq().limit().execute.side_effect = [mock_result_found]

        event = self._make_event(invoice_id="inv_123")
        result = _check_durable_dedup(sb, event)
        assert result is not None

    def test_no_ids_returns_none(self):
        sb = MagicMock()
        event = self._make_event()
        result = _check_durable_dedup(sb, event)
        assert result is None


class TestIsQuietHours:
    def test_quiet_at_10pm_ist(self):
        dt = datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)  # 10 PM IST
        assert _is_quiet_hours(dt) is True

    def test_quiet_at_3am_ist(self):
        dt = datetime(2026, 1, 1, 21, 30, tzinfo=timezone.utc)  # 3 AM IST
        assert _is_quiet_hours(dt) is True

    def test_not_quiet_at_2pm_ist(self):
        dt = datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc)  # 2 PM IST
        assert _is_quiet_hours(dt) is False

    def test_not_quiet_at_noon_ist(self):
        dt = datetime(2026, 1, 1, 6, 30, tzinfo=timezone.utc)  # 12 PM IST
        assert _is_quiet_hours(dt) is False

    def test_boundary_9am_ist_not_quiet(self):
        dt = datetime(2026, 1, 1, 3, 30, tzinfo=timezone.utc)  # 9 AM IST
        assert _is_quiet_hours(dt) is False

    def test_boundary_9pm_ist_is_quiet(self):
        dt = datetime(2026, 1, 1, 15, 30, tzinfo=timezone.utc)  # 9 PM IST
        assert _is_quiet_hours(dt) is True

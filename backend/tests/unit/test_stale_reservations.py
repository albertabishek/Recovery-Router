"""Unit tests for _cleanup_stale_reservations in escalation."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.escalation import _cleanup_stale_reservations


class FakeResult:
    def __init__(self, data):
        self.data = data


class TestStaleReservationCleanup:
    def test_marks_stale_rows_as_failed(self):
        sb = MagicMock()
        update_chain = MagicMock()
        update_chain.execute.return_value = FakeResult([
            {"id": 1, "outcome": "failed"},
            {"id": 2, "outcome": "failed"},
        ])
        update_chain.eq = MagicMock(return_value=update_chain)
        update_chain.lt = MagicMock(return_value=update_chain)
        sb.table.return_value.update.return_value = update_chain

        _cleanup_stale_reservations(sb)

        sb.table.assert_called_with("recovery_attempts")
        sb.table.return_value.update.assert_called_once()
        call_args = sb.table.return_value.update.call_args[0][0]
        assert call_args["outcome"] == "failed"
        assert "Stale reservation" in call_args["notes"]

    def test_no_stale_rows_no_error(self):
        sb = MagicMock()
        update_chain = MagicMock()
        update_chain.execute.return_value = FakeResult([])
        update_chain.eq = MagicMock(return_value=update_chain)
        update_chain.lt = MagicMock(return_value=update_chain)
        sb.table.return_value.update.return_value = update_chain

        _cleanup_stale_reservations(sb)

    def test_db_error_does_not_propagate(self):
        sb = MagicMock()
        sb.table.return_value.update.side_effect = Exception("DB down")

        _cleanup_stale_reservations(sb)


class TestCleanupFilters:
    def test_filters_on_reserved_outcome(self):
        sb = MagicMock()
        update_chain = MagicMock()
        update_chain.execute.return_value = FakeResult([])
        update_chain.eq = MagicMock(return_value=update_chain)
        update_chain.lt = MagicMock(return_value=update_chain)
        sb.table.return_value.update.return_value = update_chain

        _cleanup_stale_reservations(sb)

        update_chain.eq.assert_called_once_with("outcome", "reserved")

    def test_uses_created_at_cutoff(self):
        sb = MagicMock()
        update_chain = MagicMock()
        update_chain.execute.return_value = FakeResult([])
        update_chain.eq = MagicMock(return_value=update_chain)
        update_chain.lt = MagicMock(return_value=update_chain)
        sb.table.return_value.update.return_value = update_chain

        _cleanup_stale_reservations(sb)

        update_chain.lt.assert_called_once()
        args = update_chain.lt.call_args[0]
        assert args[0] == "created_at"

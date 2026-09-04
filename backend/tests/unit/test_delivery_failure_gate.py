"""Unit tests for delivery_failure_count exhaustion gate in escalation.

Tests the logic that stops infinite retries on unreachable contacts.
"""
import pytest
from unittest.mock import patch, MagicMock, call
from app.services.escalation import run_escalation


class FakeResult:
    def __init__(self, data):
        self.data = data


def _make_event(event_id=1, delivery_failure_count=0, max_attempts=5, attempt_count=1):
    return {
        "id": event_id,
        "status": "pending",
        "amount": 499,
        "currency": "INR",
        "customer_name": "Test",
        "customer_email": "test@test.com",
        "customer_phone": "+919999999999",
        "event_type": "payment_failure",
        "failure_category": "gateway_error",
        "attempt_count": attempt_count,
        "max_attempts": max_attempts,
        "escalation_level": attempt_count,
        "delivery_failure_count": delivery_failure_count,
        "order_id": "order_test1",
        "recovery_window_ends": None,
        "personalization_hint": None,
    }


def _mock_sb_for_gate_test(event, attempts_data, expect_exhaustion=False):
    sb = MagicMock()

    fresh_result = FakeResult([{
        "status": "pending",
        "attempt_count": event["attempt_count"],
        "max_attempts": event["max_attempts"],
        "escalation_level": event.get("escalation_level", 0),
        "delivery_failure_count": event["delivery_failure_count"],
    }])

    attempts_result = FakeResult(attempts_data)

    select_chain = MagicMock()
    select_chain.execute.side_effect = [fresh_result, attempts_result]
    select_chain.select = MagicMock(return_value=select_chain)
    select_chain.eq = MagicMock(return_value=select_chain)
    select_chain.in_ = MagicMock(return_value=select_chain)
    select_chain.lt = MagicMock(return_value=select_chain)
    select_chain.limit = MagicMock(return_value=select_chain)
    select_chain.order = MagicMock(return_value=select_chain)

    update_chain = MagicMock()
    update_chain.execute.return_value = FakeResult([{"id": event["id"]}])
    update_chain.eq = MagicMock(return_value=update_chain)
    update_chain.in_ = MagicMock(return_value=update_chain)

    sb.table.return_value = MagicMock(
        select=MagicMock(return_value=select_chain),
        update=MagicMock(return_value=update_chain),
    )
    return sb


class TestDeliveryFailureGate:
    @patch("app.services.escalation._cleanup_stale_reservations")
    @patch("app.services.escalation._release_event_lock")
    @patch("app.services.escalation._acquire_event_lock", return_value=True)
    @patch("app.services.escalation.get_supabase")
    def test_exhausts_unreachable_contact(self, mock_sb, mock_lock, mock_unlock, mock_cleanup):
        event = _make_event(delivery_failure_count=6, max_attempts=5)
        attempts = [
            {"outcome": "failed", "channel_used": "whatsapp"},
            {"outcome": "failed", "channel_used": "email"},
            {"outcome": "failed", "channel_used": "sms"},
        ]
        sb = _mock_sb_for_gate_test(event, attempts, expect_exhaustion=True)
        mock_sb.return_value = sb

        results = run_escalation([event])
        assert len(results) == 1
        assert results[0]["action"] == "exhausted_unreachable"

    @patch("app.services.escalation._cleanup_stale_reservations")
    @patch("app.services.escalation._release_event_lock")
    @patch("app.services.escalation._acquire_event_lock", return_value=True)
    @patch("app.services.escalation.get_supabase")
    def test_continues_if_some_sent(self, mock_sb, mock_lock, mock_unlock, mock_cleanup):
        event = _make_event(delivery_failure_count=6, max_attempts=5)
        attempts = [
            {"outcome": "sent", "channel_used": "whatsapp"},
            {"outcome": "failed", "channel_used": "email"},
        ]
        sb = MagicMock()
        mock_sb.return_value = sb

        fresh_result = FakeResult([{
            "status": "pending",
            "attempt_count": 1,
            "max_attempts": 5,
            "escalation_level": 1,
            "delivery_failure_count": 6,
        }])
        attempts_result = FakeResult(attempts)

        select_chain = MagicMock()
        select_chain.execute.side_effect = [fresh_result, attempts_result]
        select_chain.select = MagicMock(return_value=select_chain)
        select_chain.eq = MagicMock(return_value=select_chain)
        select_chain.in_ = MagicMock(return_value=select_chain)
        select_chain.limit = MagicMock(return_value=select_chain)
        select_chain.order = MagicMock(return_value=select_chain)
        sb.table.return_value = select_chain

        with patch("app.services.escalation._get_escalation_decision") as mock_decision:
            mock_decision.return_value = {"action": "send", "channel": "sms", "tone": "firm", "reasoning": "test"}
            with patch("app.services.escalation._reserve_attempt") as mock_reserve:
                mock_reserve.return_value = (3, "1:escalation:3")
                with patch("app.services.escalation.generate_payment_link") as mock_link:
                    mock_link.return_value = {"id": "ord_1", "short_url": "http://test"}
                    with patch("app.services.escalation.send_message") as mock_send:
                        mock_send.return_value = {"success": True, "message_id": "m1"}
                        with patch("app.services.escalation._finalize_attempt"):
                            with patch("app.services.escalation._update_event_state"):
                                results = run_escalation([event])

        assert len(results) == 1
        assert results[0]["action"] != "exhausted_unreachable"

    @patch("app.services.escalation._cleanup_stale_reservations")
    @patch("app.services.escalation._release_event_lock")
    @patch("app.services.escalation._acquire_event_lock", return_value=True)
    @patch("app.services.escalation.get_supabase")
    def test_no_exhaustion_below_threshold(self, mock_sb, mock_lock, mock_unlock, mock_cleanup):
        event = _make_event(delivery_failure_count=3, max_attempts=5)
        attempts = [{"outcome": "failed", "channel_used": "whatsapp"}]

        sb = MagicMock()
        mock_sb.return_value = sb

        fresh_result = FakeResult([{
            "status": "pending",
            "attempt_count": 1,
            "max_attempts": 5,
            "escalation_level": 1,
            "delivery_failure_count": 3,
        }])
        attempts_result = FakeResult(attempts)

        select_chain = MagicMock()
        select_chain.execute.side_effect = [fresh_result, attempts_result]
        select_chain.select = MagicMock(return_value=select_chain)
        select_chain.eq = MagicMock(return_value=select_chain)
        select_chain.in_ = MagicMock(return_value=select_chain)
        select_chain.limit = MagicMock(return_value=select_chain)
        select_chain.order = MagicMock(return_value=select_chain)
        sb.table.return_value = select_chain

        with patch("app.services.escalation._is_quiet_hours", return_value=False):
            with patch("app.services.escalation._get_escalation_decision") as mock_decision:
                mock_decision.return_value = {"action": "send", "channel": "email", "tone": "firm", "reasoning": "test"}
                with patch("app.services.escalation._reserve_attempt") as mock_reserve:
                    mock_reserve.return_value = (2, "1:escalation:2")
                    with patch("app.services.escalation.generate_payment_link") as mock_link:
                        mock_link.return_value = {"id": "ord_1", "short_url": "http://test"}
                        with patch("app.services.escalation.send_message") as mock_send:
                            mock_send.return_value = {"success": True, "message_id": "m2"}
                            with patch("app.services.escalation._finalize_attempt"):
                                with patch("app.services.escalation._update_event_state"):
                                    results = run_escalation([event])

        assert results[0]["action"] == "sent"

    @patch("app.services.escalation._cleanup_stale_reservations")
    @patch("app.services.escalation._release_event_lock")
    @patch("app.services.escalation._acquire_event_lock", return_value=True)
    @patch("app.services.escalation.get_supabase")
    def test_skips_payment_link_and_system_channels(self, mock_sb, mock_lock, mock_unlock, mock_cleanup):
        """payment_link and system channel outcomes don't count as successful sends."""
        event = _make_event(delivery_failure_count=6, max_attempts=5)
        attempts = [
            {"outcome": "sent", "channel_used": "payment_link"},
            {"outcome": "sent", "channel_used": "system"},
            {"outcome": "failed", "channel_used": "whatsapp"},
        ]
        sb = _mock_sb_for_gate_test(event, attempts, expect_exhaustion=True)
        mock_sb.return_value = sb

        results = run_escalation([event])
        assert results[0]["action"] == "exhausted_unreachable"

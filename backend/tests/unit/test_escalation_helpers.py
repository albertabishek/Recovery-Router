"""Unit tests for escalation.py — helper functions."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from app.services.escalation import (
    _pick_next_channel, _parse_datetime, _mark_exhausted,
    _update_event_state, _finalize_attempt, _is_quiet_hours,
    _get_escalation_decision,
)


class TestPickNextChannel:
    def test_rotates_from_whatsapp_to_email(self):
        event = {"customer_phone": "+91999", "customer_email": "t@t.com"}
        assert _pick_next_channel("whatsapp", event) == "email"

    def test_rotates_from_email_to_whatsapp(self):
        event = {"customer_phone": "+91999", "customer_email": "t@t.com"}
        assert _pick_next_channel("email", event) == "whatsapp"

    def test_avoids_blocked_channel(self):
        event = {"customer_phone": "+91999", "customer_email": "t@t.com"}
        assert _pick_next_channel("whatsapp", event, avoid={"email"}) == "sms"

    def test_phone_only(self):
        event = {"customer_phone": "+91999"}
        assert _pick_next_channel("whatsapp", event) in ("sms", "whatsapp")

    def test_email_only(self):
        event = {"customer_email": "t@t.com"}
        assert _pick_next_channel("email", event) == "email"

    def test_all_avoided_falls_back(self):
        event = {"customer_phone": "+91999", "customer_email": "t@t.com"}
        result = _pick_next_channel("whatsapp", event, avoid={"whatsapp", "email", "sms"})
        assert result in ("email", "whatsapp")

    def test_none_last_channel(self):
        event = {"customer_phone": "+91999", "customer_email": "t@t.com"}
        result = _pick_next_channel(None, event)
        assert result in ("whatsapp", "email", "sms")

    def test_no_contact_info_fallback(self):
        event = {}
        result = _pick_next_channel("whatsapp", event)
        assert result in ("email", "whatsapp")


class TestParseDatetime:
    def test_valid_iso(self):
        dt = _parse_datetime("2026-01-01T12:00:00+00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_none_returns_none(self):
        assert _parse_datetime(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_datetime("") is None

    def test_invalid_format_returns_none(self):
        assert _parse_datetime("not-a-date") is None

    def test_int_returns_none(self):
        assert _parse_datetime(12345) is None


class TestMarkExhausted:
    def test_marks_event_exhausted(self):
        sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": 1}]
        sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result

        event = {"id": 1, "max_attempts": 3}
        _mark_exhausted(sb, event, "All attempts used")
        call_args = sb.table.return_value.update.call_args[0][0]
        assert call_args["status"] == "exhausted"
        assert "All attempts used" in call_args["skip_reason"]

    def test_default_reason(self):
        sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": 1}]
        sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result

        event = {"id": 1, "max_attempts": 5}
        _mark_exhausted(sb, event)
        call_args = sb.table.return_value.update.call_args[0][0]
        assert "5" in call_args["skip_reason"]


class TestFinalizeAttempt:
    def test_success(self):
        sb = MagicMock()
        send_result = {"success": True, "message_id": "m1", "channel_used": "whatsapp"}
        link = {"id": "link1", "short_url": "https://rzp.io/x"}
        event = {"escalation_level": 1}
        _finalize_attempt(sb, "key1", "whatsapp", send_result, link, event)
        call_args = sb.table().update.call_args[0][0]
        assert call_args["outcome"] == "sent"
        assert call_args["message_id"] == "m1"

    def test_failure(self):
        sb = MagicMock()
        send_result = {"success": False, "error": "Provider down"}
        link = {"id": "link1", "short_url": "https://rzp.io/x"}
        event = {"escalation_level": 0}
        _finalize_attempt(sb, "key2", "email", send_result, link, event)
        call_args = sb.table().update.call_args[0][0]
        assert call_args["outcome"] == "failed"

    def test_cooldown_blocked(self):
        sb = MagicMock()
        send_result = {"success": False, "error": "Cooldown active"}
        link = {"id": "link1", "short_url": "https://rzp.io/x"}
        event = {"escalation_level": 0}
        _finalize_attempt(sb, "key3", "sms", send_result, link, event)
        call_args = sb.table().update.call_args[0][0]
        assert call_args["outcome"] == "blocked"

    def test_exception_doesnt_propagate(self):
        sb = MagicMock()
        sb.table().update().eq().execute.side_effect = Exception("DB down")
        send_result = {"success": True, "message_id": "m1"}
        link = {"id": "link1", "short_url": "url"}
        event = {"escalation_level": 0}
        _finalize_attempt(sb, "key4", "email", send_result, link, event)


class TestUpdateEventState:
    def test_increments_attempt_count(self):
        sb = MagicMock()
        event = {"id": 1, "attempt_count": 1, "escalation_level": 1,
                 "max_attempts": 5, "failure_category": "upi_timeout"}
        decision = {"tone": "firm"}
        _update_event_state(sb, event, decision)
        call_args = sb.table().update.call_args[0][0]
        assert call_args["attempt_count"] == 2
        assert call_args["escalation_level"] == 2

    def test_exhausts_at_max(self):
        sb = MagicMock()
        event = {"id": 1, "attempt_count": 4, "escalation_level": 4,
                 "max_attempts": 5, "failure_category": "gateway_error"}
        decision = {"tone": "final"}
        _update_event_state(sb, event, decision)
        call_args = sb.table().update.call_args[0][0]
        assert call_args["status"] == "exhausted"


class TestIsQuietHoursEscalation:
    def test_quiet_at_10pm_ist(self):
        dt = datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)
        assert _is_quiet_hours(dt) is True

    def test_not_quiet_at_2pm_ist(self):
        dt = datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc)
        assert _is_quiet_hours(dt) is False


class TestGetEscalationDecision:
    def test_max_attempts_reached_gives_up(self):
        event = {"id": 1, "attempt_count": 5, "max_attempts": 5}
        result = _get_escalation_decision(event, [])
        assert result["action"] == "give_up"

    @patch("app.services.escalation.ai_call", return_value=None)
    def test_fallback_rotates_channels(self, mock_ai):
        event = {"id": 1, "attempt_count": 0, "max_attempts": 5,
                 "customer_email": "t@t.com", "customer_phone": "+91999"}
        result = _get_escalation_decision(event, [])
        assert result["action"] == "send"
        assert result["channel"] == "whatsapp"

    @patch("app.services.escalation.ai_call", return_value=None)
    def test_fallback_second_attempt_email(self, mock_ai):
        event = {"id": 1, "attempt_count": 1, "max_attempts": 5}
        result = _get_escalation_decision(event, [])
        assert result["channel"] == "email"

    @patch("app.services.escalation.ai_call")
    def test_ai_give_up_overridden_when_budget_remains(self, mock_ai):
        mock_ai.return_value = {
            "action": "give_up", "channel": "none", "tone": "final",
            "reasoning": "AI wants to stop",
        }
        event = {"id": 1, "attempt_count": 1, "max_attempts": 5,
                 "customer_phone": "+91999", "customer_email": "t@t.com"}
        attempts = [{"channel_used": "whatsapp", "outcome": "sent", "attempt_number": 1}]
        result = _get_escalation_decision(event, attempts)
        assert result["action"] == "send"

    @patch("app.services.escalation.ai_call")
    def test_ai_send_respected(self, mock_ai):
        mock_ai.return_value = {
            "action": "send", "channel": "sms", "tone": "firm",
            "reasoning": "Try SMS next",
        }
        event = {"id": 1, "attempt_count": 1, "max_attempts": 5}
        result = _get_escalation_decision(event, [])
        assert result["action"] == "send"
        assert result["channel"] == "sms"

from datetime import datetime, timezone
from app.tasks.recovery import _is_quiet_hours as recovery_is_quiet
from app.services.escalation import _is_quiet_hours as escalation_is_quiet


def _utc(hour, minute=30):
    return datetime(2025, 6, 15, hour, minute, 0, tzinfo=timezone.utc)


class TestRecoveryQuietHours:
    def test_10pm_ist_is_quiet(self):
        # 10 PM IST = 4:30 PM UTC
        assert recovery_is_quiet(_utc(16, 30)) is True

    def test_3am_ist_is_quiet(self):
        # 3 AM IST = 9:30 PM UTC (previous day)
        assert recovery_is_quiet(_utc(21, 30)) is True

    def test_8am_ist_is_quiet(self):
        # 8 AM IST = 2:30 AM UTC
        assert recovery_is_quiet(_utc(2, 30)) is True

    def test_10am_ist_is_not_quiet(self):
        # 10 AM IST = 4:30 AM UTC
        assert recovery_is_quiet(_utc(4, 30)) is False

    def test_2pm_ist_is_not_quiet(self):
        # 2 PM IST = 8:30 AM UTC
        assert recovery_is_quiet(_utc(8, 30)) is False

    def test_9am_ist_boundary_not_quiet(self):
        # 9:00 AM IST = 3:30 AM UTC
        assert recovery_is_quiet(_utc(3, 30)) is False

    def test_9pm_ist_boundary_is_quiet(self):
        # 9 PM IST = 3:30 PM UTC
        assert recovery_is_quiet(_utc(15, 30)) is True


class TestEscalationQuietHours:
    def test_10pm_ist_is_quiet(self):
        assert escalation_is_quiet(_utc(16, 30)) is True

    def test_10am_ist_is_not_quiet(self):
        assert escalation_is_quiet(_utc(4, 30)) is False

    def test_default_uses_current_time(self):
        result = escalation_is_quiet()
        assert isinstance(result, bool)

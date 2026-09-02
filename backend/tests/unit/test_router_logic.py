import pytest
from app.models import ClassificationResult, ActionPlan
from app.services.router import route_action, compute_max_attempts


class TestComputeMaxAttempts:
    def test_unrecoverable_zero(self):
        assert compute_max_attempts(5000, 0.5, "unrecoverable_decline") == 0

    def test_browse_only_zero(self):
        assert compute_max_attempts(100, 0.1, "browse_only_abandonment") == 0

    def test_user_cancelled_two(self):
        assert compute_max_attempts(5000, 0.5, "user_cancelled") == 2

    def test_low_prob_one(self):
        assert compute_max_attempts(10000, 0.05, "gateway_error") == 1

    def test_high_prob_high_amount_five(self):
        assert compute_max_attempts(10000, 0.8, "upi_timeout") == 5

    def test_medium_prob_medium_amount_four(self):
        assert compute_max_attempts(3000, 0.6, "gateway_error") == 4

    def test_moderate_prob_three(self):
        assert compute_max_attempts(1500, 0.35, "bank_downtime") == 3

    def test_default_two(self):
        assert compute_max_attempts(500, 0.25, "insufficient_funds") == 2


class TestRouteAction:
    def _make_classification(self, **overrides):
        defaults = dict(
            leak_type="payment_failure",
            failure_category="gateway_error",
            recovery_probability=0.8,
            recommended_action="send retry link",
            recommended_channel="whatsapp",
            recommended_timing="immediate",
            reasoning="test",
        )
        defaults.update(overrides)
        return ClassificationResult(**defaults)

    def test_no_action_on_none_channel(self):
        c = self._make_classification(recommended_channel="none", skip_reason="fraud")
        plan = route_action(c)
        assert plan.action == "no_action"
        assert plan.skip_reason == "fraud"

    def test_no_action_on_unrecoverable(self):
        c = self._make_classification(failure_category="unrecoverable_decline")
        plan = route_action(c)
        assert plan.action == "no_action"

    def test_no_action_on_browse_only(self):
        c = self._make_classification(failure_category="browse_only_abandonment")
        plan = route_action(c)
        assert plan.action == "no_action"

    def test_send_now_immediate(self):
        c = self._make_classification(recommended_timing="immediate")
        plan = route_action(c)
        assert plan.action == "send_now"
        assert plan.channel == "whatsapp"
        assert plan.delay_seconds == 0

    def test_send_delayed_5_minutes(self):
        c = self._make_classification(recommended_timing="5_minutes")
        plan = route_action(c)
        assert plan.action == "send_delayed"
        assert plan.delay_seconds == 300

    def test_send_delayed_1_hour(self):
        c = self._make_classification(recommended_timing="1_hour")
        plan = route_action(c)
        assert plan.action == "send_delayed"
        assert plan.delay_seconds == 3600

    def test_send_delayed_4_hours(self):
        c = self._make_classification(recommended_timing="4_hours")
        plan = route_action(c)
        assert plan.action == "send_delayed"
        assert plan.delay_seconds == 14400

"""Unit tests for build_idempotency_key — the production key builder used by all send paths."""
from app.utils.idempotency import build_idempotency_key


class TestBuildIdempotencyKey:
    def test_initial_key_format(self):
        assert build_idempotency_key(42, "initial", 1) == "42:initial:1"

    def test_delayed_key_format(self):
        assert build_idempotency_key(42, "delayed", 3) == "42:delayed:3"

    def test_escalation_key_format(self):
        assert build_idempotency_key(42, "escalation", 2) == "42:escalation:2"

    def test_retry_failure_key_format(self):
        assert build_idempotency_key(42, "retry_failure", 4) == "42:retry_failure:4"

    def test_keys_are_unique_across_tags(self):
        keys = {
            build_idempotency_key(42, "initial", 1),
            build_idempotency_key(42, "delayed", 1),
            build_idempotency_key(42, "escalation", 1),
            build_idempotency_key(42, "retry_failure", 1),
        }
        assert len(keys) == 4

    def test_different_events_produce_different_keys(self):
        assert build_idempotency_key(1, "initial", 1) != build_idempotency_key(2, "initial", 1)

    def test_different_attempts_produce_different_keys(self):
        assert build_idempotency_key(1, "delayed", 1) != build_idempotency_key(1, "delayed", 2)

    def test_returns_string(self):
        assert isinstance(build_idempotency_key(1, "initial", 1), str)

    def test_contains_all_components(self):
        key = build_idempotency_key(99, "escalation", 7)
        assert "99" in key
        assert "escalation" in key
        assert "7" in key

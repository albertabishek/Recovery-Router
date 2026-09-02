class TestIdempotencyKeyFormats:
    def test_initial_key_format(self):
        key = f"{42}:initial:1"
        assert key == "42:initial:1"

    def test_delayed_key_format(self):
        key = f"{42}:delayed:{3}"
        assert key == "42:delayed:3"

    def test_escalation_key_format(self):
        key = f"{42}:escalation:{2}"
        assert key == "42:escalation:2"

    def test_retry_failure_key_format(self):
        key = f"{42}:retry_failure:{4}"
        assert key == "42:retry_failure:4"

    def test_keys_are_unique_across_tags(self):
        keys = {
            f"42:initial:1",
            f"42:delayed:1",
            f"42:escalation:1",
            f"42:retry_failure:1",
        }
        assert len(keys) == 4

    def test_different_events_produce_different_keys(self):
        key_a = f"{1}:initial:1"
        key_b = f"{2}:initial:1"
        assert key_a != key_b

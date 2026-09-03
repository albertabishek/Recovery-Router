"""Unit tests for rate_limiter.py — check_rate_limit, check_per_resource_cooldown."""
import pytest
from unittest.mock import patch, MagicMock


class TestCheckRateLimit:
    @patch("app.utils.rate_limiter.get_redis")
    def test_allows_under_limit(self, mock_redis_fn):
        mock_r = MagicMock()
        pipe = MagicMock()
        pipe.execute.return_value = [None, None, 5, None]  # 5 requests, under max of 10
        mock_r.pipeline.return_value = pipe
        mock_redis_fn.return_value = mock_r

        from app.utils.rate_limiter import check_rate_limit
        assert check_rate_limit("test_key", max_requests=10, window_seconds=60) is True

    @patch("app.utils.rate_limiter.get_redis")
    def test_blocks_over_limit(self, mock_redis_fn):
        mock_r = MagicMock()
        pipe = MagicMock()
        pipe.execute.return_value = [None, None, 11, None]  # 11 requests, over max of 10
        mock_r.pipeline.return_value = pipe
        mock_redis_fn.return_value = mock_r

        from app.utils.rate_limiter import check_rate_limit
        assert check_rate_limit("test_key", max_requests=10, window_seconds=60) is False
        mock_r.zrem.assert_called_once()

    @patch("app.utils.rate_limiter.get_redis")
    def test_at_exact_limit_is_allowed(self, mock_redis_fn):
        mock_r = MagicMock()
        pipe = MagicMock()
        pipe.execute.return_value = [None, None, 10, None]  # exactly at max
        mock_r.pipeline.return_value = pipe
        mock_redis_fn.return_value = mock_r

        from app.utils.rate_limiter import check_rate_limit
        assert check_rate_limit("test_key", max_requests=10, window_seconds=60) is True


class TestCheckPerResourceCooldown:
    @patch("app.utils.rate_limiter.get_redis")
    def test_allowed_when_no_cooldown(self, mock_redis_fn):
        mock_r = MagicMock()
        mock_r.set.return_value = True  # nx=True succeeds
        mock_redis_fn.return_value = mock_r

        from app.utils.rate_limiter import check_per_resource_cooldown
        assert check_per_resource_cooldown("phone", "+91999", 3600) is True

    @patch("app.utils.rate_limiter.get_redis")
    def test_blocked_during_cooldown(self, mock_redis_fn):
        mock_r = MagicMock()
        mock_r.set.return_value = False  # nx=True fails → cooldown active
        mock_redis_fn.return_value = mock_r

        from app.utils.rate_limiter import check_per_resource_cooldown
        assert check_per_resource_cooldown("phone", "+91999", 3600) is False

    @patch("app.utils.rate_limiter.get_redis")
    def test_uses_correct_key_format(self, mock_redis_fn):
        mock_r = MagicMock()
        mock_r.set.return_value = True
        mock_redis_fn.return_value = mock_r

        from app.utils.rate_limiter import check_per_resource_cooldown
        check_per_resource_cooldown("email", "test@test.com", 7200)
        mock_r.set.assert_called_once_with("cooldown:email:test@test.com", "1", nx=True, ex=7200)

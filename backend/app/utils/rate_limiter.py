import time
from app.redis_client import get_redis


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Sliding window rate limiter. Returns True if request is allowed."""
    r = get_redis()
    now = time.time()
    window_key = f"ratelimit:{key}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(window_key, 0, now - window_seconds)
    pipe.zadd(window_key, {str(now): now})
    pipe.zcard(window_key)
    pipe.expire(window_key, window_seconds)
    results = pipe.execute()

    current_count = results[2]
    if current_count > max_requests:
        r.zrem(window_key, str(now))
        return False
    return True


def check_per_resource_cooldown(resource_type: str, resource_id: str, cooldown_seconds: int) -> bool:
    """Per-resource cooldown (e.g., 1 message per phone per hour). Returns True if allowed."""
    r = get_redis()
    key = f"cooldown:{resource_type}:{resource_id}"
    if r.set(key, "1", nx=True, ex=cooldown_seconds):
        return True
    return False

import threading
import redis
from app.config import settings

_pool: redis.ConnectionPool | None = None
_lock = threading.Lock()


def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = redis.ConnectionPool.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
    return redis.Redis(connection_pool=_pool)

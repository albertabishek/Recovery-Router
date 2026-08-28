import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter
from app.models import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

_pool = ThreadPoolExecutor(max_workers=2)


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    services = {}
    loop = asyncio.get_running_loop()

    try:
        from app.redis_client import get_redis
        r = get_redis()
        pong = await loop.run_in_executor(_pool, r.ping)
        depth = await loop.run_in_executor(_pool, r.llen, "celery")
        services["redis"] = "ok"
        services["queue_depth"] = depth or 0
    except Exception as e:
        services["redis"] = f"error: {e}"

    def _celery_ping():
        from app.celery_app import celery_app
        insp = celery_app.control.inspect(timeout=2.0)
        ping = insp.ping()
        if ping:
            return f"ok ({len(ping)} workers)"
        return "no workers"

    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(_pool, _celery_ping), timeout=5.0
        )
        services["celery"] = result
    except asyncio.TimeoutError:
        services["celery"] = "timeout"
    except Exception as e:
        services["celery"] = f"error: {e}"

    services["supabase"] = "configured"
    overall = "ok" if services.get("redis") == "ok" else "degraded"

    return HealthResponse(status=overall, services=services)

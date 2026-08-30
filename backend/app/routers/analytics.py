from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import require_auth
from app.models import AnalyticsResponse
from app.services.analytics import compute_analytics
from app.utils.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api", tags=["analytics"], dependencies=[Depends(require_auth)])


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
):
    """Compute and return aggregate recovery analytics."""
    if not check_rate_limit("api:analytics", max_requests=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return compute_analytics(from_date=from_date, to_date=to_date)

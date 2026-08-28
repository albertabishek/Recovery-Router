import hashlib
import json
from app.redis_client import get_redis

DEDUP_TTL_SECONDS = 3600


def is_duplicate(event_type: str, identifier: str) -> bool:
    """Check if this event was already processed. Returns True if duplicate."""
    r = get_redis()
    key = f"dedup:{event_type}:{identifier}"
    if r.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS):
        return False
    return True


def get_dedup_identifier(body: dict) -> str:
    """Extract a unique identifier for deduplication from the event payload."""
    if body.get("event") == "payment.failed":
        entity = body.get("payload", {}).get("payment", {}).get("entity", {})
        return entity.get("id", "") or _hash_payload(body)

    return (
        body.get("payment_id")
        or body.get("order_id")
        or body.get("invoice_id")
        or _hash_payload(body)
    )


def _hash_payload(body: dict) -> str:
    stable = json.dumps(body, sort_keys=True, default=str)
    return f"hash_{hashlib.sha256(stable.encode()).hexdigest()[:16]}"

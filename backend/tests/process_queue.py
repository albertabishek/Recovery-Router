"""
Process pending Celery tasks synchronously (for testing without a worker).
Reads tasks from the Redis queue and executes them directly.
"""
import sys
import json
import base64
import logging

sys.path.insert(0, r"C:\Users\ELCOT\Desktop\Razorpay_buildathon\backend")

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from app.redis_client import get_redis
from app.tasks.recovery import process_recovery_event

r = get_redis()

queue_key = "celery"
processed = 0
failed = 0
skipped = 0

queue_len = r.llen(queue_key)
print(f"Found {queue_len} tasks in queue")

for i in range(min(queue_len, 150)):
    raw = r.lpop(queue_key)
    if not raw:
        break

    try:
        task = json.loads(raw)
        body_raw = task.get("body", "")
        decoded = base64.b64decode(body_raw)
        body = json.loads(decoded)

        # Celery body format: [[arg1, arg2, ...], {kwargs}, {options}]
        args = body[0] if isinstance(body, list) else []
        if not args or not isinstance(args[0], dict):
            skipped += 1
            continue

        event_data = args[0]

        # Check which task this is
        headers = task.get("headers", {})
        task_name = headers.get("task", "")
        if "process_recovery_event" not in task_name:
            skipped += 1
            continue

        result = process_recovery_event(event_data)
        processed += 1
        status = result.get("status", "unknown") if isinstance(result, dict) else "ok"
        if processed % 10 == 0:
            print(f"  Processed {processed}... last: {status} ({event_data.get('event_type', '?')} - {event_data.get('error_code', '?')})")

    except Exception as e:
        failed += 1
        if failed <= 5:
            print(f"  Error: {e}")

print(f"\nDone: {processed} processed, {failed} failed, {skipped} skipped (non-recovery tasks)")

# Show updated DB count
from app.database import get_supabase
sb = get_supabase()
res = sb.table("recovery_events").select("id", count="exact").execute()
print(f"Total events in DB: {res.count}")

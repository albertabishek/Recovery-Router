def build_idempotency_key(event_id: int, tag: str, attempt_number: int) -> str:
    return f"{event_id}:{tag}:{attempt_number}"

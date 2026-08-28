"""
OpenRouter AI client with 3-model fallback chain.
Chain: Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini → rules.
Handles rate limits, timeouts, invalid responses, and retries.
"""

import json
import logging
import time
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL_CHAIN = [
    {
        "id": "anthropic/claude-haiku-4.5",
        "name": "Claude Haiku 4.5",
        "timeout": 12,
        "max_retries": 1,
    },
    {
        "id": "google/gemini-3.7-flash",
        "name": "Gemini 3.7 Flash",
        "timeout": 10,
        "max_retries": 1,
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "GPT-4o-mini",
        "timeout": 12,
        "max_retries": 1,
    },
]

_http_client = None


def _get_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=15,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.API_BASE_URL,
                "X-Title": "Recovery Router",
            },
        )
    return _http_client


def ai_call(
    system_prompt: str,
    user_message: str,
    response_schema: dict | None = None,
    temperature: float = 0.1,
    max_tokens: int = 600,
) -> dict | None:
    """Make an AI call with automatic model fallback.

    Returns parsed JSON dict on success, None if all models fail.
    Logs every attempt for observability.
    """
    client = _get_client()

    for model in MODEL_CHAIN:
        for attempt in range(1 + model["max_retries"]):
            try:
                result = _call_single(
                    client, model, system_prompt, user_message,
                    response_schema, temperature, max_tokens, attempt,
                )
                if result is not None:
                    return result
            except Exception as e:
                logger.warning(
                    "AI call failed: model=%s attempt=%d error=%s",
                    model["name"], attempt + 1, str(e)[:200],
                )
                if attempt < model["max_retries"]:
                    time.sleep(0.5 * (attempt + 1))

    logger.error("All AI models exhausted, returning None for rule-based fallback")
    return None


def _call_single(
    client: httpx.Client,
    model: dict,
    system_prompt: str,
    user_message: str,
    response_schema: dict | None,
    temperature: float,
    max_tokens: int,
    attempt: int,
) -> dict | None:
    """Call a single model. Returns parsed dict or None."""
    payload = {
        "model": model["id"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature + (0.05 * attempt),
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    start = time.time()
    resp = client.post(OPENROUTER_URL, json=payload, timeout=model["timeout"])
    elapsed = time.time() - start

    if resp.status_code == 429:
        logger.warning("Rate limited on %s, trying next model", model["name"])
        return None

    if resp.status_code != 200:
        logger.warning(
            "AI HTTP %d from %s: %s",
            resp.status_code, model["name"], resp.text[:200],
        )
        return None

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content")

    if not content:
        logger.warning("Empty content from %s", model["name"])
        return None

    parsed = _parse_json(content)

    if response_schema:
        _validate_fields(parsed, response_schema)

    usage = data.get("usage", {})
    logger.info(
        "AI success: model=%s latency=%.1fs tokens=%d/%d",
        model["name"], elapsed,
        usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
    )
    return parsed


def _parse_json(content: str) -> dict:
    """Parse JSON from AI response, stripping markdown fences if present."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end]).strip()
    return json.loads(text)


def _validate_fields(parsed: dict, schema: dict):
    """Validate and fix fields against expected schema.

    Schema format: {"field_name": {"type": "str", "allowed": [...], "default": "value"}}
    """
    for field, rules in schema.items():
        value = parsed.get(field)
        allowed = rules.get("allowed")

        if allowed and value not in allowed:
            parsed[field] = rules.get("default", allowed[0])

        if value is None and "default" in rules:
            parsed[field] = rules["default"]

        if rules.get("type") == "float" and field in parsed:
            try:
                parsed[field] = max(
                    rules.get("min", 0.0),
                    min(rules.get("max", 1.0), float(parsed[field])),
                )
            except (TypeError, ValueError):
                parsed[field] = rules.get("default", 0.5)

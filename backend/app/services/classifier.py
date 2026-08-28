"""
AI-powered event classifier using OpenRouter with 3-model fallback.
The AI analyzes error descriptions, amounts, payment methods, and context
to make nuanced classification decisions that hardcoded rules cannot.
Falls back to rules only when all AI models are unavailable.
"""

import json
import re
import logging
from app.models import ClassificationResult, RecoveryEventInput
from app.services.ai_client import ai_call

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """You are the classification engine for a payment recovery system used by Indian merchants on Razorpay.

Your job: analyze a failed payment, abandoned cart, or overdue invoice and determine the best recovery strategy. You must figure out WHY it failed and what recovery approach has the highest chance of success.

## How to think about this

1. READ the error_description carefully — it contains the real reason, not just the error_code.
   - "Payment timed out" with method=upi means network congestion, NOT user abandonment. High recovery chance — the customer was trying to pay.
   - "Card declined" is ambiguous — could be expired, insufficient funds, or fraud. Look at amount and error_code for clues.
   - "Bank server unavailable" is temporary — very high recovery if you wait and retry.

2. CONSIDER the amount — it affects urgency and channel choice.
   - High amounts (>₹5000) justify WhatsApp (personal, immediate) over email.
   - Low amounts (<₹200) on cart abandonment are likely low-intent browsing.
   - Very high amounts (>₹50000) on invoices need careful, professional email.

3. PICK the right channel for the situation:
   - WhatsApp: urgent, time-sensitive, high-recovery scenarios. The customer is likely still at their device.
   - Email: formal, non-urgent, detailed. Good for expired cards (needs card update), invoices, follow-ups.
   - SMS: brief reminder. Good for insufficient funds (check balance later) or as a secondary nudge.
   - None: fraud, stolen cards, permanently blocked accounts, or very low-value browse-only carts.

4. DETECT user-initiated cancellations:
   - If the error_description mentions "cancelled", "canceled", "user aborted" or similar, this is NOT a gateway error.
   - Category should be "user_cancelled" — the customer actively chose to stop.
   - Recovery probability should be moderate (0.3-0.5) — they showed payment intent but backed out.
   - Don't send an immediate retry — wait at least 1 hour. They cancelled for a reason.

5. SET timing based on what will actually help:
   - immediate: UPI timeouts (retry now while session is fresh), gateway errors (already fixed)
   - 5_minutes: gateway errors where a brief wait helps
   - 30_minutes: bank downtime (wait for bank to come back online)
   - 1_hour: cart abandonment or user cancellations (don't nag instantly)
   - 4_hours: insufficient funds (give customer time to transfer money)

6. ESTIMATE recovery_probability honestly based on ALL signals, not just the category.
   A ₹499 UPI timeout at peak hours has higher recovery (0.85) than a ₹49,999 card decline with "suspected fraud" (0.0).

## Output format

Respond with a single JSON object:
{
  "leak_type": "payment_failure" | "cart_abandonment" | "invoice_overdue",
  "failure_category": "<category>",
  "recovery_probability": <0.0 to 1.0>,
  "recommended_action": "<specific action description>",
  "recommended_channel": "whatsapp" | "email" | "sms" | "none",
  "recommended_timing": "immediate" | "5_minutes" | "30_minutes" | "1_hour" | "4_hours",
  "reasoning": "<2-3 sentences explaining your analysis>",
  "alternative_action": "<backup approach if primary fails, or null>",
  "skip_reason": "<if no action, explain why, otherwise null>",
  "personalization_hint": "<key insight for message personalization>"
}

Categories: upi_timeout, bank_downtime, card_expired, insufficient_funds, gateway_error, user_cancelled, unrecoverable_decline, high_intent_abandonment, browse_only_abandonment, recently_overdue, moderately_overdue, long_overdue"""

RESPONSE_SCHEMA = {
    "leak_type": {
        "type": "str",
        "allowed": ["payment_failure", "cart_abandonment", "invoice_overdue"],
        "default": "payment_failure",
    },
    "failure_category": {
        "type": "str",
        "allowed": [
            "upi_timeout", "bank_downtime", "card_expired", "insufficient_funds",
            "gateway_error", "user_cancelled", "unrecoverable_decline", "high_intent_abandonment",
            "browse_only_abandonment", "recently_overdue", "moderately_overdue",
            "long_overdue",
        ],
        "default": "gateway_error",
    },
    "recovery_probability": {
        "type": "float", "min": 0.0, "max": 1.0, "default": 0.5,
    },
    "recommended_channel": {
        "type": "str",
        "allowed": ["whatsapp", "email", "sms", "none"],
        "default": "email",
    },
    "recommended_timing": {
        "type": "str",
        "allowed": ["immediate", "5_minutes", "30_minutes", "1_hour", "4_hours"],
        "default": "immediate",
    },
}

FALLBACK_RULES = {
    "TIMEOUT": ("upi_timeout", 0.80, "whatsapp", "immediate"),
    "UPI": ("upi_timeout", 0.80, "whatsapp", "immediate"),
    "BANK_DOWNTIME": ("bank_downtime", 0.75, "whatsapp", "30_minutes"),
    "NETWORK": ("bank_downtime", 0.75, "whatsapp", "30_minutes"),
    "CARD_EXPIRED": ("card_expired", 0.50, "email", "immediate"),
    "EXPIRED": ("card_expired", 0.50, "email", "immediate"),
    "INSUFFICIENT_FUNDS": ("insufficient_funds", 0.40, "sms", "4_hours"),
    "INSUFFICIENT": ("insufficient_funds", 0.40, "sms", "4_hours"),
    "GATEWAY_ERROR": ("gateway_error", 0.85, "whatsapp", "5_minutes"),
    "GATEWAY": ("gateway_error", 0.85, "whatsapp", "5_minutes"),
    "CANCELLED": ("user_cancelled", 0.35, "email", "1_hour"),
    "CANCELED": ("user_cancelled", 0.35, "email", "1_hour"),
    "FRAUD": ("unrecoverable_decline", 0.0, "none", "immediate"),
    "STOLEN": ("unrecoverable_decline", 0.0, "none", "immediate"),
    "DECLINED": ("unrecoverable_decline", 0.05, "none", "immediate"),
}


def _sanitize(value: str | None, max_len: int = 200) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value))
    return cleaned[:max_len]


def classify_event(event: RecoveryEventInput) -> ClassificationResult:
    """Classify an event using AI with 3-model fallback, then rules as last resort."""
    try:
        result = _ai_classify(event)
        if result:
            return result
    except Exception as e:
        logger.error("AI classification pipeline failed: %s", e)

    logger.info("Using rule-based fallback for event_type=%s", event.event_type)
    return _fallback_classify(event)


def _ai_classify(event: RecoveryEventInput) -> ClassificationResult | None:
    """Classify using OpenRouter AI with multi-model fallback."""
    user_msg = json.dumps({
        "event_type": event.event_type,
        "method": _sanitize(event.method, 50),
        "error_code": _sanitize(event.error_code, 100),
        "error_description": _sanitize(event.error_description, 200),
        "amount": event.amount,
        "currency": event.currency,
        "customer_name": _sanitize(event.customer_name, 100),
        "days_overdue": event.days_overdue,
        "cart_value": event.cart_value,
        "items_in_cart": event.items_in_cart,
    })

    raw = ai_call(
        system_prompt=CLASSIFICATION_PROMPT,
        user_message=user_msg,
        response_schema=RESPONSE_SCHEMA,
        temperature=0.1,
        max_tokens=600,
    )

    if raw is None:
        return None

    raw.setdefault("leak_type", event.event_type)
    raw.setdefault("recommended_action", f"recover_via_{raw.get('recommended_channel', 'email')}")
    raw.setdefault("reasoning", "AI classification")
    raw.setdefault("alternative_action", None)
    raw.setdefault("skip_reason", None)

    if raw.get("recommended_channel") == "none" and not raw.get("skip_reason"):
        raw["skip_reason"] = raw.get("reasoning", "No recovery action recommended")

    return ClassificationResult(**raw, fallback_used=False)


def _fallback_classify(event: RecoveryEventInput) -> ClassificationResult:
    """Rule-based fallback when all AI models are unavailable."""
    error_code = (event.error_code or "").upper()

    category = "gateway_error"
    prob = 0.5
    channel = "email"
    timing = "immediate"

    if event.event_type == "cart_abandonment":
        if event.cart_value and event.cart_value >= 200:
            category, prob, channel, timing = "high_intent_abandonment", 0.35, "whatsapp", "1_hour"
        else:
            category, prob, channel, timing = "browse_only_abandonment", 0.07, "none", "immediate"
    elif event.event_type == "invoice_overdue":
        days = event.days_overdue or 0
        if days <= 7:
            category, prob, channel, timing = "recently_overdue", 0.70, "whatsapp", "immediate"
        elif days <= 30:
            category, prob, channel, timing = "moderately_overdue", 0.40, "email", "immediate"
        else:
            category, prob, channel, timing = "long_overdue", 0.15, "email", "immediate"
    else:
        error_desc = (event.error_description or "").upper()
        matched = False
        for code_prefix, rule in FALLBACK_RULES.items():
            if code_prefix in error_code:
                category, prob, channel, timing = rule
                matched = True
                break
        if not matched:
            for code_prefix, rule in FALLBACK_RULES.items():
                if code_prefix in error_desc:
                    category, prob, channel, timing = rule
                    break

    return ClassificationResult(
        leak_type=event.event_type,
        failure_category=category,
        recovery_probability=prob,
        recommended_action=f"fallback_{channel}_recovery",
        recommended_channel=channel,
        recommended_timing=timing,
        reasoning=f"Rule-based fallback (AI unavailable). Matched error_code={event.error_code}",
        alternative_action=None,
        skip_reason="Unrecoverable decline" if channel == "none" else None,
        fallback_used=True,
    )

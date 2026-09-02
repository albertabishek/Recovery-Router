# AI & Prompts: Complete Technical Reference

> Every AI decision Recovery Router makes - classification, messaging, escalation - documented with the actual code and prompts.

**Author:** Albert Abishek I
**Project:** Recovery Router (Razorpay AI Buildathon 2026, Track 3)
**Codebase:** `backend/app/services/`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [The 3-Model Fallback Chain](#2-the-3-model-fallback-chain)
3. [AI Classification System](#3-ai-classification-system)
4. [AI Message Generation](#4-ai-message-generation)
5. [AI Escalation Decisions](#5-ai-escalation-decisions)
6. [Dynamic Budget Calculation](#6-dynamic-budget-calculation)
7. [AI Safety Measures](#7-ai-safety-measures)
8. [Prompt Engineering Decisions](#8-prompt-engineering-decisions)

---

## 1. Architecture Overview

Recovery Router uses AI at three decision points in the recovery pipeline:

```
Event arrives
    |
    v
[1. CLASSIFY] -- AI decides: what failed, how to recover, which channel, when
    |
    v
[2. ROUTE] -- Deterministic: maps classification to action plan
    |
    v
[3. GENERATE MESSAGE] -- AI writes personalized message for the chosen channel
    |
    v
[4. SEND] -- Multi-provider messenger delivers the message
    |
    v
(customer doesn't respond)
    |
    v
[5. ESCALATE] -- AI decides: try again? different channel? give up?
    |
    v
[3. GENERATE MESSAGE] -- AI writes next message with escalated tone
    ...repeat until budget exhausted...
```

All three AI touchpoints use the same underlying client (`ai_client.py`) with the same 3-model fallback chain. Every AI call has a rule-based fallback for when all models are unavailable.

---

## 2. The 3-Model Fallback Chain

**File:** `backend/app/services/ai_client.py`

### Model Chain Configuration (lines 18-37)

```python
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
```

### Why These Models in This Order

1. **Claude Haiku 4.5 (first):** Fastest inference among the three. Best at following structured JSON output instructions. 12s timeout with 1 retry = up to 24s before moving on. Handles the classification prompt's nuanced reasoning (Indian payment context, UPI vs card vs bank errors) most reliably.

2. **Gemini 3.7 Flash (second):** Google's speed-optimized model. 10s timeout (shortest) - if Claude is down, this responds quickly. Good at structured JSON. Different provider (Google vs Anthropic), so an Anthropic outage won't affect it.

3. **GPT-4o-mini (third/last):** OpenAI's cheapest model. Reliable but slightly slower for structured output. Acts as the final AI attempt before falling back to rules. Different provider again (OpenAI), maximizing resilience.

4. **Rule-based fallback (final):** If all three AI models fail (network outage, API keys expired, rate limits), hardcoded rules ensure the system never stops classifying events. Reliability over sophistication.

### OpenRouter Integration (lines 43-57)

All models are accessed through a single OpenRouter API endpoint. This means one API key, one HTTP client, one integration - but access to models from Anthropic, Google, and OpenAI.

```python
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def _get_client() -> httpx.Client:
    """Singleton HTTP client with thread-safe initialization."""
    # Uses httpx.Client with:
    #   - Authorization: Bearer <OPENROUTER_API_KEY>
    #   - HTTP-Referer: <API_BASE_URL> (required by OpenRouter)
    #   - X-Title: "Recovery Router" (for OpenRouter dashboard tracking)
    #   - Default timeout: 15s (overridden per-model)
```

### How the Fallback Chain Works (lines 60-92)

```python
def ai_call(system_prompt, user_message, response_schema=None,
            temperature=0.1, max_tokens=600) -> dict | None:
    for model in MODEL_CHAIN:                    # Try each model in order
        for attempt in range(1 + model["max_retries"]):  # With retries
            result = _call_single(...)
            if result is not None:
                return result                    # First success wins
            # On failure: log, wait 0.5s * attempt, try again
    return None  # All models exhausted -> caller uses rule-based fallback
```

The flow for each individual model call (`_call_single`, lines 95-150):

1. Build the OpenRouter payload with model ID, messages, temperature, max_tokens, and `response_format: {"type": "json_object"}`
2. POST to OpenRouter with per-model timeout
3. If HTTP 429 (rate limited): log, return None (triggers next model)
4. If HTTP != 200: log the error body, return None
5. Extract `choices[0].message.content` from the response
6. Parse JSON (stripping markdown fences if the model wrapped them)
7. Validate against the response schema (fix invalid values using defaults)
8. Log success with latency and token usage
9. Return the parsed dict

### JSON Parsing (lines 153-165)

Models sometimes wrap JSON in markdown code fences. The parser handles this:

```python
def _parse_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1  # Skip the opening ```json line
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end]).strip()
    return json.loads(text)
```

### Schema Validation (lines 168-191)

After parsing, fields are validated against an expected schema:

```python
def _validate_fields(parsed: dict, schema: dict):
    for field, rules in schema.items():
        value = parsed.get(field)
        allowed = rules.get("allowed")
        if allowed and value not in allowed:
            parsed[field] = rules.get("default", allowed[0])  # Fix invalid enum values
        if value is None and "default" in rules:
            parsed[field] = rules["default"]                  # Fill missing fields
        if rules.get("type") == "float" and field in parsed:
            parsed[field] = max(min, min(max, float(value)))  # Clamp numeric ranges
```

This means if an AI model returns `"failure_category": "timeout"` (not in the allowed list), it gets corrected to `"gateway_error"` (the default). The system never propagates invalid values.

---

## 3. AI Classification System

**File:** `backend/app/services/classifier.py`

### The Classification Prompt (lines 16-70)

This is the exact prompt sent as the system message. It is the most detailed prompt in the system because classification drives every downstream decision.

```
You are the classification engine for a payment recovery system used by Indian merchants on Razorpay.

Your job: analyze a failed payment, abandoned cart, or overdue invoice and determine the best recovery strategy. You must figure out WHY it failed and what recovery approach has the highest chance of success.

## How to think about this

1. READ the error_description carefully - it contains the real reason, not just the error_code.
   - "Payment timed out" with method=upi means network congestion, NOT user abandonment. High recovery chance - the customer was trying to pay.
   - "Card declined" is ambiguous - could be expired, insufficient funds, or fraud. Look at amount and error_code for clues.
   - "Bank server unavailable" is temporary - very high recovery if you wait and retry.

2. CONSIDER the amount - it affects urgency and channel choice.
   - High amounts (>₹5000) justify WhatsApp (personal, immediate) over email.
   - Low amounts (<₹200) on cart abandonment are likely low-intent browsing.
   - Very high amounts (>₹50000) on invoices need careful, professional email.

3. PICK the right channel for the situation:
   - WhatsApp: urgent, time-sensitive, high-recovery scenarios. The customer is likely still at their device.
   - Email: formal, non-urgent, detailed. Good for expired cards (needs card update), invoices, follow-ups.
   - SMS: brief reminder. Good for insufficient funds (check balance later) or as a secondary nudge.
   - None: fraud, stolen cards, permanently blocked accounts, very low-value browse-only carts. ALWAYS use "none" when failure_category is "unrecoverable_decline" or "browse_only_abandonment".

4. DETECT user-initiated cancellations:
   - If the error_description mentions "cancelled", "canceled", "user aborted" or similar, this is NOT a gateway error.
   - Category should be "user_cancelled" - the customer actively chose to stop.
   - Recovery probability should be moderate (0.3-0.5) - they showed payment intent but backed out.
   - Don't send an immediate retry - wait at least 1 hour. They cancelled for a reason.

5. SET timing based on what will actually help:
   - immediate: UPI timeouts (retry now while session is fresh), gateway errors (already fixed)
   - 5_minutes: gateway errors where a brief wait helps
   - 30_minutes: bank downtime (wait for bank to come back online)
   - 1_hour: cart abandonment or user cancellations (don't nag instantly)
   - 4_hours: insufficient funds (give customer time to transfer money)

6. ESTIMATE recovery_probability honestly based on ALL signals, not just the category.
   A ₹499 UPI timeout at peak hours has higher recovery (0.85) than a ₹49,999 card decline with "suspected fraud" (0.0).
```

### Output Schema

The AI must return this exact JSON structure:

```json
{
  "leak_type": "payment_failure" | "cart_abandonment" | "invoice_overdue",
  "failure_category": "<one of 12 categories>",
  "recovery_probability": 0.0 to 1.0,
  "recommended_action": "<specific action description>",
  "recommended_channel": "whatsapp" | "email" | "sms" | "none",
  "recommended_timing": "immediate" | "5_minutes" | "30_minutes" | "1_hour" | "4_hours",
  "reasoning": "<2-3 sentences explaining the analysis>",
  "alternative_action": "<backup approach if primary fails, or null>",
  "skip_reason": "<if no action, explain why, otherwise null>",
  "personalization_hint": "<key insight for message personalization>"
}
```

### The 12 Failure Categories

| # | Category | Type | Description |
|---|----------|------|-------------|
| 1 | `upi_timeout` | Payment | UPI transaction timed out - network congestion, customer was trying to pay |
| 2 | `bank_downtime` | Payment | Bank server unavailable - temporary, high recovery on retry |
| 3 | `card_expired` | Payment | Customer's card has expired - needs to update payment method |
| 4 | `insufficient_funds` | Payment | Not enough balance - customer needs time to transfer money |
| 5 | `gateway_error` | Payment | Payment gateway technical error - customer's method is fine |
| 6 | `user_cancelled` | Payment | Customer actively cancelled the transaction |
| 7 | `unrecoverable_decline` | Payment | Fraud, stolen card, permanently blocked - do NOT attempt recovery |
| 8 | `high_intent_abandonment` | Cart | High-value cart with items - genuine shopping intent |
| 9 | `browse_only_abandonment` | Cart | Low-value browsing cart - not worth pursuing |
| 10 | `recently_overdue` | Invoice | Invoice 1-7 days late - gentle reminder usually works |
| 11 | `moderately_overdue` | Invoice | Invoice 2-4 weeks late - needs formal approach |
| 12 | `long_overdue` | Invoice | Invoice 30+ days late - requires escalation notice |

### Response Schema Validation (lines 72-101)

```python
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
            "gateway_error", "user_cancelled", "unrecoverable_decline",
            "high_intent_abandonment", "browse_only_abandonment",
            "recently_overdue", "moderately_overdue", "long_overdue",
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
```

Key design decisions in the schema:
- **`failure_category` defaults to `"gateway_error"`** - the safest default. Gateway errors have high recovery probability (0.85), so if the AI returns garbage, the system treats it as recoverable and tries.
- **`recovery_probability` is clamped to [0.0, 1.0]** - prevents AI hallucinations like `probability: 95` (which would be clamped to 1.0).
- **`recommended_channel` defaults to `"email"`** - the least intrusive channel. If AI fails to specify, the system doesn't spam via WhatsApp.

### Input Sanitization (lines 122-127)

Before sending data to the AI, all string inputs are sanitized:

```python
def _sanitize(value: str | None, max_len: int = 200) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value))
    return cleaned[:max_len]
```

- **Control character stripping:** Removes ASCII control characters (null bytes, backspace, etc.) that could confuse the model or be used for prompt injection.
- **Length truncation:** `error_description` capped at 200 chars, `method` at 50, `error_code` at 100, `customer_name` at 100. Prevents token waste and limits attack surface.

### User Message Construction (lines 144-155)

The event data is serialized as JSON for the user message:

```python
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
```

AI call parameters: `temperature=0.1` (near-deterministic), `max_tokens=600`.

### Post-AI Processing (lines 166-177)

After the AI responds, defaults are filled for optional fields:

```python
raw.setdefault("leak_type", event.event_type)
raw.setdefault("recommended_action", f"recover_via_{raw.get('recommended_channel', 'email')}")
raw.setdefault("reasoning", "AI classification")
raw.setdefault("alternative_action", None)
raw.setdefault("skip_reason", None)

# Safety: if channel is "none" but skip_reason is missing, fill it
if raw.get("recommended_channel") == "none" and not raw.get("skip_reason"):
    raw["skip_reason"] = raw.get("reasoning", "No recovery action recommended")
```

### Rule-Based Fallback (lines 103-119, 244-293)

When all three AI models fail, the system falls back to keyword matching against `error_code` and `error_description`.

**Fallback Rules Table (lines 103-119):**

```python
FALLBACK_RULES = {
    "TIMEOUT":           ("upi_timeout",           0.80, "whatsapp",  "immediate"),
    "UPI":               ("upi_timeout",           0.80, "whatsapp",  "immediate"),
    "BANK_DOWNTIME":     ("bank_downtime",         0.75, "whatsapp",  "30_minutes"),
    "NETWORK":           ("bank_downtime",         0.75, "whatsapp",  "30_minutes"),
    "CARD_EXPIRED":      ("card_expired",          0.50, "email",     "immediate"),
    "EXPIRED":           ("card_expired",          0.50, "email",     "immediate"),
    "INSUFFICIENT_FUNDS":("insufficient_funds",    0.40, "sms",       "4_hours"),
    "INSUFFICIENT":      ("insufficient_funds",    0.40, "sms",       "4_hours"),
    "GATEWAY_ERROR":     ("gateway_error",         0.85, "whatsapp",  "5_minutes"),
    "GATEWAY":           ("gateway_error",         0.85, "whatsapp",  "5_minutes"),
    "CANCELLED":         ("user_cancelled",        0.35, "email",     "1_hour"),
    "CANCELED":          ("user_cancelled",        0.35, "email",     "1_hour"),
    "FRAUD":             ("unrecoverable_decline",  0.0, "none",      "immediate"),
    "STOLEN":            ("unrecoverable_decline",  0.0, "none",      "immediate"),
    "DECLINED":          ("unrecoverable_decline", 0.05, "none",      "immediate"),
}
```

Note: Each keyword has two entries (e.g., `TIMEOUT` and `UPI`, `CANCELLED` and `CANCELED`) to handle variant spellings from different payment processors.

**Fallback Classification Logic (lines 244-293):**

1. For `cart_abandonment`: cart_value >= 200 -> `high_intent_abandonment` (WhatsApp, 1hr delay); otherwise -> `browse_only_abandonment` (no action).
2. For `invoice_overdue`: days_overdue <= 7 -> `recently_overdue`; <= 30 -> `moderately_overdue`; else -> `long_overdue`.
3. For `payment_failure`: search `error_code` first, then `error_description` for keyword matches. First match wins. No match -> defaults to `gateway_error` (the safest assumption).

**Fallback Actions (lines 180-241):**

Each category has a pre-written action description, reasoning, and alternative action used when AI is unavailable. These are defined in the `FALLBACK_ACTIONS` dict and provide human-readable explanations even in degraded mode.

---

## 4. AI Message Generation

**File:** `backend/app/services/message_generator.py`

### The Message Generation Prompt (lines 14-61)

```
You write recovery messages for a payment recovery system used by Indian merchants.

Your job: write a SHORT, WARM, HELPFUL message that makes the customer want to complete their payment. Not pushy. Not corporate. Like a helpful shopkeeper who noticed something went wrong.

## Context you'll receive
- channel: whatsapp, sms, or email
- failure_category: what went wrong
- amount and currency
- customer_name (use first name only if full name given)
- personalization_hint: specific insight from the classification engine
- attempt_number: 0 = first contact, 1+ = follow-up

## Channel constraints

**WhatsApp** (max 200 chars):
- Conversational, warm, direct
- Include the payment link naturally
- Use 1-2 relevant emojis max (not generic smiley - match the context)
- No formal greetings, no "Dear Sir/Madam"

**SMS** (max 140 chars):
- Ultra-brief, action-focused
- Amount + reason + link, that's it
- No emojis, no fluff

**Email** (subject + body):
- Subject: max 60 chars, specific to the failure (not generic "payment failed")
- Body: 2-3 short paragraphs. Acknowledge what happened. Explain it's easy to fix. Link.
- Warm but professional. No "We apologize for the inconvenience."

## Tone by attempt
- attempt 0: Helpful, no pressure. "Hey, looks like something went wrong."
- attempt 1: Gentle reminder. "Just following up."
- attempt 2: Slightly more direct. "Your payment is still pending."
- attempt 3+: Final, honest. "Last reminder before we close this."

## Output format
Respond with JSON:
{
  "whatsapp_text": "<message with {link} placeholder>",
  "sms_text": "<message with {link} placeholder>",
  "email_subject": "<subject line>",
  "email_greeting": "<opening line>",
  "email_body": "<main paragraph>",
  "email_cta_text": "<button text, max 25 chars>"
}

IMPORTANT: Use {link} as placeholder for the payment URL. Do NOT invent a URL.
```

### How Context Flows to the AI (lines 68-103)

The message generator receives context from the classifier and escalation engine:

```python
user_msg = json.dumps({
    "channel": channel,                          # Which channel the escalation engine chose
    "failure_category": failure_category,         # From classifier
    "amount": amount,
    "currency": currency,
    "customer_name": name,                        # First name only (split from full name)
    "personalization_hint": personalization_hint,  # From classifier's analysis
    "attempt_number": attempt_number,              # 0 = first, 1+ = follow-up
    "reasoning": reasoning,                        # From escalation engine
})
```

AI call parameters: `temperature=0.4` (more creative than classification, but still controlled), `max_tokens=400`.

### Tone Escalation

The AI receives `attempt_number` and is instructed to adjust tone:

| Attempt | Tone | Example Opening |
|---------|------|-----------------|
| 0 | Helpful, no pressure | "Hey, looks like something went wrong." |
| 1 | Gentle reminder | "Just following up." |
| 2 | More direct | "Your payment is still pending." |
| 3+ | Final, honest | "Last reminder before we close this." |

This is AI-driven, not hardcoded. The AI has creative freedom within these guidelines, producing different messages for a UPI timeout vs. an expired card vs. an overdue invoice.

### Channel-Specific Output

The AI generates messages for ALL channels in a single call, even though only one will be used. This ensures consistency if the message needs to be re-sent via a different channel during escalation.

- **WhatsApp:** Max 200 chars, conversational, 1-2 contextual emojis, `{link}` placeholder
- **SMS:** Max 140 chars, ultra-brief, no emojis, `{link}` placeholder
- **Email:** Subject (max 60 chars) + greeting + body (2-3 paragraphs) + CTA button text (max 25 chars)

### Template Fallback (lines 111-135)

When AI is unavailable, hardcoded templates are used:

```python
# attempt 0:
wa = f"Hi {name}, your payment of {currency} {amount:,.0f} didn't go through. Tap here to retry: {link}"
sms = f"{currency} {amount:,.0f} payment pending. Retry: {link}"
subj = f"Complete your {currency} {amount:,.0f} payment"

# attempt 1+:
wa = f"Hi {name}, just a reminder - your {currency} {amount:,.0f} payment is still pending: {link}"
sms = f"Reminder: {currency} {amount:,.0f} pending. Complete: {link}"
subj = f"Reminder: {currency} {amount:,.0f} payment pending"
```

### Email HTML Rendering (lines 138-176)

The `render_email_html()` function takes the AI's output and renders it into a styled HTML email. Key safety measures:

- All text fields are HTML-escaped using `html.escape()` to prevent XSS
- The payment link URL is validated to start with `http://` or `https://` - otherwise replaced with `"#"`
- Newlines in the email body are converted to `<br>` tags

---

## 5. AI Escalation Decisions

**File:** `backend/app/services/escalation.py`

### The Escalation Prompt (lines 40-78)

```
You are the escalation decision agent for a payment recovery system. A customer hasn't completed their payment despite previous recovery attempts.

Your job: analyze what happened in previous attempts and decide the BEST next move. You will be given the event's max_attempts - the system already computed how many attempts this event deserves based on amount, probability, and failure type. Respect that budget.

## Decision framework

1. LOOK at previous attempts AND blocked/failed channels:
   - What channel was used? Did it succeed in delivering?
   - If WhatsApp was sent but customer didn't act → try email with more detail or SMS.
   - If email was sent but not opened → try WhatsApp or SMS for immediacy.
   - If delivery failed (provider error) → SWITCH to a different channel, don't retry the same one.
   - Check "blocked_channels" - these hit a cooldown/rate limit. ALWAYS pick a different channel.
   - Check "failed_channels" - delivery failed on these. Prefer a different channel.
   - If a "backup_plan" is provided, follow it when the primary channel didn't work.

2. CONSIDER the event context:
   - High amount (>5000) + multiple attempts → the customer is hesitating, not forgetting. Address their concern.
   - UPI timeout → high recovery chance, keep trying with different channels.
   - Card expired → customer needs to update their card. Email is best.
   - Insufficient funds → give them more time between attempts.

3. ADJUST tone:
   - After 0-1 attempts: friendly, helpful
   - After 2 attempts: direct, acknowledge it's a follow-up
   - After 3+ attempts: honest, final chance

4. WHEN TO GIVE UP:
   - ONLY give up if attempt_count >= max_attempts (the budget is already computed for you)
   - OR if ALL previous delivery attempts failed (bad contact info - no channel works)
   - Do NOT give up just because probability is low or amount is small - the max_attempts budget already accounts for that
   - NEVER give up on the first escalation (attempt_count == 1). The customer deserves at least one follow-up on a different channel.
```

### Escalation Output Schema (lines 80-84)

```python
ESCALATION_SCHEMA = {
    "action": {"type": "str", "allowed": ["send", "give_up"], "default": "send"},
    "channel": {"type": "str", "allowed": ["whatsapp", "email", "sms"], "default": "email"},
    "tone": {"type": "str", "allowed": ["friendly", "firm", "urgent", "final"], "default": "firm"},
}
```

Note: The schema default for `action` is `"send"`, not `"give_up"`. This is a deliberate safety decision - if the AI returns an invalid action value, the system defaults to continuing recovery rather than giving up.

### What the AI Receives (lines 256-299)

The escalation AI gets a comprehensive context object:

```python
user_msg = json.dumps({
    "event_type": event.get("event_type"),
    "amount": event.get("amount"),
    "currency": event.get("currency", "INR"),
    "failure_category": event.get("failure_category"),
    "recovery_probability": event.get("recovery_probability"),
    "attempt_count": attempt_count,
    "max_attempts": max_attempts,
    "attempts_remaining": max_attempts - attempt_count,
    "previous_attempts": attempt_summary,       # List of {number, channel, outcome, notes}
    "blocked_channels": list(blocked_channels), # Channels on cooldown
    "failed_channels": list(failed_channels),   # Channels where delivery failed
    "recommended_channel": event.get("recommended_channel"),  # Original classifier recommendation
    "backup_plan": event.get("alternative_action"),           # Alternative from classifier
    "has_email": bool(event.get("customer_email")),
    "has_phone": bool(event.get("customer_phone")),
})
```

AI call parameters: `temperature=0.15`, `max_tokens=250`.

### Three-Layer Safety Against Premature Give-Up

The system has three independent layers preventing the AI from giving up too early:

**Layer 1 - Hard budget check before AI is called (lines 260-263):**

```python
if attempt_count >= max_attempts:
    return {"action": "give_up", ...}  # Budget exhausted, don't even ask AI
```

**Layer 2 - AI override within `_get_escalation_decision` (lines 310-351):**

If the AI says `give_up` but `attempt_count < max_attempts`, the function checks whether there are truly no options left:

```python
if result.get("action") == "give_up" and attempt_count < max_attempts:
    # Check if ALL outreach attempts actually failed AND no untried channels remain
    all_truly_exhausted = (
        outreach_attempts
        and all(a.get("outcome") == "failed" for a in outreach_attempts)
        and not untried_channels
    )
    if not all_truly_exhausted or attempt_count == 0:
        # Override: force a send on a different channel
        result = {
            "action": "send",
            "channel": _pick_next_channel(last_channel, event, avoid=blocked_chs),
            "tone": "firm" if attempt_count <= 2 else "urgent",
            "reasoning": "Override: AI suggested give_up but attempts remain. Switching channel.",
        }
```

**Layer 3 - Hard guard in `run_escalation` (lines 136-155):**

Even if the AI override somehow fails, `run_escalation()` itself blocks give_up when budget remains:

```python
if decision.get("action") == "give_up":
    if attempt_count < max_attempts:
        # Force send - pick a channel that isn't blocked
        decision = {
            "action": "send",
            "channel": _pick_next_channel(last_ch, event, avoid=blocked_chs),
            "tone": "firm" if attempt_count <= 2 else "urgent",
            "reasoning": f"Safety override: give_up blocked because {remaining} attempts remain.",
        }
```

This means the AI can ONLY give up when `attempt_count >= max_attempts` OR when every channel has been tried and every delivery has failed AND there are no untried channels left.

### Channel Selection Logic (lines 363-384)

When overriding the AI's give_up or when the AI is unavailable, channels are picked with `_pick_next_channel()`:

```python
def _pick_next_channel(last_channel, event, avoid=None):
    # Priority order: whatsapp > email > sms
    # Constraints: must have contact info, must not be in avoid set
    # Always picks a DIFFERENT channel from last_channel if possible
```

### Fallback When AI is Unavailable (lines 354-360)

```python
channel_rotation = ["whatsapp", "email", "sms", "whatsapp", "email"]
return {
    "action": "send",
    "channel": channel_rotation[min(attempt_count, 4)],
    "tone": "firm" if attempt_count <= 2 else "urgent",
    "reasoning": f"Fallback: AI unavailable, rotating channels (attempt {attempt_count + 1}/{max_attempts})",
}
```

This deterministic rotation ensures recovery continues even without AI: WhatsApp first, then email, then SMS, then back to WhatsApp.

### Retry Delays Between Escalations (lines 430-441)

After each successful send, the next attempt is scheduled based on failure category:

```python
RETRY_DELAY_HOURS = {
    "upi_timeout": 1,
    "gateway_error": 1,
    "bank_downtime": 2,
    "card_expired": 6,
    "insufficient_funds": 8,
    "user_cancelled": 12,
    "recently_overdue": 24,
    "moderately_overdue": 48,
    "long_overdue": 48,
    "high_intent_abandonment": 2,
}
```

The logic: technical errors get short delays (customer might retry soon), behavioral issues get longer delays (customer needs time/space).

### Quiet Hours (lines 22-38)

No messages are sent between 9 PM and 9 AM IST. Events are rescheduled to the next permitted time.

---

## 6. Dynamic Budget Calculation

**File:** `backend/app/services/router.py`, lines 13-35

The `max_attempts` value determines how many recovery attempts an event gets. It is computed deterministically (not by AI) based on the AI's classification output.

```python
def compute_max_attempts(amount, recovery_probability, failure_category) -> int:
    # Hard stops: never attempt recovery for these
    if failure_category == "unrecoverable_decline":
        return 0
    if failure_category == "browse_only_abandonment":
        return 0

    # Reduced budget: user chose to cancel
    if failure_category == "user_cancelled":
        return 2

    # Very low probability: one attempt max
    if recovery_probability <= 0.1:
        return 1

    # Tiered budget based on value and probability
    if recovery_probability >= 0.7 and amount >= 5000:
        return 5  # High-value, high-probability: full budget
    if recovery_probability >= 0.5 and amount >= 2000:
        return 4
    if recovery_probability >= 0.3 or amount >= 1000:
        return 3

    return 2  # Default: modest effort
```

### Budget Tiers Summary

| Condition | max_attempts | Rationale |
|-----------|-------------|-----------|
| Unrecoverable decline | 0 | Fraud/stolen card - any contact would be harmful |
| Browse-only abandonment | 0 | Not worth the cost of a single message |
| User cancelled | 2 | They chose to cancel - respect that, but try twice |
| recovery_probability <= 0.1 | 1 | Very unlikely to recover - one shot |
| prob >= 0.7 AND amount >= 5000 | 5 | High-value, high-probability - invest heavily |
| prob >= 0.5 AND amount >= 2000 | 4 | Moderate-high value |
| prob >= 0.3 OR amount >= 1000 | 3 | Worth a few tries |
| Default | 2 | Low-value or low-probability |

---

## 7. AI Safety Measures

### Prompt Injection Prevention

1. **Input sanitization** (`classifier.py`, line 122): All user-supplied strings are stripped of control characters and truncated before being sent to the AI. The regex `[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]` removes null bytes, backspace, and other non-printable characters that could be used to inject hidden instructions.

2. **JSON serialization**: User inputs are serialized with `json.dumps()`, which escapes special characters. This prevents a malicious `error_description` like `"}, "system": "ignore previous instructions"` from breaking out of the JSON structure.

3. **Length limits**: `error_description` is capped at 200 characters, `method` at 50, `error_code` at 100. This limits the attack surface - a prompt injection payload needs enough tokens to be effective.

### Output Validation Against Allowed Categories

Every AI response field that has a constrained set of values is validated:

- `failure_category` must be one of 12 specific strings - any other value is replaced with `"gateway_error"`
- `recommended_channel` must be `"whatsapp"`, `"email"`, `"sms"`, or `"none"` - defaults to `"email"`
- `recommended_timing` must be one of 5 specific values - defaults to `"immediate"`
- `recovery_probability` is clamped to [0.0, 1.0]
- Escalation `action` must be `"send"` or `"give_up"` - defaults to `"send"`
- Escalation `tone` must be one of 4 values - defaults to `"firm"`

### What Happens When ALL AI Fails

The system has fallbacks at every level:

1. **Classification**: Rule-based keyword matching against error codes and descriptions
2. **Message generation**: Hardcoded template messages per channel
3. **Escalation**: Deterministic channel rotation (whatsapp -> email -> sms -> whatsapp -> email)

The system never stops processing events because AI is unavailable. The `fallback_used: true` flag on classification results makes it visible in the dashboard when AI was not used.

### Email HTML Safety

- All AI-generated text is HTML-escaped with `html.escape()` before rendering into email HTML
- Payment link URLs are validated to start with `http://` or `https://` - anything else becomes `"#"`
- This prevents XSS in email clients if the AI were to generate malicious content

### Event-Level Locking

Each event is locked with a Redis key (`lock:event:{id}`, TTL 300s) before processing. This prevents duplicate sends if the scheduler fires twice or if two workers pick up the same event.

### Quiet Hours Enforcement

Messages are never sent between 9 PM and 9 AM IST, regardless of what the AI recommends. Events are rescheduled to the next permitted window.

---

## 8. Prompt Engineering Decisions

### Why the Classification Prompt Is So Detailed

The classification prompt explicitly teaches the AI about Indian payment systems (UPI timeouts, Razorpay error codes) because general-purpose models don't have deep knowledge of these. The "How to think about this" section walks through reasoning steps that prevent common misclassifications:

- UPI timeouts being classified as abandonment (they're network issues, not intent issues)
- All card declines being treated as fraud (most are expired cards or insufficient funds)
- User cancellations being treated as errors (the customer made a deliberate choice)

### Why Examples Use Rupee Amounts

The prompt uses amounts like "₹5000", "₹200", "₹50000", "₹499", "₹49,999" rather than abstract thresholds. This grounds the AI in the Indian payment context and helps it reason about what constitutes "high value" or "low value" in INR terms.

### Why the Message Prompt Says "Like a Helpful Shopkeeper"

This metaphor was chosen to prevent corporate-speak. Without it, models tend to generate messages like "We apologize for the inconvenience in processing your transaction." The shopkeeper framing produces warmer, more natural messages - particularly important for WhatsApp, where formal language feels out of place.

The prompt also explicitly bans "Dear Sir/Madam" and "We apologize for the inconvenience" - phrases that Indian corporate communications overuse.

### Why Temperature Varies by Task

| Task | Temperature | Reason |
|------|------------|--------|
| Classification | 0.1 | Near-deterministic. The same error should always produce the same category. |
| Escalation | 0.15 | Slightly more flexibility for reasoning about novel situations. |
| Message generation | 0.4 | Creative variety. The same customer shouldn't get identical-sounding messages on retry. |

### Why `{link}` Is a Placeholder, Not Injected

The message generation prompt tells the AI to use `{link}` as a placeholder rather than a real URL. The actual payment link is substituted later by the messenger. This prevents the AI from hallucinating URLs - a real risk with LLMs. The messenger does a simple string replacement: `wa_text.replace("{link}", link)`.

### Why All Channels Are Generated in One Call

The message generator produces WhatsApp, SMS, and email text in a single AI call, even though only one channel is used per attempt. This is intentional - if the first channel fails and the system degrades to a different channel (e.g., WhatsApp fails, falls back to email), the pre-generated messages for the fallback channel are already available without a second AI call.

### Why the Escalation Prompt Receives `max_attempts`

Early versions of the escalation prompt didn't include the attempt budget. The AI would give up after 2 attempts on low-probability events, even though the budget allowed 3-4. By passing `max_attempts` and `attempts_remaining` explicitly, and instructing "Respect that budget", the AI makes better use of the computed budget.

The three-layer safety system (schema default -> AI override -> hard guard) exists because despite this prompt guidance, models still occasionally suggest `give_up` prematurely. The system trusts the budget calculation over the AI's judgment about when to stop.

### Why `personalization_hint` Exists

The classifier generates a `personalization_hint` field that flows through to the message generator. This carries insights like "customer was at checkout for 5 minutes before timeout" or "card expired 2 days ago" that help the message generator write contextually relevant messages. Without this, the message generator would only know the category name, losing the nuance the classifier discovered.

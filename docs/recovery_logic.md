# Recovery Pipeline Logic

Complete technical reference for Recovery Router's Classify, Route, Act, Measure pipeline.

Built by Albert Abishek I for the Razorpay AI Buildathon 2026 (Track 3: AI-Powered Payment Recovery).

---

## Table of Contents

1. [Entry Points](#1-entry-points)
2. [Classification Step](#2-classification-step)
3. [Routing Step -- Dynamic Budgets](#3-routing-step----dynamic-budgets)
4. [Action Step -- Message Sending](#4-action-step----message-sending)
5. [Measure Step -- Recovery Reconciliation](#5-measure-step----recovery-reconciliation)
6. [Escalation Engine](#6-escalation-engine)
7. [State Machine](#7-state-machine)
8. [Edge Cases and Safety](#8-edge-cases-and-safety)

---

## 1. Entry Points

Recovery Router has four distinct entry points, each handling a different source of recovery events.

### 1.1 Webhook Endpoint (Production Path)

**File:** `backend/app/routers/webhooks.py`, lines 29-85

This is the primary production entry point. It receives real Razorpay webhook events (e.g., `payment.failed`, `payment.captured`).

**Request flow:**

```
POST /webhook/recovery-router
  |
  +--> Rate limit check (100 requests / 60 seconds)
  +--> Body size check (max 256 KB)
  +--> HMAC-SHA256 signature verification
  +--> Redis-based deduplication
  +--> Payload normalization
  +--> Celery task dispatch
```

**Step 1 -- HMAC Verification** (`webhooks.py`, lines 20-26):

```python
def _verify_razorpay_signature(raw_body: bytes, signature: str) -> bool:
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        logger.warning("RAZORPAY_WEBHOOK_SECRET not configured -- rejecting webhook")
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

The signature comes from the `X-Razorpay-Signature` header. The function uses `hmac.compare_digest` for constant-time comparison, preventing timing attacks. If the webhook secret is not configured, all webhooks are rejected (fail-closed).

**Step 2 -- Deduplication** (`backend/app/utils/dedup.py`, lines 8-14):

```python
def is_duplicate(event_type: str, identifier: str) -> bool:
    r = get_redis()
    key = f"dedup:{event_type}:{identifier}"
    if r.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS):
        return False  # First time seeing this -- not a duplicate
    return True        # Already processed
```

Uses Redis `SET NX` (set-if-not-exists) with a 1-hour TTL. The identifier is extracted from the payload: for `payment.failed` webhooks it uses the payment entity ID; for other events it uses `payment_id`, `order_id`, or `invoice_id`, falling back to a SHA-256 hash of the full payload.

**Step 3 -- Normalization** (`backend/app/utils/normalizer.py`, lines 4-29):

Two paths:
- **Raw Razorpay `payment.failed`**: Extracts fields from the nested `payload.payment.entity` structure, converting amount from paise to rupees (divide by 100), and mapping Razorpay field names to the internal `RecoveryEventInput` schema.
- **Custom format**: Direct `RecoveryEventInput(**body)` construction.

**Step 4 -- Recovery Link Failure Detection** (`webhooks.py`, lines 59-77):

Before dispatching a new recovery event, the webhook checks whether this `payment.failed` is actually a customer failing to pay through a recovery link I already sent. It does a two-pass lookup via `_find_parent_recovery_event`:

1. Check if `notes.source == "recovery_router"` (set by my checkout page)
2. Query `recovery_attempts` for a matching `order_id` in the metadata

If a parent event is found, the webhook dispatches `handle_recovery_retry_failure` instead of `process_recovery_event`, which logs the failure on the existing event rather than creating a duplicate.

**Step 5 -- Task Dispatch** (`webhooks.py`, line 80):

```python
process_recovery_event.delay(event_data)
```

The normalized event data is dispatched as an asynchronous Celery task. The webhook returns `202 Accepted` immediately without waiting for processing.

### 1.2 Recovery Tracker Webhook

**File:** `backend/app/routers/webhooks.py`, lines 88-113

A separate webhook endpoint that listens for `payment.captured` and `payment_link.paid` events. When a customer successfully pays, this endpoint triggers the reconciliation logic (`process_payment_captured`) to match the payment back to an open recovery event and mark it as recovered.

Same security: rate limiting, body size limit, HMAC verification. Events not matching the two expected types are silently ignored.

### 1.3 Simulator Endpoint

**File:** `backend/app/routers/events.py`, lines 121-148

```
POST /api/simulate
```

This endpoint generates synthetic recovery events for testing. Key differences from the webhook path:

- **No HMAC verification** -- requires JWT authentication instead (`require_auth` dependency)
- **No deduplication** -- simulator events are intentionally allowed to repeat (IDs are prefixed with `pay_TEST_` / `order_TEST_`, which the durable dedup check skips)
- **Pre-built scenarios**: 10 scenarios covering all three leak types and various failure modes

The 10 available scenarios:

| Scenario | Leak Type | Amount Range |
|---|---|---|
| `upi_timeout` | payment_failure | 499-4999 |
| `card_expired` | payment_failure | 1999-8999 |
| `insufficient_funds` | payment_failure | 2499-12999 |
| `bank_downtime` | payment_failure | 999-4999 |
| `gateway_error` | payment_failure | 799-3999 |
| `fraud_decline` | payment_failure | 9999-24999 |
| `high_value_cart` | cart_abandonment | 2999-14999 |
| `low_value_cart` | cart_abandonment | 99-199 |
| `recent_invoice` | invoice_overdue | 5000-50000 |
| `old_invoice` | invoice_overdue | 15000-75000 |

Amounts are randomized per request to simulate realistic variance. All scenarios dispatch to the same `process_recovery_event.delay()` Celery task as the production webhook.

### 1.4 Live Checkout Endpoint

**File:** `backend/app/routers/events.py`, lines 334-377

```
POST /api/live-checkout
```

Creates a real Razorpay test-mode order via the Orders API. Returns the order ID and Razorpay key to the frontend, which then opens the Razorpay checkout modal. If the customer intentionally fails the payment (e.g., using Razorpay's test-mode failure cards), it generates a real `payment.failed` webhook that flows through the production pipeline.

This exists so you can trigger real end-to-end recovery flows without needing a production Razorpay account.

### 1.5 Invoice Scanner (Periodic Task)

**File:** `backend/app/tasks/invoice_scan.py`, lines 9-20
**Scanner:** `backend/app/services/invoice_scanner.py`, lines 11-66

A Celery Beat periodic task that runs every 6 hours (21,600 seconds, configurable via `INVOICE_SCAN_INTERVAL_SECONDS`).

**How it works:**

1. Paginate through all invoices from Razorpay's Invoices API with `status=issued`
2. For each invoice, calculate `days_overdue` from the due date
3. Skip invoices that are not yet overdue (`days_overdue < 1`)
4. Batch-check which invoice IDs already exist in `recovery_events` via a single `IN` query (`_already_tracked_batch`)
5. For each new overdue invoice, dispatch `process_recovery_event.delay()` with event_type `invoice_overdue`

This means invoices do not need an explicit webhook trigger -- the system proactively discovers them.

---

## 2. Classification Step

**File:** `backend/app/services/classifier.py`

Every event entering the pipeline is classified by AI to determine what went wrong, how likely recovery is, and what action to take. The classifier is the brain of the system.

### 2.1 The 12 Failure Categories

The system recognizes 12 distinct failure categories, organized by leak type:

**Payment Failure Categories (6):**

| Category | Meaning | Typical Probability |
|---|---|---|
| `upi_timeout` | UPI payment timed out due to network congestion or app latency. Customer was actively trying to pay. | 0.80 |
| `bank_downtime` | Bank server temporarily unavailable. Not a customer issue -- transient infrastructure failure. | 0.75 |
| `card_expired` | Customer's card has expired. They need to use a different card. | 0.50 |
| `insufficient_funds` | Customer's account does not have enough balance. They may need time to transfer funds. | 0.40 |
| `gateway_error` | Payment gateway had a technical error. Customer's payment method is fine. | 0.85 |
| `user_cancelled` | Customer actively chose to cancel the payment. They showed intent but backed out. | 0.35 |
| `unrecoverable_decline` | Bank permanently declined the payment (fraud, stolen card, blocked account). No recovery possible. | 0.00 |

**Cart Abandonment Categories (2):**

| Category | Meaning | Typical Probability |
|---|---|---|
| `high_intent_abandonment` | High-value cart (>= 200 INR) with items added. Genuine shopping intent. | 0.35 |
| `browse_only_abandonment` | Low-value cart (< 200 INR), likely just browsing. Not worth pursuing. | 0.07 |

**Invoice Overdue Categories (3):**

| Category | Meaning | Typical Probability |
|---|---|---|
| `recently_overdue` | Invoice 1-7 days past due. A friendly reminder usually works. | 0.70 |
| `moderately_overdue` | Invoice 8-30 days past due. Needs a more formal approach. | 0.40 |
| `long_overdue` | Invoice 31+ days past due. Formal communication with clear deadline needed. | 0.15 |

### 2.2 AI Classification

**File:** `classifier.py`, lines 142-177

The AI receives a structured JSON with all event fields:

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

Input fields are sanitized: control characters are stripped and values are truncated to prevent prompt injection (200 chars max for error_description, 100 for error_code, etc.).

The AI returns a JSON object with:
- `failure_category` -- one of the 12 categories
- `recovery_probability` -- 0.0 to 1.0
- `recommended_channel` -- whatsapp, email, sms, or none
- `recommended_timing` -- immediate, 5_minutes, 30_minutes, 1_hour, or 4_hours
- `reasoning` -- 2-3 sentence explanation
- `personalization_hint` -- insight for message personalization

The AI model chain is defined in `backend/app/services/ai_client.py` (lines 18-37):

```
Claude Haiku 4.5 --> Gemini 3.7 Flash --> GPT-4o-mini --> rule-based fallback
```

Each model gets 1 retry before falling through to the next. All calls go through OpenRouter with `response_format: json_object` to force JSON output. The temperature is set to 0.1 for classification (near-deterministic) and 0.15 for escalation decisions.

### 2.3 Response Validation

**File:** `ai_client.py`, lines 168-191

After parsing the AI response, each field is validated against the `RESPONSE_SCHEMA`:
- String fields are checked against allowed values; invalid values are replaced with defaults
- Float fields are clamped to min/max bounds
- Missing fields get their schema defaults

This means even if the AI hallucinates an invalid category name, the system self-corrects to a safe default rather than crashing.

### 2.4 Rule-Based Fallback

**File:** `classifier.py`, lines 244-293

When all three AI models fail, a deterministic rule-based classifier takes over. It works differently for each leak type:

**For payment failures** (`classifier.py`, lines 267-278): The system matches the `error_code` against the `FALLBACK_RULES` lookup table. If no match in the error code, it tries matching against the `error_description`. This two-pass approach handles both standardized Razorpay error codes and free-text error descriptions.

```python
FALLBACK_RULES = {
    "TIMEOUT": ("upi_timeout", 0.80, "whatsapp", "immediate"),
    "BANK_DOWNTIME": ("bank_downtime", 0.75, "whatsapp", "30_minutes"),
    "CARD_EXPIRED": ("card_expired", 0.50, "email", "immediate"),
    "INSUFFICIENT_FUNDS": ("insufficient_funds", 0.40, "sms", "4_hours"),
    # ... and so on
}
```

**For cart abandonment** (`classifier.py`, lines 253-257): Simple threshold on `cart_value` -- >= 200 INR is "high intent", below is "browse only".

**For invoices** (`classifier.py`, lines 258-265): Based on `days_overdue` -- <= 7 is recent, <= 30 is moderate, 31+ is long overdue.

The fallback classifier also provides pre-written `recommended_action`, `reasoning`, and `alternative_action` strings from the `FALLBACK_ACTIONS` dictionary (lines 180-241), so even without AI the system gives meaningful explanations.

---

## 3. Routing Step -- Dynamic Budgets

**File:** `backend/app/services/router.py`

After classification, the router makes two decisions: how many recovery attempts this event deserves, and whether to act immediately, after a delay, or not at all.

### 3.1 Max Attempts Calculation

**File:** `router.py`, lines 13-35

```python
def compute_max_attempts(amount, recovery_probability, failure_category):
    if failure_category == "unrecoverable_decline":
        return 0
    if failure_category == "browse_only_abandonment":
        return 0
    if failure_category == "user_cancelled":
        return 2
    if recovery_probability <= 0.1:
        return 1
    if recovery_probability >= 0.7 and amount >= 5000:
        return 5
    if recovery_probability >= 0.5 and amount >= 2000:
        return 4
    if recovery_probability >= 0.3 or amount >= 1000:
        return 3
    return 2
```

The logic considers three factors in priority order:

1. **Category overrides**: Some categories have hard-coded budgets regardless of amount or probability:
   - `unrecoverable_decline` --> 0 (never try)
   - `browse_only_abandonment` --> 0 (not worth it)
   - `user_cancelled` --> 2 (respect the customer's choice, light follow-up only)

2. **Probability floor**: If recovery probability is 10% or below, budget is 1 attempt (one shot, then stop).

3. **Amount x Probability matrix**: Higher value and higher probability earn more attempts:
   - High-value UPI timeout (>= 5000 INR, probability 0.80) --> 5 attempts
   - Medium-value card expired (>= 2000 INR, probability 0.50) --> 4 attempts
   - Low-value with moderate probability --> 3 attempts
   - Everything else --> 2 attempts (the safe default)

**Example decisions:**

| Scenario | Amount | Probability | Category | Max Attempts |
|---|---|---|---|---|
| High-value UPI timeout | 4999 | 0.80 | upi_timeout | 5 |
| Card expired | 3499 | 0.50 | card_expired | 4 |
| Fraud decline | 24999 | 0.00 | unrecoverable_decline | 0 |
| Browse-only cart | 99 | 0.07 | browse_only_abandonment | 0 |
| User cancelled | 999 | 0.35 | user_cancelled | 2 |
| Low-value gateway error | 799 | 0.85 | gateway_error | 5 |

### 3.2 Action Routing

**File:** `router.py`, lines 38-69

After computing `max_attempts`, the router decides the immediate action:

- **`no_action`**: If the recommended channel is `none` or the category is `unrecoverable_decline` / `browse_only_abandonment`. The event is stored but no outreach happens.
- **`send_delayed`**: If the AI recommended a non-zero timing (e.g., `30_minutes` for bank downtime). A Celery task is scheduled with `countdown=delay_seconds`.
- **`send_now`**: If the timing is `immediate`. The message is sent in the same Celery task.

The timing map:

```python
TIMING_MAP = {
    "immediate":  0 seconds,
    "5_minutes":  300 seconds,
    "30_minutes": 1800 seconds,
    "1_hour":     3600 seconds,
    "4_hours":    14400 seconds,
}
```

### 3.3 Per-Resource Cooldowns

**File:** `backend/app/utils/rate_limiter.py`, lines 25-31

```python
def check_per_resource_cooldown(resource_type, resource_id, cooldown_seconds):
    r = get_redis()
    key = f"cooldown:{resource_type}:{resource_id}"
    if r.set(key, "1", nx=True, ex=cooldown_seconds):
        return True   # Allowed -- cooldown starts now
    return False       # Blocked -- cooldown still active
```

Before sending any message, the system checks whether the customer has been contacted on this channel recently. The cooldown is 300 seconds (5 minutes) per phone number for WhatsApp and SMS, and per email address for email. This prevents spamming a customer who appears in multiple recovery events simultaneously.

The cooldown uses Redis `SET NX` with a TTL, making it atomic and self-expiring.

---

## 4. Action Step -- Message Sending

**File:** `backend/app/services/messenger.py`

The messenger implements a multi-provider architecture with automatic degradation. If the preferred channel fails, the system automatically tries alternative providers and channels rather than giving up.

### 4.1 Channel Selection and Provider Chains

Each channel has a degradation chain that tries providers in order:

**WhatsApp chain** (`messenger.py`, lines 72-101):
```
Green API (personalized text)
  --> Twilio WhatsApp (pre-approved template)
    --> Email via Resend (final fallback)
```

**SMS chain** (`messenger.py`, lines 104-138):
```
Twilio SMS
  --> Green API WhatsApp (fallback to different channel)
    --> Twilio WhatsApp (template)
      --> Email via Resend (final fallback)
```

**Email chain** (`messenger.py`, lines 141-156):
```
Resend (single provider, no fallback)
```

### 4.2 Provider Details

**Green API WhatsApp** (`messenger.py`, lines 215-244):
- Sends via the Green API HTTP API
- Phone number is cleaned (leading `+` stripped) and formatted as `{number}@c.us`
- Sends the AI-generated personalized text with the payment link embedded
- Message IDs are prefixed with `greenapi:` for tracking

**Twilio WhatsApp** (`messenger.py`, lines 195-212):
- Uses Twilio's WhatsApp Business API with a pre-approved content template (`content_sid`)
- Cannot send custom text -- limited to the template content
- Useful when Green API is down but still delivers via WhatsApp

**Twilio SMS** (`messenger.py`, lines 247-267):
- Sends the AI-generated SMS text with the payment link
- Limited to 140 characters (SMS constraint, enforced by the message generator)

**Resend Email** (`messenger.py`, lines 270-289):
- Sends HTML email with AI-personalized content
- Uses the `render_email_html` function from `message_generator.py` to build a branded HTML template
- Subject line, greeting, body, and CTA button text are all AI-generated

### 4.3 Cooldown Checks

Before trying any provider in a chain, the system checks per-resource cooldowns:

```python
if not check_per_resource_cooldown("whatsapp", phone, 300):
    path.append({"provider": "whatsapp_cooldown", "status": "skipped", "error": "Cooldown active"})
    # Fall through to email
```

If a cooldown is active, the entire phone-based chain is skipped and the system falls through to email (if available). The 300-second (5-minute) cooldown prevents the same customer from receiving multiple messages in quick succession.

### 4.4 Payment Link Generation

**File:** `backend/app/services/payment_links.py`, lines 42-105

Recovery messages include a payment link so the customer can complete payment with one tap. The system creates a Razorpay order (not a Payment Link -- the Orders API has no test-mode limit, while the Payment Links API is capped at 30 in test mode).

**How it works:**

1. Create a Razorpay order via `POST /v1/orders` with the amount, currency, and notes containing `source: recovery_router` and the `recovery_event_id`
2. Store customer PII (name, email, phone) in Redis with a random 24-byte token, expiring in 24 hours
3. Return a checkout URL: `{API_BASE_URL}/pay/{order_id}?t={token}`

The checkout page reads the token to prefill customer details, and the `notes.source = recovery_router` tag lets the webhook identify payments made through recovery links.

### 4.5 AI-Generated Messages

**File:** `backend/app/services/message_generator.py`

Every recovery message is personalized by AI. The generator receives the channel, failure category, amount, customer name, personalization hint from the classifier, and the attempt number. It produces messages for all three channels simultaneously:

- `whatsapp_text` (max ~200 chars, conversational, 1-2 emojis)
- `sms_text` (max ~140 chars, action-focused, no emojis)
- `email_subject`, `email_greeting`, `email_body`, `email_cta_text`

All messages use `{link}` as a placeholder for the payment URL, which is substituted at send time.

**Tone escalation by attempt number** (`message_generator.py`, lines 44-48):
- Attempt 0: Helpful, no pressure ("Hey, looks like something went wrong")
- Attempt 1: Gentle reminder ("Just following up")
- Attempt 2: Direct ("Your payment is still pending")
- Attempt 3+: Final, honest ("Last reminder before we close this")

If AI is unavailable, template fallback messages are used (`message_generator.py`, lines 111-135).

### 4.6 Degradation Path Logging

Every send attempt tracks its full degradation path -- an array recording each provider tried, whether it succeeded or failed, and the error:

```python
degradation_path = [
    {"provider": "green_api", "status": "failed", "error": "Green API HTTP 500"},
    {"provider": "twilio_whatsapp", "status": "failed", "error": "Twilio not configured"},
    {"provider": "resend", "status": "sent", "error": None},
]
```

This is stored in the `recovery_attempts.metadata` column, making it possible to audit exactly what happened for every outreach attempt.

### 4.7 Delivery Tracking

The system tracks "sent" status -- meaning the provider accepted the message for delivery. It does not currently implement delivery confirmation (read receipts, delivery webhooks from Twilio/Green API). The `outcome` field on a recovery attempt is:

- `"sent"` -- provider accepted the message
- `"failed"` -- provider returned an error
- `"blocked"` -- per-resource cooldown was active (message not sent)

---

## 5. Measure Step -- Recovery Reconciliation

**File:** `backend/app/services/recovery_tracker.py`

When a customer pays, the `payment.captured` webhook triggers reconciliation. The tracker matches the payment to an open recovery event and determines whether the recovery was driven by my outreach or happened organically.

### 5.1 Four-Strategy Matching

**File:** `recovery_tracker.py`, lines 84-108

The tracker tries four matching strategies in order, stopping at the first hit:

```python
# Strategy 1: notes.recovery_event_id
# Set when I generated the payment link -- most reliable
res = sb.table("recovery_events").select("*").eq("id", int(recovery_event_id))...

# Strategy 2: payment_link reference_id
# My order_id stored as the payment link's reference_id
res = sb.table("recovery_events").select("*").eq("order_id", reference_id)...

# Strategy 3: order_id from the payment entity
# Match on the original order (skips TEST_ prefixed IDs)
res = sb.table("recovery_events").select("*").eq("order_id", order_id)...

# Strategy 4: payment_id from the payment entity
# Last resort -- match on the original payment ID
res = sb.table("recovery_events").select("*").eq("payment_id", payment_id)...
```

Only events in `pending`, `paused`, or `exhausted` status are eligible for matching. This means already-recovered or cancelled events cannot be matched again.

### 5.2 Reconciliation Checks

Before marking an event as recovered, the tracker runs several validation checks:

**Entity status validation** (`recovery_tracker.py`, lines 48-53):
The payment entity's status must be `"captured"`. If it is anything else (e.g., `"authorized"` but not captured), the reconciliation is rejected. This prevents counting payments that have not actually been settled.

**Double-attribution prevention** (`recovery_tracker.py`, lines 64-82):
Before matching, the tracker checks whether this `payment_id` has already been attributed to any recovery event (via the `recovered_payment_id` column or by checking for events in `recovered`/`organic_recovery` status with the same `payment_id`). If found, the reconciliation returns `"duplicate_attribution"` and no change is made.

**Currency match** (`recovery_tracker.py`, lines 116-123):
The captured payment's currency must match the recovery event's currency. A payment in USD cannot recover an event denominated in INR.

**Amount tolerance** (`recovery_tracker.py`, lines 125-133):
The captured amount must be within 1% of the event amount (tolerance = 0.01). This allows for minor rounding differences between paise-to-rupee conversions without accepting wildly different amounts. Both amounts must be positive for this check to apply.

### 5.3 Ghost Recovery Prevention

**File:** `recovery_tracker.py`, lines 146-173

The critical question: did my outreach cause this payment, or would the customer have paid anyway?

```python
# Re-read the latest attempt_count (may have changed since initial query)
fresh = sb.table("recovery_events").select("attempt_count").eq("id", event["id"]).limit(1).execute()
actual_attempt_count = (fresh.data[0]["attempt_count"] if fresh.data else ...) or 0

# Check if any outreach message was successfully delivered
sent_attempts = sb.table("recovery_attempts").select("id").eq(
    "recovery_event_id", event["id"]
).eq("outcome", "sent").limit(1).execute()
has_successful_outreach = bool(sent_attempts.data)

is_organic = actual_attempt_count == 0 and not has_successful_outreach
```

A recovery is classified as **organic** when both conditions are true:
1. `actual_attempt_count == 0` -- no outreach attempts have been counted
2. `not has_successful_outreach` -- no recovery attempt has `outcome = "sent"`

This dual check is deliberately conservative. Even if `attempt_count` is 0 (perhaps due to a bug or race condition), if any attempt record shows successful delivery, the recovery is attributed to my outreach.

**Organic recoveries** are stored with status `"organic_recovery"` rather than `"recovered"`, clearly separating them in analytics. This prevents inflating the AI recovery rate with payments that would have happened regardless.

**Outreach-driven recoveries** get status `"recovered"` and are attributed to the recovery system.

### 5.4 Race Condition Protection

The update uses an `in_("status", recoverable_statuses)` guard:

```python
upd = sb.table("recovery_events").update(update_data).eq("id", event["id"]).in_("status", recoverable_statuses).execute()
if not upd.data:
    logger.warning("Event %d already processed (race avoided)", event["id"])
    return {"status": "already_processed", "event_id": event["id"]}
```

If two `payment.captured` webhooks arrive simultaneously for the same event, only the first one succeeds (the second finds the status already changed and returns `"already_processed"`). This is optimistic concurrency control -- no locks needed.

---

## 6. Escalation Engine

**File:** `backend/app/services/escalation.py` and `backend/app/tasks/escalation.py`

The escalation engine is the heartbeat of the recovery system. It runs every 5 minutes via Celery Beat, finds events that are due for their next action, and decides what to do.

### 6.1 Celery Beat Schedule

**File:** `backend/app/tasks/escalation.py`, lines 14-16

```python
@celery_app.task
def run_escalation_cycle() -> dict:
    """Periodic task (every 5 min via Beat): fetch due events, escalate."""
```

The cycle acquires a global Redis lock (`lock:escalation`, TTL 240 seconds) to prevent multiple workers from running escalation simultaneously. If the lock is held, the cycle is skipped.

**Event selection** (`escalation.py` task, lines 27-36):

```python
res = (
    sb.table("recovery_events")
    .select("*")
    .eq("status", "pending")
    .lte("next_action_at", now)
    .order("recovery_probability", desc=True)  # High probability first
    .order("next_action_at", desc=False)        # Then oldest first
    .limit(50)                                   # Max 50 per cycle
    .execute()
)
```

Events are prioritized by recovery probability (highest first), then by how long they have been waiting. Only `pending` events with `next_action_at <= now` are selected.

**Pre-filters** (`escalation.py` task, lines 42-61):

Before sending events to the escalation engine, several are filtered out:
- Events where the customer has opted out
- Events where the recovery window has expired (marked `exhausted` with strategy `window_expired`)
- Events where `attempt_count >= max_attempts` (marked `exhausted` with strategy `max_attempts_reached`)
- Events with `failure_category == "unrecoverable_decline"`
- Events with `recovery_probability == 0`

### 6.2 The 72-Hour Recovery Window + 24-Hour Extension

**File:** `backend/app/tasks/escalation.py`, lines 75-103

Every event gets a 72-hour recovery window set at creation time. After 72 hours, the event is normally marked as `exhausted` with strategy `window_expired`.

**Exception -- the 24-hour extension** (`escalation.py` task, lines 78-89):

If the window expires but `attempt_count == 0` and `max_attempts > 0`, it means no outreach was ever successfully sent (perhaps all providers were down, or cooldowns blocked every attempt). In this case, the system extends the window by 24 hours and sets `next_action_at` to now, giving the event one more chance:

```python
if attempt_count == 0 and max_attempts > 0:
    sb.table("recovery_events").update({
        "status": "pending",
        "current_strategy": "retry_after_window",
        "recovery_window_ends": (now + timedelta(hours=24)).isoformat(),
        "next_action_at": now.isoformat(),
    }).eq("id", event["id"]).eq("status", "pending").execute()
```

### 6.3 AI-Driven Escalation Decisions

**File:** `backend/app/services/escalation.py`, lines 256-360

For each actionable event, the escalation engine asks the AI to decide the next move. The AI receives:

- Event context: type, amount, currency, failure category, recovery probability
- Attempt budget: `attempt_count`, `max_attempts`, `attempts_remaining`
- Previous attempt history: channel used, outcome, and notes for each attempt
- Blocked channels (cooldown-blocked) and failed channels (delivery failures)
- Available contact methods: `has_email`, `has_phone`
- The backup plan from the original classification

The AI returns:

```json
{
  "action": "send" or "give_up",
  "channel": "whatsapp" or "email" or "sms",
  "tone": "friendly" or "firm" or "urgent" or "final",
  "reasoning": "2-3 sentences"
}
```

### 6.4 Three-Layer Safety Against Premature Give-Up

The system has three layers preventing the AI from giving up too early:

**Layer 1 -- Schema default** (`escalation.py`, line 81):
The `ESCALATION_SCHEMA` defaults `action` to `"send"`, so if the AI returns an invalid action, it defaults to sending.

**Layer 2 -- AI override in `_get_escalation_decision`** (`escalation.py`, lines 310-351):
Even if the AI says `give_up`, the function checks whether attempts remain:

```python
if result.get("action") == "give_up" and attempt_count < max_attempts:
    # Check if there are truly no untried channels with contact info
    if not all_truly_exhausted or attempt_count == 0:
        result = {
            "action": "send",
            "channel": _pick_next_channel(last_channel, event, avoid=blocked_chs),
            "tone": "firm" if attempt_count <= 2 else "urgent",
            "reasoning": "Override: AI suggested give_up but attempts remain.",
        }
```

It only allows give_up when ALL of these are true:
- Every outreach attempt has failed (all outcomes are `"failed"`)
- No untried channels remain (given available contact info)
- `attempt_count > 0` (never give up on the first escalation)

**Layer 3 -- Hard guard in `run_escalation`** (`escalation.py`, lines 136-155):
Even after the decision function returns, the main loop double-checks:

```python
if decision.get("action") == "give_up":
    if attempt_count < max_attempts:
        # Force a send instead
        decision = {
            "action": "send",
            "channel": _pick_next_channel(...),
            "tone": "firm" if attempt_count <= 2 else "urgent",
            "reasoning": f"Safety override: give_up blocked because {remaining} attempts remain.",
        }
```

### 6.5 Quiet Hours

**File:** `escalation.py`, lines 21-38

No messages are sent between 9 PM and 9 AM IST (`Asia/Kolkata` timezone). If escalation runs during quiet hours, the event's `next_action_at` is set to the next 9 AM IST:

```python
QUIET_START_HOUR = 21  # 9 PM IST
QUIET_END_HOUR = 9     # 9 AM IST

def _is_quiet_hours(now_utc=None):
    now = (now_utc or datetime.now(timezone.utc)).astimezone(IST)
    return now.hour >= QUIET_START_HOUR or now.hour < QUIET_END_HOUR
```

This applies to both the initial send (in `process_recovery_event`) and escalation cycles.

### 6.6 Channel Rotation

**File:** `escalation.py`, lines 363-384

When the AI or safety overrides need to pick a different channel, `_pick_next_channel` applies this logic:

1. Build a preference list: WhatsApp (if phone available and not blocked), then email (if available and not blocked), then SMS (if phone available and not blocked)
2. Pick the first channel that differs from the last one used
3. If all channels match the last used, pick the first available
4. Ultimate fallback: email if available, otherwise WhatsApp

The `avoid` set contains channels that are blocked (cooldown) or failed (delivery error), ensuring the system does not retry a broken channel.

### 6.7 Retry Delays Between Escalations

**File:** `escalation.py`, lines 430-441

After each successful send, the next escalation is scheduled based on the failure category:

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

The logic: urgent, transient failures (UPI timeout, gateway error) get short delays. Customer-side issues (insufficient funds, card expired) get longer delays to give the customer time to fix the problem. Invoices get the longest delays because they are less time-sensitive.

---

## 7. State Machine

### 7.1 Event Lifecycle States

Every recovery event follows this state machine:

```
                      +--> no_action_needed
                      |
  [created] --> pending --+--> paused (merchant)
                      |   |      |
                      |   |      +--> resumed --> pending
                      |   |
                      |   +--> recovered (outreach-driven)
                      |   |
                      |   +--> organic_recovery (no outreach)
                      |   |
                      |   +--> exhausted
                      |   |      |
                      |   |      +--> recovered (late payment)
                      |   |
                      |   +--> cancelled (merchant)
                      |
                      +--> [delayed send] --> pending
```

**State definitions:**

| Status | Meaning | Terminal? |
|---|---|---|
| `pending` | Actively being worked on. Has a `next_action_at` for the escalation engine. | No |
| `paused` | Merchant manually paused recovery. No escalation until resumed. | No |
| `no_action_needed` | Classification determined no recovery action should be taken (e.g., fraud, browse-only). | Yes |
| `recovered` | Payment was captured and attributed to my outreach. | Yes |
| `organic_recovery` | Payment was captured but no successful outreach was sent (customer paid on their own). | Yes |
| `exhausted` | All recovery attempts used or recovery window expired. | Semi-terminal* |
| `cancelled` | Merchant manually cancelled recovery. | Yes |

*Exhausted events can still transition to `recovered` if a late payment comes in.

### 7.2 State Transitions and Triggers

**pending --> recovered/organic_recovery:**
Triggered by a `payment.captured` webhook matching the event (via `process_payment_captured`).

**pending --> exhausted:**
Two paths:
1. `attempt_count >= max_attempts` after a successful send (`_update_event_state` in escalation)
2. Recovery window expired (`_mark_window_expired` in the escalation cycle task)
3. AI decides `give_up` and all safety layers agree (all channels truly exhausted)

**pending --> paused:**
Triggered by `PATCH /api/events/{id}/control` with `action: "pause"`.

**paused --> pending:**
Triggered by `PATCH /api/events/{id}/control` with `action: "resume"`. Sets `next_action_at` to now so escalation picks it up immediately.

**pending/paused/exhausted --> cancelled:**
Triggered by `PATCH /api/events/{id}/control` with `action: "cancel"`. Clears `next_action_at` and `recovery_window_ends`.

**exhausted --> recovered:**
A late payment captured webhook can still match an exhausted event (the recoverable statuses list includes `exhausted`).

### 7.3 Optimistic Concurrency

Throughout the codebase, state transitions use Supabase's `.eq("status", expected_status)` as a guard:

```python
sb.table("recovery_events").update({
    "status": "exhausted",
    ...
}).eq("id", event["id"]).eq("status", "pending").execute()
```

If another process has already changed the status (e.g., a recovery webhook arrived between the read and the update), the update returns no rows and the code detects this:

```python
if not upd.data:
    logger.warning("Event %d: status already changed", event["id"])
```

This is optimistic concurrency control -- no locking required for correctness, just the conditional update.

### 7.4 Distributed Redis Locks

For operations that involve read-modify-write sequences (where a conditional update alone is not sufficient), the system uses Redis distributed locks:

**Event-level lock** (`escalation.py`, lines 87-94):
```python
def _acquire_event_lock(event_id: int, ttl: int = 300) -> bool:
    r = get_redis()
    return bool(r.set(f"lock:event:{event_id}", "1", nx=True, ex=ttl))
```

Each event is locked for up to 300 seconds while the escalation engine processes it. If the lock is held, the event is skipped (another worker is handling it).

**Escalation cycle lock** (`escalation.py` task, lines 18-19):
A global lock (`lock:escalation`, TTL 240 seconds) prevents multiple workers from running the escalation cycle simultaneously.

**Delayed send lock** (`recovery.py`, lines 413-414):
When a delayed send fires, it acquires `lock:event:{event_id}` to prevent collision with a concurrent escalation.

---

## 8. Edge Cases and Safety

### 8.1 What Happens When AI Returns Invalid Output

**File:** `backend/app/services/ai_client.py`, lines 168-191

The `_validate_fields` function silently corrects invalid AI output:
- If `failure_category` is not one of the 12 allowed values, it defaults to `"gateway_error"`
- If `recovery_probability` is not a float between 0 and 1, it is clamped to bounds or defaults to 0.5
- If `recommended_channel` is not `whatsapp`/`email`/`sms`/`none`, it defaults to `"email"`

If the AI returns malformed JSON (not parseable), `_parse_json` handles markdown code fences (```json...```) by stripping them. If parsing still fails, the exception propagates up and the next model in the chain is tried.

If all three models fail or return None, `classify_event` falls back to rule-based classification. The system never crashes due to AI output -- it always degrades gracefully.

### 8.2 What Happens When All Messaging Providers Fail

**File:** `backend/app/services/messenger.py`, lines 172-181

When every provider in the degradation chain fails, the `_fail` function returns:

```python
{
    "success": False,
    "message_id": None,
    "error": "All providers failed",
    "channel_used": intended_channel,
    "degraded_from": None,
    "degradation_path": [... full trace of each failed provider ...],
}
```

In the initial send path (`recovery.py`, lines 274-280), a failed send sets `current_strategy` to `"first_contact_failed"` and schedules a retry in 15 minutes:

```python
update_data = {
    "current_strategy": "first_contact_failed",
    "next_action_at": (now + timedelta(minutes=15)).isoformat(),
}
```

In the escalation path (`escalation.py`, lines 224-229), a failed send also reschedules in 15 minutes. The event remains `pending` and will be picked up again by the next escalation cycle.

The attempt is logged with `outcome: "failed"` and the full `degradation_path` in metadata, so the AI can see what failed when making the next escalation decision.

### 8.3 What Happens When Redis Is Down

**Deduplication fails open**: If Redis is unavailable, `is_duplicate()` will raise an exception. The webhook handler does not catch this specifically, so the request will return a 500 error and Razorpay will retry the webhook (standard webhook retry behavior).

**Rate limiting fails open**: Same pattern -- Redis unavailability causes the rate limiter to raise, returning 500.

**Locks fail open**: The `_acquire_event_lock` function will raise if Redis is unavailable. In `run_escalation`, this causes the event to be skipped for this cycle. The `try/finally` block ensures lock release is attempted but won't crash if Redis was never reachable.

**Celery tasks may not dispatch**: Since Redis is both the Celery broker and result backend, a complete Redis outage means tasks cannot be queued. The webhook will return 503 ("Service temporarily unavailable").

The system is designed to be safe-by-default: Redis outage causes failures that are visible and retryable, never silent data corruption.

### 8.4 Premature Give-Up Prevention (Bug #1 Fix)

**Problem:** The AI escalation engine would sometimes recommend `give_up` prematurely -- before all budgeted attempts were used. This happened because the AI was making qualitative judgments ("probability is low, not worth it") that contradicted the already-computed budget.

**Fix -- Three layers:**

**Application Layer 1** (`escalation.py`, `_get_escalation_decision`, lines 310-351):
When the AI says `give_up` but `attempt_count < max_attempts`, the function checks whether there are truly no untried channels. If untried channels exist (or if `attempt_count == 0`), it overrides the AI's decision to `send` on a different channel.

**Application Layer 2** (`escalation.py`, `run_escalation`, lines 136-155):
A second check in the main loop catches any `give_up` that slipped through Layer 1. If `attempt_count < max_attempts`, it forces a `send` with a safety override message.

**Database Layer** (`backend/migrations/004_prevent_premature_exhaustion.sql`):
A PostgreSQL `BEFORE UPDATE` trigger that catches any attempt to set `status = 'exhausted'` when the budget is not used up:

```sql
CREATE OR REPLACE FUNCTION prevent_premature_exhaustion()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'exhausted' AND (OLD.status IS NULL OR OLD.status != 'exhausted') THEN
    IF (COALESCE(NEW.attempt_count, 0) < COALESCE(NEW.max_attempts, 5))
       AND COALESCE(NEW.max_attempts, 5) > 0
       AND NEW.skip_reason IS NULL THEN
      RAISE WARNING 'Blocked premature exhaustion of event %';
      NEW.status := OLD.status;           -- revert to previous status
      NEW.current_strategy := OLD.current_strategy;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
```

This trigger acts as a last defense, catching not just application code bugs but also external writers (manual SQL queries, n8n workflows, etc.) that might accidentally mark events as exhausted.

The trigger allows exhaustion in three cases:
1. `attempt_count >= max_attempts` (budget actually spent)
2. `max_attempts = 0` (unrecoverable events that should never be attempted)
3. `skip_reason IS NOT NULL` (application code provided an explicit reason, e.g., window expired)

### 8.5 TOCTOU Race Condition Handling (Bug #2 Fix)

**Problem:** Time-of-check-to-time-of-use race: the escalation reads an event as `pending`, but by the time it processes and writes back, the event may have been recovered, paused, or cancelled by another concurrent process (e.g., a `payment.captured` webhook arriving between the read and write).

**Fix -- Two mechanisms:**

**Conditional updates** (throughout the codebase):
Every status transition includes a `.eq("status", expected_status)` guard:

```python
sb.table("recovery_events").update({"status": "exhausted"})
    .eq("id", event["id"])
    .eq("status", "pending")  # Only if still pending
    .execute()
```

If the status changed between read and write, the update matches zero rows and the code detects the race.

**Fresh re-read after lock acquisition** (`escalation.py`, lines 111-121):
After acquiring the event lock in `run_escalation`, the engine re-reads the event's current status before proceeding:

```python
fresh = sb.table("recovery_events").select(
    "status,attempt_count,max_attempts,escalation_level"
).eq("id", event["id"]).limit(1).execute()
if not fresh.data or fresh.data[0].get("status") != "pending":
    results.append({"event_id": event["id"], "action": "skipped_not_pending"})
    continue
event.update(fresh.data[0])
```

This closes the gap between the batch query (which fetched 50 events at once) and the per-event processing, ensuring the engine works with the latest state.

### 8.6 Permanent Task Failures

**File:** `backend/app/tasks/recovery.py`, lines 292-311

If a Celery task encounters an unrecoverable error (not in the `TRANSIENT_ERRORS` list), it logs a special "system" attempt with `permanent_failure: True` in metadata. This creates a visible audit trail that something went wrong, even if the event itself could not be processed.

Transient errors (connection timeouts, network issues) trigger Celery's built-in retry mechanism with exponential backoff:

```python
backoff = 60 * (2 ** self.request.retries)  # 60s, 120s, 240s
raise self.retry(exc=exc, countdown=backoff)
```

Max retries: 3 for `process_recovery_event`, 2 for `handle_recovery_retry_failure` and `_send_delayed`.

### 8.7 Premature Exhaustion Fix-Up Migration

**File:** `backend/app/routers/events.py`, lines 495-551

The `POST /api/migrate/fix-premature-exhaustion` endpoint is a one-time migration that fixes events that were exhausted prematurely due to cooldown failures being counted as real failures. It:

1. Finds `exhausted` events where `attempt_count < max_attempts`
2. Reclassifies `"failed"` attempts with `send_error == "Cooldown active"` as `"blocked"` (they were not real failures)
3. If the event had at least one successful send, re-opens it as `pending` with strategy `"first_contact_sent"`
4. If no sends ever succeeded, re-opens it as `pending` with strategy `"first_contact_failed"` and schedules a retry in 15 minutes

---

## Complete Event Lifecycle Trace

Here is the complete path of a single recovery event from entry to resolution, using a real-world example: a 4999 INR UPI payment timeout.

**1. Webhook arrives** at `POST /webhook/recovery-router`
   - HMAC signature verified
   - Redis dedup check passes (first time seeing this payment ID)
   - Payload normalized from Razorpay's nested format
   - `process_recovery_event.delay(event_data)` dispatched to Celery

**2. Celery worker picks up the task** (`process_recovery_event`)
   - Durable dedup: checks DB for existing event with same `payment_id` -- none found
   - AI classifies: `failure_category=upi_timeout`, `recovery_probability=0.85`, `recommended_channel=whatsapp`, `recommended_timing=immediate`
   - `compute_max_attempts(4999, 0.85, "upi_timeout")` --> 5
   - Event inserted into `recovery_events` with `status=pending`, `recovery_window_ends=now+72h`
   - `route_action` returns `send_now` on WhatsApp

**3. Payment link created**
   - Razorpay order created via Orders API
   - Customer PII stored in Redis with a token
   - Checkout URL generated: `{base}/pay/{order_id}?t={token}`

**4. Message sent**
   - AI generates personalized WhatsApp message
   - Green API WhatsApp attempted first -- succeeds
   - Recovery attempt logged: `attempt_number=1`, `channel_used=whatsapp`, `outcome=sent`
   - Event updated: `attempt_count=1`, `current_strategy=first_contact_sent`, `next_action_at=now+1h`

**5. One hour later -- escalation cycle runs**
   - Event is selected (pending, `next_action_at <= now`)
   - AI decides: `action=send`, `channel=email`, `tone=firm` (switch channel after WhatsApp)
   - New payment link created, email sent via Resend
   - Attempt logged: `attempt_number=2`, `channel_used=email`, `outcome=sent`
   - Event updated: `attempt_count=2`, `next_action_at=now+1h`

**6. Customer clicks the recovery link and pays**
   - Razorpay sends `payment.captured` webhook to `/webhook/recovery-tracker`
   - Recovery tracker matches via `notes.recovery_event_id` (Strategy 1)
   - Entity status check: "captured" -- passes
   - Currency check: INR matches -- passes
   - Amount check: within 1% tolerance -- passes
   - Double-attribution check: payment_id not previously attributed -- passes
   - `attempt_count=2`, has successful outreach (`outcome=sent` exists) --> NOT organic
   - Event updated: `status=recovered`, `recovered_at=now`, `recovered_amount=4999`

**7. Event complete.** No further escalation. The dashboard shows this as an AI-recovered payment.

# Recovery Router -- Architecture Document

Built by Albert Abishek I for the Razorpay AI Buildathon 2026 (Track 3: AI-Powered Revenue Recovery).

---

## 1. System Overview

Recovery Router is an async, event-driven payment recovery engine. It ingests three kinds of revenue leaks -- payment failures, cart abandonments, and overdue invoices -- through a single webhook pipeline, classifies them with AI, routes recovery messages across WhatsApp/Email/SMS with multi-provider fallback, and measures outcomes by closing the feedback loop when payments land.

### Six Components

| Component | Role | Technology |
|---|---|---|
| **FastAPI API** | HTTP entry point: webhooks, REST API, hosted checkout pages | Python 3.12, FastAPI, Uvicorn |
| **Celery Worker** | Async task execution: classification, message sending, escalation | Celery 5 with prefork pool |
| **Celery Beat** | Periodic scheduler: escalation sweeps (5 min), invoice scans (6 h) | Celery Beat |
| **React Frontend** | Merchant dashboard: live feed, analytics, simulator, audit logs | React 19, Vite 8, Tailwind 4 |
| **Redis** | Message broker, task result backend, dedup cache, rate limiter, distributed locks | Redis (Railway-hosted) |
| **Supabase PostgreSQL** | Persistent storage, Realtime subscriptions for live dashboard updates | Supabase (managed Postgres) |

### System Diagram

```
                           Razorpay Webhooks
                      (payment.failed, payment.captured,
                       payment_link.paid)
                                 |
                                 v
                     +---------------------+
                     |    FastAPI API       |
                     |  (Uvicorn on :8000)  |
                     |                     |
                     |  /webhook/recovery-router   <-- failure events
                     |  /webhook/recovery-tracker  <-- success events
                     |  /api/events, /analytics    <-- dashboard REST
                     |  /api/simulate              <-- test event generator
                     |  /pay/{order_id}            <-- hosted checkout
                     +-----+-------+-------+
                           |       |       |
            +--------------+       |       +------------------+
            |                      |                          |
            v                      v                          v
    +---------------+     +----------------+         +----------------+
    |    Redis      |     |   Supabase     |         | React Frontend |
    | (broker +     |     |  PostgreSQL    |         |  (Vercel)      |
    |  cache +      |     |                |         |                |
    |  locks +      |<--->|  recovery_     |<------->|  Supabase      |
    |  rate limit)  |     |  events        |Realtime |  Realtime      |
    |               |     |  recovery_     |  Sub    |  Live Feed     |
    +-------+-------+     |  attempts      |         +----------------+
            |              +----------------+
            v
    +-------+--------+       +------------------+
    |  Celery Worker  |       |   Celery Beat    |
    |  (prefork x2)   |       |                  |
    |                  |       | escalation-5min  |
    |  Tasks:          |       | invoice-scan-6h  |
    |  - classify      |       +--------+---------+
    |  - route         |                |
    |  - generate link |                |
    |  - send message  |<---------------+
    |  - log attempt   |
    +---+---------+----+
        |         |
        v         v
  +---------+  +------------------+
  |OpenRouter|  | Message Providers|
  |  AI API  |  |                  |
  | (3-model |  | WhatsApp: Green  |
  | fallback)|  |   API + Twilio   |
  |          |  | SMS: Twilio      |
  | Haiku    |  | Email: Resend    |
  | Gemini   |  +------------------+
  | GPT-4o   |
  +---------+         +-------------------+
                       | Razorpay Orders   |
                       | API (payment link |
                       | generation)       |
                       +-------------------+
```

### Data Flow: Webhook to Recovery

```
Webhook arrives
    |
    +-> Body size check (max 256 KB)
    +-> HMAC-SHA256 signature verification
    +-> Rate limit check (100 req/min per endpoint)
    +-> Redis dedup check (1h TTL, keyed on payment_id/order_id)
    +-> Payload normalization (Razorpay raw or custom format)
    +-> Parent event check (is this a retry on my recovery link?)
    |       |
    |       +--[yes]--> handle_recovery_retry_failure.delay()
    |       |               (log attempt on parent, don't create new event)
    |       |
    |       +--[no]---> process_recovery_event.delay()
    |                       |
    v                       v
  HTTP 202               Celery Worker picks up task
  "accepted"                 |
                             +-> AI Classification (3-model fallback -> rules)
                             +-> DB-level dedup check (payment_id/order_id/invoice_id unique indexes)
                             +-> Insert recovery_events row
                             +-> Route action (send_now / send_delayed / no_action)
                             +-> Quiet hours check (9 PM - 9 AM IST)
                             +-> Generate Razorpay Order + hosted checkout URL
                             +-> AI-personalized message generation
                             +-> Send via channel (WhatsApp -> SMS -> Email fallback chain)
                             +-> Log recovery_attempts row
                             +-> Schedule next_action_at for escalation
```

---

## 2. Backend Architecture

The backend lives in `backend/app/` and follows a layered structure: routers handle HTTP, services contain business logic, tasks define Celery work, and utils provide shared infrastructure.

### 2.1 Application Entry Point

**`backend/app/main.py`** -- FastAPI app creation, middleware, router registration.

- Creates the FastAPI instance with CORS middleware configured for Vercel frontend origins plus a regex for `recovery-router*.vercel.app` preview deploys.
- Registers five router modules.
- Startup hook pings Redis to verify connectivity.
- Login endpoint: accepts a password, returns the `APP_PASSWORD` as a bearer token. This is a simple shared-secret auth -- the dashboard is single-tenant.

### 2.2 Routers

#### `backend/app/routers/webhooks.py` -- Webhook Ingestion

Two POST endpoints that Razorpay calls:

1. **`POST /webhook/recovery-router`** -- Entry point for all failure events.
   - Rate limited to 100 requests per 60 seconds.
   - Reads raw body, enforces 256 KB size limit.
   - HMAC-SHA256 signature verification against `RAZORPAY_WEBHOOK_SECRET` using `hmac.compare_digest` (timing-safe).
   - Dedup: extracts a stable identifier (payment entity ID or hash of payload), checks Redis with 1-hour TTL.
   - Normalizes payload: handles both raw Razorpay `payment.failed` webhook format (nested `payload.payment.entity`) and custom flat format.
   - Parent event detection: if this `payment.failed` webhook is from a recovery payment link I sent, routes to `handle_recovery_retry_failure` instead of creating a duplicate event.
   - Dispatches `process_recovery_event.delay(event_data)` to Celery.

2. **`POST /webhook/recovery-tracker`** -- Feedback loop for successful payments.
   - Same auth and rate limiting as above.
   - Handles `payment.captured` and `payment_link.paid` events.
   - Calls `process_payment_captured()` synchronously (no Celery -- it must update status before the next escalation cycle).

#### `backend/app/routers/events.py` -- Dashboard API + Simulator

Protected by `require_auth` (bearer token from login).

- **`GET /api/events`** -- Paginated event list with status/type/date filters.
- **`GET /api/events/counts`** -- Status counts for dashboard tabs.
- **`GET /api/events/{event_id}/trace`** -- Full event trace: event data + all attempts + structured timeline. Builds a step-by-step timeline (event_received -> classified -> payment_link_created -> outreach_attempt -> recovered/exhausted).
- **`POST /api/simulate`** -- 10 pre-built scenarios (upi_timeout, card_expired, insufficient_funds, bank_downtime, gateway_error, fraud_decline, high_value_cart, low_value_cart, recent_invoice, old_invoice) with randomized amounts. Dispatches to Celery like a real webhook.
- **`PATCH /api/events/{event_id}/control`** -- Pause, resume, or cancel recovery for a specific event. Uses optimistic concurrency: updates only where status matches expected value, returns 409 on conflict.
- **`POST /api/live-checkout`** -- Creates a real Razorpay test-mode order for live payment testing.
- **`DELETE /api/reset/all-data`** -- Deletes all data and resets sequences. Requires `?confirm=yes-delete-everything`.
- Debug endpoints for manual escalation testing.

#### `backend/app/routers/analytics.py` -- Analytics

- **`GET /api/analytics`** -- Aggregated recovery metrics with date range filtering. Delegates to `services/analytics.py`.

#### `backend/app/routers/checkout.py` -- Hosted Checkout Page

- **`GET /pay/{order_id}`** -- Server-rendered HTML page that opens Razorpay Standard Checkout.
  - Customer PII is NOT in the URL -- it's stored in Redis with a random token (`?t=<token>`).
  - Auto-opens Razorpay checkout 500ms after page load.
  - Sets `notes.source = "recovery_router"` on the payment so the tracker webhook can identify it.
  - Order ID validated against regex `^order_[A-Za-z0-9]{8,30}$`.
  - All user-supplied strings escaped for both HTML and JavaScript contexts.

#### `backend/app/routers/health.py` -- Health Check

- **`GET /api/health`** -- Checks Redis, Celery worker availability (with 5s timeout), and Supabase connectivity. Returns `"ok"` or `"degraded"` with per-service status.

### 2.3 Services

#### `backend/app/services/classifier.py` -- AI Event Classification

The classification engine. Uses AI to analyze each event and decide:
- **failure_category**: one of 12 categories (upi_timeout, bank_downtime, card_expired, insufficient_funds, gateway_error, user_cancelled, unrecoverable_decline, high_intent_abandonment, browse_only_abandonment, recently_overdue, moderately_overdue, long_overdue).
- **recovery_probability**: 0.0 to 1.0.
- **recommended_channel**: whatsapp, email, sms, or none.
- **recommended_timing**: immediate, 5_minutes, 30_minutes, 1_hour, 4_hours.
- **reasoning**: human-readable explanation.
- **personalization_hint**: key insight for message personalization.

The system prompt is detailed (70 lines) and teaches the AI to think about Indian payment methods (UPI timeouts are high-recovery because the customer was actively paying), amount-based channel selection, cancellation detection, and honest probability estimation.

Fallback: if all AI models fail, a rule-based classifier maps error codes to categories via `FALLBACK_RULES` dictionary. Each category has a pre-defined action description and reasoning via `FALLBACK_ACTIONS`.

#### `backend/app/services/ai_client.py` -- OpenRouter AI with 3-Model Fallback

Central AI client that routes through OpenRouter with automatic model failover:

1. **Claude Haiku 4.5** (12s timeout, 1 retry)
2. **Gemini 3.7 Flash** (10s timeout, 1 retry)
3. **GPT-4o-mini** (12s timeout, 1 retry)

If all three models fail (rate limits, timeouts, invalid responses), returns `None` and the caller falls back to rules. Uses a persistent `httpx.Client` with connection pooling. Handles markdown-fenced JSON responses. Validates and fixes response fields against an expected schema.

This same client is used for both classification and message generation, giving the system consistent AI behavior across the pipeline.

#### `backend/app/services/router.py` -- Action Routing

Deterministic routing from classification output to action plan:

- `no_action`: unrecoverable_decline, browse_only_abandonment, or channel == "none".
- `send_now`: immediate timing.
- `send_delayed`: non-zero timing (5 min to 4 hours).

Also computes `max_attempts` dynamically based on amount, probability, and failure category:
- Unrecoverable/browse-only: 0 attempts.
- User cancelled: 2 attempts.
- High probability + high amount: up to 5 attempts.
- Low probability: 1-2 attempts.

This budget system prevents wasting outreach on low-value events while ensuring high-value recoverable events get thorough follow-up.

#### `backend/app/services/escalation.py` -- AI-Powered Escalation Engine

The escalation engine re-analyzes events that haven't been recovered after the initial outreach. It uses a second AI call with the `ESCALATION_PROMPT` that provides the full attempt history and asks the AI to decide the next move.

Key behaviors:
- **Channel rotation**: AI considers which channels have been tried, which were blocked (cooldown), and which failed (provider error). It picks a different channel.
- **Tone progression**: friendly -> firm -> urgent -> final, based on attempt count.
- **Budget enforcement**: the AI might say "give_up" but the engine overrides this if `attempt_count < max_attempts`. This is a safety guard -- the AI's give-up suggestion is only honored when the budget is truly exhausted or all channels have failed.
- **Distributed locking**: acquires a per-event Redis lock before processing to prevent concurrent escalation on the same event.
- **Quiet hours**: 9 PM to 9 AM IST. Events hitting quiet hours are rescheduled to 9 AM next day.

Fallback: if all AI models are unavailable, uses a simple channel rotation: whatsapp -> email -> sms -> whatsapp -> email.

#### `backend/app/services/messenger.py` -- Multi-Provider Message Sending

Handles the actual delivery with provider fallback chains:

**WhatsApp chain:**
1. Green API (sends AI-personalized freeform text)
2. Twilio WhatsApp (sends pre-approved content template -- required by Twilio trial)
3. Email fallback (if both WhatsApp providers fail)

**SMS chain:**
1. Twilio SMS (AI-personalized text)
2. Green API WhatsApp fallback
3. Twilio WhatsApp fallback
4. Email fallback

**Email chain:**
1. Resend (AI-personalized HTML email with branded template)

Each provider attempt is logged in a `degradation_path` array so the audit trail shows exactly which providers were tried and why each failed. Per-resource cooldowns (5 min per phone number/email) prevent message spam.

#### `backend/app/services/message_generator.py` -- AI Message Personalization

Uses the same OpenRouter AI client to generate context-aware recovery messages. The AI receives the failure category, amount, customer name, attempt number, and personalization hint, then produces channel-appropriate messages:
- WhatsApp: max 200 chars, conversational, 1-2 relevant emojis.
- SMS: max 140 chars, ultra-brief, action-focused.
- Email: subject line + greeting + body + CTA button text.

The `render_email_html` function produces a branded HTML email with header, body, CTA button, and footer. All user content is HTML-escaped. Payment URLs are validated to start with `http://` or `https://`.

#### `backend/app/services/recovery_tracker.py` -- Payment Reconciliation

Handles the feedback loop when a payment lands. This is architecturally important because it closes the recovery cycle.

**Reconciliation checks** (must all pass):
1. Payment entity status must be `"captured"` (not just authorized).
2. Currency must match the recovery event.
3. Amount must be within 1% tolerance of the event amount.
4. Payment ID must not already be attributed to another recovery (prevents double-counting).

**Matching strategy** (tries in order):
1. `notes.recovery_event_id` -- set by the payment link generator.
2. `payment_link.reference_id` -- the original order_id stored as reference.
3. `order_id` on the recovery event (skips TEST_ prefixed IDs).
4. `payment_id` on the recovery event.

**Organic vs. AI-driven recovery**: if `attempt_count == 0` and no successful outreach attempts exist, the recovery is marked `organic_recovery` (customer paid on their own) rather than `recovered` (my outreach worked). This prevents inflating AI recovery metrics.

#### `backend/app/services/payment_links.py` -- Payment Link Generation

Uses the **Razorpay Orders API** (not the Payment Links API) to create checkout orders. This is a deliberate architectural choice: the Payment Links API has a 30-link limit in test mode, while the Orders API has no such limit.

The flow:
1. Create a Razorpay order with amount, currency, and notes containing `recovery_event_id`.
2. Store customer PII (name, email, phone) in Redis with a random token (24-byte URL-safe, 24h TTL).
3. Return a checkout URL: `{API_BASE_URL}/pay/{order_id}?t={token}`.

Customer data never appears in the URL path or query parameters beyond the opaque token.

#### `backend/app/services/invoice_scanner.py` -- Invoice Polling

Polls the Razorpay Invoices API for overdue invoices. Paginates through all `issued` invoices, calculates `days_overdue` from the due date, filters out already-tracked invoices (batch query against `recovery_events.invoice_id`), and returns normalized event data for the recovery pipeline.

#### `backend/app/services/analytics.py` -- Analytics Computation

Computes aggregate metrics from all recovery events:
- Summary stats: total events, recovered/pending/exhausted/no_action counts, recovery rate, amounts.
- AI Lift: compares the system's recovery rate against a 15% industry baseline (cited from Razorpay blog). Calculates improvement points, lift multiplier, and additional revenue recovered.
- Breakdowns: by event type, by channel (with ranking), by failure category.

Results are cached in Redis for 120 seconds to avoid hammering Supabase on dashboard refreshes.

### 2.4 Celery Tasks

#### `backend/app/tasks/recovery.py`

Three Celery tasks:

1. **`process_recovery_event`** (max_retries=3, acks_late=True) -- The main pipeline. Classify -> dedup -> insert -> route -> generate link -> send -> log. Handles transient errors (connection, timeout) with exponential backoff (60s, 120s, 240s). Permanent failures are logged as a recovery_attempt with `outcome="failed"`.

2. **`handle_recovery_retry_failure`** (max_retries=2) -- When a customer opens my recovery link and their payment fails again, this logs it on the parent event instead of creating a duplicate. Uses Redis distributed lock with 60s TTL to prevent races. Detects user cancellations by scanning the error description.

3. **`_send_delayed`** (max_retries=2) -- Executes delayed sends (for events classified with 5_minutes, 30_minutes, etc. timing). Checks that the event is still pending and hasn't been handled by escalation before sending.

**Quiet hours**: 9 PM to 9 AM IST. Events arriving during quiet hours are rescheduled to 9 AM. This applies to both initial sends and escalation.

**Retry delay schedule** (per failure category):
| Category | Delay Between Attempts |
|---|---|
| upi_timeout, gateway_error | 1 hour |
| bank_downtime | 2 hours |
| high_intent_abandonment | 2 hours |
| card_expired | 6 hours |
| insufficient_funds | 8 hours |
| user_cancelled | 12 hours |
| recently_overdue | 24 hours |
| moderately_overdue, long_overdue | 48 hours |

#### `backend/app/tasks/escalation.py`

**`run_escalation_cycle`** -- Runs every 5 minutes via Celery Beat. Acquires a global Redis lock (`lock:escalation`, 240s TTL) to prevent concurrent cycles.

Flow:
1. Query `recovery_events` where `status = 'pending'` AND `next_action_at <= now()`.
2. Sort by `recovery_probability DESC, next_action_at ASC` (highest-value events first).
3. Limit to 50 events per cycle.
4. Filter out: opted-out events, expired windows, exhausted attempts, unrecoverable declines, zero-probability events.
5. For expired windows: if 0 attempts were made, extend the window by 24h (don't waste the event). Otherwise, mark exhausted.
6. Pass actionable events to `run_escalation()`.

#### `backend/app/tasks/invoice_scan.py`

**`scan_overdue_invoices`** -- Runs every 6 hours via Celery Beat. Calls `fetch_overdue_invoices()` and dispatches each new overdue invoice to `process_recovery_event.delay()`.

### 2.5 Utils

#### `backend/app/utils/dedup.py` -- Redis Dedup

Two-layer deduplication:

1. **Redis fast path**: `SET dedup:{event_type}:{identifier} 1 NX EX 3600`. Returns true if the key already exists (duplicate). TTL of 1 hour prevents reprocessing of retried webhooks.
2. **Identifier extraction**: for Razorpay `payment.failed` webhooks, uses the payment entity ID. For custom payloads, uses `payment_id`, `order_id`, `invoice_id`, or a SHA-256 hash of the sorted payload.

A third layer (durable DB dedup) is in `recovery.py` -- unique indexes on `payment_id`, `order_id`, `invoice_id` (excluding TEST_ prefixes) catch anything Redis misses.

#### `backend/app/utils/rate_limiter.py` -- Rate Limiting

Two rate limiting strategies:

1. **Sliding window** (`check_rate_limit`): Uses a Redis sorted set. Members are timestamps; the set is trimmed to the window on each check. Used for API endpoint protection:
   - Webhook endpoints: 100 req/min
   - Events API: 60 req/min
   - Analytics: 30 req/min
   - Simulator: 10 req/min
   - Live checkout: 5 req/min

2. **Per-resource cooldown** (`check_per_resource_cooldown`): Simple `SET NX EX` -- prevents sending more than one message per phone number or email address within 5 minutes. Prevents customer spam during escalation.

#### `backend/app/utils/normalizer.py` -- Webhook Normalization

Handles two payload formats:
1. **Raw Razorpay** (`event: "payment.failed"`): extracts fields from deeply nested `payload.payment.entity`, converts amount from paise to rupees.
2. **Custom format**: direct mapping to `RecoveryEventInput` model.

#### `backend/app/redis_client.py` -- Redis Connection

Thread-safe singleton using a connection pool with `decode_responses=True`. The pool is created lazily on first access with double-checked locking.

#### `backend/app/database.py` -- Supabase Client

Thread-safe singleton Supabase client, created lazily with double-checked locking. Uses `SUPABASE_SERVICE_KEY` (not the anon key) for full table access.

#### `backend/app/auth.py` -- Authentication

Simple shared-secret authentication:
- `require_auth`: FastAPI dependency that validates the `Authorization` header against `APP_PASSWORD`. Accepts both `Bearer <token>` and plain token formats. Uses `hmac.compare_digest` for timing-safe comparison.
- `verify_login`: validates a password for the login endpoint.

#### `backend/app/config.py` -- Configuration

All configuration via environment variables with `python-dotenv`. Key settings:
- Razorpay API keys and webhook secret.
- OpenRouter API key (routes to Claude/Gemini/GPT).
- Green API (WhatsApp), Twilio (WhatsApp + SMS), Resend (email) credentials.
- Supabase URL and keys (service key for backend, anon key for frontend Realtime).
- Redis URL.
- Hardcoded operational constants: 72-hour recovery window, max 5 attempts default, 300-second escalation interval, 21600-second (6h) invoice scan interval.

---

## 3. Async Pipeline Deep Dive

### 3.1 Webhook Ingestion

```
Razorpay fires webhook
    |
    v
FastAPI receives POST /webhook/recovery-router
    |
    +-- [body > 256KB?] --> 413 reject
    +-- [HMAC invalid?] --> 401 reject
    +-- [rate limit exceeded?] --> 429 reject
    +-- [Redis dedup hit?] --> 200 "duplicate"
    +-- [normalization fails?] --> 400 reject
    |
    v
Is this a retry failure on my recovery link?
    |
    +--[yes]--> handle_recovery_retry_failure.delay(parent_data)
    |               |
    |               +-- Acquires Redis lock on parent event
    |               +-- Increments attempt_number
    |               +-- Logs payment_link attempt with failure details
    |               +-- Detects user cancellations in error_description
    |               +-- Updates parent event timestamps
    |
    +--[no]--> process_recovery_event.delay(event_data)
                   |
                   v
              (Celery worker picks up -- see next section)
```

### 3.2 The Recovery Pipeline (Celery Task)

`process_recovery_event` is the central pipeline. It runs as a single atomic Celery task:

**Step 1: Classify**
```
event_data --> RecoveryEventInput model validation
    |
    v
classify_event(event)
    |
    +-- ai_call(CLASSIFICATION_PROMPT, event_json)
    |       |
    |       +-- Try Claude Haiku 4.5 (OpenRouter)
    |       +-- Try Gemini 3.7 Flash (OpenRouter)
    |       +-- Try GPT-4o-mini (OpenRouter)
    |       +-- All failed? Return None
    |
    +-- [AI returned result] --> validate, create ClassificationResult
    +-- [AI failed] --> _fallback_classify() using FALLBACK_RULES
```

**Step 2: Dedup + Insert**
```
compute_max_attempts(amount, probability, category)
    |
    v
_check_durable_dedup(payment_id, order_id, invoice_id)
    |
    +-- [duplicate found] --> return {status: "duplicate"}
    +-- [no duplicate] --> INSERT into recovery_events
```

**Step 3: Route**
```
route_action(classification)
    |
    +-- [no_action] --> update status to "no_action_needed", return
    +-- [send_delayed] --> schedule _send_delayed.apply_async(countdown=N), return
    +-- [send_now] --> continue to step 4
```

**Step 4: Quiet Hours Check**
```
_is_quiet_hours() -- 9 PM to 9 AM IST
    |
    +-- [quiet hours] --> reschedule to next 9 AM, return
    +-- [ok] --> continue
```

**Step 5: Generate Payment Link**
```
generate_payment_link(amount, customer, event_id, ...)
    |
    +-- POST to Razorpay Orders API
    +-- Store customer PII in Redis (token-based)
    +-- Return checkout URL: /pay/{order_id}?t={token}
    |
    +-- [failed] --> reschedule in 15 min, return
```

**Step 6: Send Message**
```
send_message(channel, customer, amount, link, ...)
    |
    +-- generate_personalized_messages() via AI
    |       (same 3-model fallback, falls back to templates)
    |
    +-- Provider chain based on channel
    |       WhatsApp: Green API -> Twilio WA -> Email
    |       SMS: Twilio SMS -> Green API WA -> Twilio WA -> Email
    |       Email: Resend
    |
    +-- Per-resource cooldown check (5 min per phone/email)
    +-- Returns: {success, message_id, channel_used, degraded_from, degradation_path}
```

**Step 7: Log + Schedule**
```
INSERT recovery_attempts (event_id, attempt_number, channel, outcome, metadata)
    |
    v
UPDATE recovery_events:
    +-- [send succeeded, max_attempts reached] --> status = "exhausted"
    +-- [send succeeded, more attempts] --> next_action_at = now + RETRY_DELAY
    +-- [send failed] --> next_action_at = now + 15 min (retry soon)
```

### 3.3 Escalation Engine (Beat Schedule)

Every 5 minutes, Celery Beat fires `run_escalation_cycle`:

```
Acquire global Redis lock (lock:escalation, 240s TTL)
    |
    v
Query: SELECT * FROM recovery_events
    WHERE status = 'pending'
    AND next_action_at <= NOW()
    ORDER BY recovery_probability DESC, next_action_at ASC
    LIMIT 50
    |
    v
For each event:
    +-- [opted_out?] --> skip
    +-- [window expired?]
    |       +-- [0 attempts made] --> extend window +24h
    |       +-- [attempts > 0] --> mark exhausted
    +-- [attempt_count >= max_attempts?] --> mark exhausted
    +-- [unrecoverable_decline or probability == 0?] --> skip
    |
    v
Acquire per-event Redis lock (lock:event:{id}, 300s TTL)
    |
    v
Re-read event from DB (status might have changed)
    |
    v
Fetch attempt history (last 10 attempts)
    |
    v
AI escalation decision:
    +-- Sends event context + attempt history + blocked/failed channels
    +-- AI decides: send (which channel, what tone) or give_up
    +-- Safety override: if AI says give_up but attempts < max_attempts,
    |   force send on next available channel
    |
    v
Same send flow as initial: generate link -> send message -> log attempt -> update state
    |
    v
Release per-event lock
    |
    v
Release global lock
```

### 3.4 Invoice Scanner (Beat Schedule)

Every 6 hours:

```
scan_overdue_invoices
    |
    v
Paginate through Razorpay Invoices API (status=issued, 100/page)
    |
    v
For each invoice:
    +-- Calculate days_overdue from due_date
    +-- [not overdue (< 1 day)?] --> skip
    +-- [already in recovery_events?] --> skip (batch lookup)
    +-- Normalize to event format
    |
    v
For each new overdue invoice:
    process_recovery_event.delay(invoice_data)
```

---

## 4. Database Schema

All tables live in Supabase PostgreSQL, defined across five migration files in `backend/migrations/`.

### 4.1 `recovery_events` Table

The primary table. One row per revenue leak event.

| Column | Type | Purpose |
|---|---|---|
| `id` | BIGSERIAL PK | Auto-incrementing event ID |
| **Event Data** | | |
| `event_type` | TEXT NOT NULL | `payment_failure`, `cart_abandonment`, `invoice_overdue` |
| `payment_id` | TEXT | Razorpay payment ID (unique index, excluding TEST_ prefix) |
| `order_id` | TEXT | Razorpay order ID (unique index, excluding TEST_ prefix) |
| `invoice_id` | TEXT | Razorpay invoice ID (unique index) |
| `amount` | DECIMAL | Event amount in major currency units |
| `currency` | TEXT | Default `INR` |
| `method` | TEXT | Payment method (upi, card, netbanking, etc.) |
| `error_code` | TEXT | Razorpay error code |
| `error_description` | TEXT | Human-readable error description |
| `customer_email` | TEXT | Customer email for outreach |
| `customer_phone` | TEXT | Customer phone for outreach |
| `customer_name` | TEXT | Customer display name |
| `cart_value` | DECIMAL | For cart_abandonment events |
| `items_in_cart` | INTEGER | For cart_abandonment events |
| `days_overdue` | INTEGER | For invoice_overdue events |
| **AI Classification** | | |
| `leak_type` | TEXT | AI-determined leak type |
| `failure_category` | TEXT | One of 12 categories |
| `recovery_probability` | FLOAT | 0.0 to 1.0 |
| `recommended_action` | TEXT | Detailed action description |
| `recommended_channel` | TEXT | whatsapp, email, sms, none |
| `recommended_timing` | TEXT | immediate through 4_hours |
| `reasoning` | TEXT | AI's reasoning for the classification |
| `alternative_action` | TEXT | Backup plan if primary fails |
| `skip_reason` | TEXT | Why no action was taken (if applicable) |
| **Status Tracking** | | |
| `status` | TEXT | `pending`, `paused`, `recovered`, `exhausted`, `no_action_needed`, `organic_recovery`, `cancelled` |
| `recovered_at` | TIMESTAMPTZ | When payment was captured |
| `recovered_amount` | DECIMAL | Actual captured amount |
| `recovered_payment_id` | TEXT | Payment ID that closed the recovery (unique index) |
| **Agent State** | | |
| `attempt_count` | INTEGER | Number of outreach attempts made |
| `last_attempt_at` | TIMESTAMPTZ | When the last attempt was made |
| `max_attempts` | INTEGER | Dynamic budget (0-5, computed from amount/probability) |
| `current_strategy` | TEXT | Current state label (initial, first_contact_sent, follow_up_sent, etc.) |
| `next_action_at` | TIMESTAMPTZ | When the escalation engine should next act |
| `opted_out` | BOOLEAN | Customer opted out of recovery |
| `recovery_window_ends` | TIMESTAMPTZ | 72-hour window from event creation |
| `escalation_level` | INTEGER | Current escalation level |
| **Metadata** | | |
| `source` | TEXT | `api`, `simulator`, `invoice_scanner` |
| `razorpay_raw` | BOOLEAN | Whether the event came from a raw Razorpay webhook |
| `fallback_classification` | BOOLEAN | Whether rule-based fallback was used |
| `created_at` | TIMESTAMPTZ | Row creation time |
| `updated_at` | TIMESTAMPTZ | Last modification time |

### 4.2 `recovery_attempts` Table

One row per outreach attempt or system event on a recovery event.

| Column | Type | Purpose |
|---|---|---|
| `id` | BIGSERIAL PK | Auto-incrementing attempt ID |
| `recovery_event_id` | BIGINT FK | References recovery_events(id) |
| `attempt_number` | INTEGER | Monotonically increasing per event |
| `channel_used` | TEXT | whatsapp, email, sms, payment_link, system |
| `action_taken` | TEXT | Description of what was done |
| `outcome` | TEXT | sent, failed, blocked |
| `message_id` | TEXT | Provider message ID for tracking |
| `notes` | TEXT | AI reasoning or error details |
| `idempotency_key` | TEXT | `{event_id}:{phase}:{attempt}` (unique index) |
| `metadata` | JSONB | Structured data: payment_link_id, payment_link_url, send_error, degraded_from, degradation_path, ai_personalized |
| `created_at` | TIMESTAMPTZ | Row creation time |

### 4.3 Indexes

Performance-critical indexes:

```sql
-- Fast escalation queries (the most frequent query in the system)
idx_recovery_events_pending_next ON (status, next_action_at) WHERE status = 'pending'

-- Webhook dedup lookups
idx_recovery_events_payment_id ON (payment_id)
idx_recovery_events_order_id ON (order_id) WHERE status = 'pending'
idx_recovery_events_invoice_id ON (invoice_id)

-- Dashboard queries
idx_recovery_events_status ON (status)
idx_recovery_events_created_at ON (created_at DESC)

-- Durable idempotency (unique, excluding simulator events)
idx_recovery_events_payment_id_unique ON (payment_id) WHERE payment_id NOT LIKE 'pay_TEST_%'
idx_recovery_events_order_id_unique ON (order_id) WHERE order_id NOT LIKE 'order_TEST_%'
idx_recovery_events_invoice_id_unique ON (invoice_id) WHERE invoice_id IS NOT NULL

-- Prevent double-attribution of recovered payments
idx_recovery_events_recovered_payment_unique ON (recovered_payment_id)

-- Attempt lookups
idx_recovery_attempts_event_id ON (recovery_event_id)
idx_recovery_attempts_created_at ON (created_at DESC)
idx_recovery_attempts_idempotency ON (idempotency_key) WHERE idempotency_key IS NOT NULL
```

### 4.4 Trigger: `trg_prevent_premature_exhaustion`

A database-level safety guard (migration 004). Fires `BEFORE UPDATE` on `recovery_events` whenever status is changing to `exhausted`. Blocks the transition if:
- `attempt_count < max_attempts`, AND
- `max_attempts > 0`, AND
- `skip_reason IS NULL`

When blocked, the trigger reverts status and current_strategy to their old values and raises a WARNING. This catches any external writer (manual queries, future integrations) that tries to prematurely exhaust an event.

### 4.5 Row Level Security

RLS is enabled on both tables (migration 005). Only the `service_role` can read/write -- the frontend uses the anon key for Realtime subscriptions only, which uses Supabase's built-in Realtime permissions.

### 4.6 Realtime

```sql
ALTER PUBLICATION supabase_realtime ADD TABLE recovery_events;
```

The frontend subscribes to changes on `recovery_events` via Supabase Realtime (the publication is configured in migration 001). This powers the live event feed -- new events and status changes appear on the dashboard without polling.

---

## 5. Frontend Architecture

### 5.1 Stack

- **React 19** with function components and hooks.
- **Vite 8** for build tooling and dev server.
- **Tailwind CSS 4** (via `@tailwindcss/vite` plugin).
- **Supabase JS client** (`@supabase/supabase-js`) for Realtime subscriptions.
- No router library -- page state is managed via `useState('overview')` in `App.jsx`.

### 5.2 Application Structure

**`frontend/src/main.jsx`** -- Entry point. Wraps the app in `<StrictMode>` and `<LoadingProvider>` (provides a global loading bar context).

**`frontend/src/App.jsx`** -- Root component with:
- **Authentication**: checks `sessionStorage` for `rr_auth_token`. Shows `LoginPage` if not authenticated. Token is the `APP_PASSWORD` itself.
- **Data loading**: polls `fetchAnalytics` + `fetchEvents` every 30 seconds.
- **Page routing**: switches between five pages based on `page` state.
- **Error boundary**: catches React render errors and shows a reload button.

### 5.3 Pages

| Page | Component | Purpose |
|---|---|---|
| Overview | `OverviewPage.jsx` | Stat tiles + live event feed + quick actions |
| Events | `EventsPage.jsx` | Paginated event table with status filters and event trace drill-down |
| Analytics | `AnalyticsPage.jsx` | Recovery metrics, AI lift calculation, channel performance |
| Simulator | `SimulatorPage.jsx` | Send test events (10 scenarios), live checkout testing |
| Audit Logs | `AuditLogsPage.jsx` | Recovery attempt history with full degradation paths |

### 5.4 Key Components

- **`Layout.jsx`** -- Top navigation bar with Razorpay logo SVG, date range picker, sidebar navigation (responsive with mobile hamburger menu).
- **`StatTiles.jsx`** -- Summary cards (total events, recovery rate, recovered amount, pending).
- **`LiveFeed.jsx`** -- Real-time event list with status colors, amount formatting, time-ago labels.
- **`RecoveryByType.jsx`** -- Breakdown by event type (payment/cart/invoice).
- **`ChannelRanking.jsx`** -- Channel performance comparison.
- **`AILift.jsx`** -- AI vs. baseline recovery rate visualization.
- **`HealthBadge.jsx`** -- Service health indicator (Redis/Celery/Supabase status).
- **`DateRangePicker.jsx`** -- Date range filter for all data views.
- **`LoadingBar.jsx`** -- Global loading indicator (context provider pattern).
- **`SimulatorPanel.jsx`** -- Test scenario selector with customer info inputs.

### 5.5 API Layer

**`frontend/src/lib/api.js`** -- Centralized API client:
- Base URL from `VITE_API_BASE` env var (empty in dev, Vite proxies `/api` to backend).
- Token stored in `sessionStorage` (cleared on tab close).
- Automatic 401 handling: clears token and triggers re-login.
- Loading hooks: global `start`/`done` callbacks drive the loading bar.

**`frontend/src/lib/supabase.js`** -- Supabase client for Realtime:
- Created with `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- Only used for Realtime subscriptions, not for data queries (those go through the API).

### 5.6 Design System

The frontend uses Razorpay's design language (dark navy navbar, blue primary accent `#528FF0`, card-based layout) via CSS custom properties in `index.css`. The approach is a handcrafted CSS clone, not Razorpay's official design system library.

---

## 6. Scalability

### 6.1 Current Architecture Capacity

The system is designed for a single-merchant deployment handling moderate volume. Current configuration:

- **Celery workers**: 2 prefork processes (Railway Procfile).
- **Escalation cycle**: processes up to 50 events per 5-minute cycle.
- **Redis**: single instance for broker + cache + locks.
- **Supabase**: managed Postgres with connection pooling.

### 6.2 Horizontal Scaling with Celery

The primary scale lever is Celery workers. Adding more workers is a matter of increasing `--concurrency` or running additional worker containers.

Key properties that enable this:
- **Stateless tasks**: all state is in Supabase/Redis. Workers share nothing.
- **`acks_late=True`**: tasks are acknowledged after completion, not on pickup. If a worker dies, the task returns to the queue.
- **`task_reject_on_worker_lost=True`**: crashed worker tasks are re-queued.
- **`worker_prefetch_multiplier=1`**: each worker fetches one task at a time, ensuring even distribution.

### 6.3 Redis as Broker + Cache + Lock Store

Redis serves four roles:
1. **Celery broker**: task queue for the recovery pipeline.
2. **Dedup cache**: 1-hour TTL keys prevent duplicate webhook processing.
3. **Rate limiter**: sliding window counters and per-resource cooldowns.
4. **Distributed locks**: per-event locks prevent concurrent escalation, global lock prevents concurrent escalation cycles.

At higher scale, these concerns should be separated:
- Dedicated Redis instance for the Celery broker (tuned for queue throughput).
- Dedicated Redis instance for cache/locks (tuned for low latency).

### 6.4 Distributed Locking Strategy

Three lock levels:

| Lock | Key | TTL | Purpose |
|---|---|---|---|
| Global escalation | `lock:escalation` | 240s | Prevents concurrent escalation cycles |
| Per-event | `lock:event:{id}` | 300s | Prevents concurrent processing of the same event |
| Delayed send | `lock:event:{id}` | 300s | Prevents delayed task racing with escalation |

All locks use `SET NX EX` (atomic set-if-not-exists with expiry). No lock renewal -- if a process dies, the lock expires and another process can take over.

### 6.5 Rate Limiting

Two-tier approach:
- **API-level**: sliding window rate limiter on Redis sorted sets. Protects the API from webhook floods.
- **Per-resource cooldown**: prevents sending more than one message to the same phone/email within 5 minutes. Prevents customer annoyance during concurrent escalation.

### 6.6 Scaling Path

**10x scale** (~500 events/day):
- Increase Celery concurrency to 4-8 workers.
- Increase escalation batch size from 50 to 200.
- Add Redis connection pooling with higher max connections.
- No schema changes needed.

**100x scale** (~5,000 events/day):
- Separate Redis instances (broker vs. cache).
- Add Celery task routing with dedicated queues: `recovery`, `escalation`, `invoice_scan`.
- Add database read replicas for analytics queries.
- Partition `recovery_events` by `created_at` (monthly).
- Add a dedicated analytics table (materialized view or pre-computed).
- Consider replacing the 30-second polling in the frontend with server-sent events or WebSocket.

**1000x scale** (~50,000 events/day):
- Replace Supabase with self-managed Postgres cluster.
- Replace Redis with Redis Cluster or Valkey.
- Add a proper message queue (RabbitMQ or Amazon SQS) instead of Redis as broker.
- Implement event sourcing -- the current model updates rows in place, which creates lock contention at high concurrency.
- Add an API gateway (rate limiting, request routing).
- Multi-tenant support: add `merchant_id` to all tables, partition by merchant.

---

## 7. Deployment Architecture

### 7.1 Backend (Railway)

The backend deploys to Railway using a Procfile with three process types:

```
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: celery -A app.celery_app worker --loglevel=info --pool=prefork --concurrency=2
beat: celery -A app.celery_app beat --loglevel=info
```

Railway runs each Procfile entry as a separate container. The `web` process handles HTTP traffic, `worker` processes Celery tasks, and `beat` runs the periodic scheduler.

Nixpacks auto-detects the Python project and builds from `requirements.txt`.

### 7.2 Frontend (Vercel)

The React frontend deploys to Vercel with standard Vite build configuration. Environment variables:
- `VITE_API_BASE`: Backend URL (e.g., `https://api.albertabishek.com`).
- `VITE_SUPABASE_URL`: Supabase project URL.
- `VITE_SUPABASE_ANON_KEY`: Supabase public anon key (safe to expose -- RLS restricts access).

### 7.3 CORS Configuration

The FastAPI app allows requests from:
- The configured `FRONTEND_URL`.
- `localhost:5173` and `localhost:3000` (local dev).
- `albertabishek.com` subdomains (production).
- Any `recovery-router*.vercel.app` origin (Vercel preview deploys, matched via regex).

Methods: GET, POST, PATCH, DELETE, OPTIONS. Credentials allowed.

### 7.4 Environment Variables

All secrets are injected via environment variables on Railway/Vercel. The backend `config.py` uses `python-dotenv` for local development (`.env` file). Key variable groups:

| Group | Variables | Service |
|---|---|---|
| Razorpay | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Payment orders + webhook verification |
| AI | `OPENROUTER_API_KEY` | Classification + message generation |
| WhatsApp | `GREEN_API_INSTANCE_ID`, `GREEN_API_TOKEN`, `GREEN_API_URL` | Green API provider |
| WhatsApp + SMS | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | Twilio provider |
| Email | `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Resend email provider |
| Database | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY` | Supabase Postgres |
| Cache/Broker | `REDIS_URL` | Redis |
| App | `APP_PASSWORD`, `FRONTEND_URL`, `API_BASE_URL`, `APP_ENV` | Application config |

### 7.5 Deployment Diagram

```
                    Internet
                       |
            +----------+----------+
            |                     |
            v                     v
    +-----------------+   +-----------------+
    |    Vercel CDN   |   |   Razorpay      |
    | (React Frontend)|   |   Webhooks      |
    |                 |   |                 |
    | razorpay.       |   | payment.failed  |
    | albertabishek.   |   | payment.captured|
    | com             |   | payment_link.   |
    +---------+-------+   |   paid          |
              |           +--------+--------+
              |                    |
              |    REST API        |    Webhooks
              |    (fetch)         |    (POST)
              |                    |
              +----------+---------+
                         |
                         v
              +---------------------+
              |  Railway Platform   |
              |                     |
              |  +---------------+  |
              |  | web container |  |
              |  | (Uvicorn)     |  |
              |  +-------+-------+  |
              |          |          |
              |  +-------+-------+  |
              |  | Redis (addon) |  |
              |  +-------+-------+  |
              |          |          |
              |  +-------+-------+  |
              |  | worker         |  |
              |  | (Celery x2)   |  |
              |  +-------+-------+  |
              |          |          |
              |  +-------+-------+  |
              |  | beat           |  |
              |  | (Celery Beat)  |  |
              |  +---------------+  |
              +----------+----------+
                         |
        +----------------+--+------------------+
        |                   |                  |
        v                   v                  v
  +-----------+    +--------------+    +--------------+
  | Supabase  |    |  OpenRouter  |    |  Messaging   |
  | Postgres  |    |  AI API      |    |  Providers   |
  |           |    |              |    |              |
  | recovery_ |    | Claude Haiku |    | Green API WA |
  | events    |    | Gemini Flash |    | Twilio WA    |
  | recovery_ |    | GPT-4o-mini  |    | Twilio SMS   |
  | attempts  |    +--------------+    | Resend Email |
  +-----------+                        +--------------+
```

---

## 8. Key Architectural Decisions

### Why Celery instead of async FastAPI tasks?

The recovery pipeline involves external API calls (Razorpay, OpenRouter, messaging providers) that can take 5-30 seconds. Running these in the FastAPI request handler would block the webhook response and risk Razorpay's webhook timeout. Celery gives me:
- Immediate webhook acknowledgment (HTTP 202 within milliseconds).
- Automatic retries with exponential backoff for transient failures.
- Delayed task execution (for events classified with non-immediate timing).
- Worker isolation -- a crashed AI call doesn't affect the API.

### Why OpenRouter instead of direct provider APIs?

A single API endpoint that routes to multiple models means the AI client only needs one authentication flow, one request format, and one error handling path. The 3-model fallback chain (Claude -> Gemini -> GPT) provides resilience against individual model outages or rate limits. The rule-based fallback ensures the system operates (with reduced intelligence) even when all AI is unavailable.

### Why Razorpay Orders API instead of Payment Links API?

The Payment Links API has a 30-link limit in test mode. The Orders API has no such limit. By creating orders and hosting my own checkout page at `/pay/{order_id}`, I get unlimited test-mode payment links.

### Why two dedup layers?

Redis dedup is fast (sub-millisecond) but volatile -- it's lost on Redis restart. The durable DB-level dedup (unique partial indexes) catches anything Redis missed. The combination gives both speed and correctness.

### Why token-based checkout URLs instead of embedding customer data?

Customer PII (name, email, phone) is stored in Redis with a random token, not in the URL. This means payment links can be shared without leaking customer information. The token has a 24-hour TTL, after which the checkout page still works but without pre-filled customer details.

### Why organic vs. recovered distinction?

If a customer pays on their own (before any outreach attempt was delivered), marking it as "recovered" would inflate the AI's effectiveness metrics. The `organic_recovery` status separates genuine AI-driven recoveries from coincidental payments, giving honest metrics in the analytics dashboard.

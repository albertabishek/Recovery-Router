# Recovery Router - Complete Feature Inventory

Built by Albert Abishek I for the Razorpay AI Buildathon 2026, Track 3.

This document covers every feature in the codebase, verified against the actual source files. Backend lives in `backend/app/`, frontend in `frontend/src/`.

---

## 1. Core Pipeline

The pipeline handles three types of revenue leaks: payment failures, cart abandonment, and overdue invoices. Every event goes through the same sequence - classify, route, generate payment link, send message, track outcome.

### 1.1 Revenue Leak Types

Defined in the `RecoveryEventInput` model (`backend/app/models.py`, line 9):

- **payment_failure** - A customer's payment attempt failed (UPI timeout, card expired, bank downtime, etc.)
- **cart_abandonment** - A customer added items to cart but left without paying
- **invoice_overdue** - A merchant's invoice hasn't been paid past its due date

Each type carries different fields. Payment failures have `error_code`, `error_description`, `method`. Cart abandonments have `cart_value`, `items_in_cart`. Invoice overdues have `days_overdue`.

### 1.2 AI Classification (12 Categories)

File: `backend/app/services/classifier.py`

The classifier uses OpenRouter's multi-model AI to analyze each event and assign a failure category. The 12 categories (lines 80-86):

1. **upi_timeout** - UPI payment timed out, likely network congestion. High recovery chance.
2. **bank_downtime** - Bank server temporarily unavailable. Wait and retry.
3. **card_expired** - Card has expired, customer needs to update details.
4. **insufficient_funds** - Not enough balance. Give time to transfer money.
5. **gateway_error** - Payment gateway technical error. Immediate retry likely works.
6. **user_cancelled** - Customer actively chose to cancel. Wait before re-engaging.
7. **unrecoverable_decline** - Fraud, stolen card, permanently blocked. No recovery action.
8. **high_intent_abandonment** - High-value cart with multiple items. Worth pursuing.
9. **browse_only_abandonment** - Low-value browsing session. Not worth the cost.
10. **recently_overdue** - Invoice 1-7 days late. Friendly reminder usually works.
11. **moderately_overdue** - Invoice 2-4 weeks late. Formal approach needed.
12. **long_overdue** - Invoice 30+ days late. Escalation notice required.

The AI receives the full event context (error description, amount, payment method, customer name, etc.) and returns a JSON object with the category, recovery probability (0.0-1.0), recommended channel, recommended timing, reasoning, alternative action, and a personalization hint. The system prompt (lines 16-70) guides the AI to think about _why_ the payment failed, consider amount thresholds for channel selection, detect user-initiated cancellations, and estimate recovery probability honestly.

If all AI models fail, rule-based fallback kicks in (`_fallback_classify`, line 244). The fallback uses keyword matching against the error code and description, with a `FALLBACK_RULES` dictionary (lines 103-118) mapping error keywords to (category, probability, channel, timing) tuples. Each category also has a `FALLBACK_ACTIONS` dictionary (lines 180-241) providing pre-written action descriptions and reasoning.

### 1.3 Three-Model AI Fallback Chain

File: `backend/app/services/ai_client.py`

The AI client uses OpenRouter with three models in sequence (lines 18-37):

1. **Claude Haiku 4.5** (`anthropic/claude-haiku-4.5`) - 12s timeout, 1 retry
2. **Gemini 3.7 Flash** (`google/gemini-3.7-flash`) - 10s timeout, 1 retry
3. **GPT-4o-mini** (`openai/gpt-4o-mini`) - 12s timeout, 1 retry

Each model gets up to 2 attempts (1 + 1 retry). If a model returns HTTP 429 (rate limited), it moves to the next model immediately. If all six attempts across three models fail, `ai_call` returns `None` and the caller falls back to rules.

The client validates AI responses against a schema (`_validate_fields`, line 168) - if the AI returns a channel not in the allowed list, it gets replaced with the default. Float fields are clamped to min/max ranges. The JSON parser (`_parse_json`, line 153) strips markdown code fences if the AI wraps its response in them.

A shared `httpx.Client` (thread-safe via lock) is reused across calls for connection pooling.

### 1.4 Dynamic Attempt Budgets

File: `backend/app/services/router.py`, function `compute_max_attempts` (line 13)

Recovery Router dynamically calculates how many recovery messages each event deserves based on three factors:

- **Unrecoverable decline or browse-only abandonment**: 0 attempts (no action taken)
- **User cancelled**: 2 attempts max (they cancelled for a reason)
- **Recovery probability <= 0.1**: 1 attempt only
- **High probability (>=0.7) + high amount (>=5000)**: 5 attempts
- **Medium probability (>=0.5) + medium amount (>=2000)**: 4 attempts
- **Low-medium probability (>=0.3) or amount >= 1000**: 3 attempts
- **Everything else**: 2 attempts

This means a high-value UPI timeout might get 5 recovery attempts across different channels, while a low-value browse-only cart gets zero.

### 1.5 Multi-Channel Messaging

File: `backend/app/services/messenger.py`

Three channels with multi-provider fallback chains:

**WhatsApp chain** (lines 72-101):
1. Green API (personalized text message) - primary
2. Twilio WhatsApp (content template) - fallback if Green API fails
3. Email via Resend - final fallback if no phone or both WhatsApp providers fail

**SMS chain** (lines 104-138):
1. Twilio SMS - primary
2. Green API WhatsApp - first fallback
3. Twilio WhatsApp - second fallback
4. Email via Resend - final fallback

**Email chain** (lines 141-156):
1. Resend - the only provider (with AI-personalized HTML content)

Every channel checks per-resource cooldowns before sending (5-minute cooldown per phone number or email address). If a cooldown is active, Recovery Router degrades to the next channel in the chain. The full degradation path is recorded in attempt metadata so you can trace exactly which providers were tried and why.

### 1.6 AI-Personalized Messages

File: `backend/app/services/message_generator.py`

Every outreach message is generated by AI, not from static templates. The AI receives the channel, failure category, amount, customer's first name, personalization hint from the classifier, and the attempt number, then writes channel-appropriate text:

- **WhatsApp**: max 200 chars, conversational, 1-2 emojis, payment link woven in naturally
- **SMS**: max 140 chars, ultra-brief, amount + reason + link
- **Email**: subject (max 60 chars), greeting, body (2-3 short paragraphs), and CTA button text

The tone escalates with attempt number (lines 44-48):
- Attempt 0: "Hey, looks like something went wrong"
- Attempt 1: "Just following up"
- Attempt 2: "Your payment is still pending"
- Attempt 3+: "Last reminder before we close this"

The email is rendered into a styled HTML template (`render_email_html`, line 138) with a header bar, greeting, body, CTA button, and footer. URLs are sanitized to prevent injection.

If AI is unavailable, template fallback messages are used (`_fallback_messages`, line 111).

### 1.7 Escalation Engine

File: `backend/app/tasks/escalation.py` (Celery Beat task) + `backend/app/services/escalation.py` (engine)

**Scheduling**: The escalation task `run_escalation_cycle` runs every 5 minutes via Celery Beat (`backend/app/celery_app.py`, line 22). It fetches up to 50 pending events whose `next_action_at` has passed, ordered by recovery probability (highest first), then by next_action_at (oldest first).

**Filtering** (lines 43-61 in `tasks/escalation.py`): Before escalation, events are filtered out if they:
- Have opted out
- Have an expired recovery window (gets marked exhausted or extended)
- Have exhausted their attempt budget
- Are unrecoverable declines
- Have zero recovery probability

**AI-driven decisions** (`services/escalation.py`, `_get_escalation_decision`, line 256): The escalation engine sends the event context plus full attempt history to AI. The AI decides:
- Whether to **send** or **give up**
- Which **channel** to use (considering what channels already failed or are on cooldown)
- What **tone** to use (friendly, firm, urgent, or final)

**Three-layer give-up prevention** (see Section 5.1 below): The AI's give_up decision is overridden if the attempt budget hasn't been spent.

**Retry delays** vary by failure category (`RETRY_DELAY_HOURS`, line 430):
- UPI timeout / gateway error: 1 hour between attempts
- Bank downtime: 2 hours
- Card expired: 6 hours
- Insufficient funds: 8 hours
- User cancelled: 12 hours
- Recently overdue invoice: 24 hours
- Moderately/long overdue: 48 hours
- High-intent cart: 2 hours

**Channel rotation**: If AI is unavailable, the engine falls back to a fixed rotation: whatsapp -> email -> sms -> whatsapp -> email (line 354). The `_pick_next_channel` function (line 363) avoids channels that are blocked (on cooldown) or failed (delivery error), preferring a different channel from the last one used.

### 1.8 Recovery Reconciliation

File: `backend/app/services/recovery_tracker.py`

When a payment is captured (via `payment.captured` or `payment_link.paid` webhook), Recovery Router matches it back to the recovery event that triggered it. Four matching strategies, tried in order (lines 89-108):

1. **notes.recovery_event_id** - Set when the payment link was generated. Most reliable.
2. **payment_link reference_id** - The original order_id stored as the payment link's reference_id.
3. **order_id** - Direct match on the recovery event's order_id (skips fake TEST_ IDs).
4. **payment_id** - Match on the recovery event's payment_id (skips fake TEST_ IDs).

Before attributing, three reconciliation checks must pass (lines 46-128):
- Payment entity status must be "captured" (not authorized, failed, etc.)
- Currency must match (e.g., can't attribute a USD payment to an INR recovery event)
- Captured amount must be within 1% tolerance of the event amount
- Payment ID must not already be attributed to another recovery (double-attribution prevention)

### 1.9 Ghost Recovery Prevention

File: `backend/app/services/recovery_tracker.py`, lines 146-173

When a payment is captured and matched to a recovery event, Recovery Router checks whether the recovery _actually_ caused the payment:

- If `attempt_count == 0` AND no successful outreach attempt exists in the database, the payment is marked as **organic_recovery** - the customer paid on their own without any recovery message reaching them.
- If there was at least one successfully sent recovery message, the payment is attributed as **recovered** - the outreach drove the payment.

This prevents inflating recovery metrics with payments that would have happened anyway. The two statuses are tracked separately in analytics.

### 1.10 Payment Link Generation

File: `backend/app/services/payment_links.py`

Instead of using Razorpay's Payment Links API (which has a 30-link limit in test mode), I use the **Orders API** to create orders, then build a hosted checkout page URL.

The flow (lines 42-105):
1. Create a Razorpay order via `POST /v1/orders` with the amount, currency, and notes containing the recovery_event_id and failure_category
2. Store customer PII (name, email, phone) in Redis with a random token (24-byte URL-safe, 24-hour TTL) - the PII never appears in the URL
3. Return `{API_BASE_URL}/pay/{order_id}?t={token}` as the checkout URL

The checkout page (`backend/app/routers/checkout.py`) is a self-contained HTML page that loads Razorpay's Standard Checkout SDK, pre-fills customer details from the Redis token, and auto-opens the checkout modal 500ms after page load.

---

## 2. Dashboard Pages

The frontend is a React single-page app (`frontend/src/App.jsx`) with five pages, a sidebar navigation, and a top navigation bar. Data refreshes every 30 seconds (`App.jsx`, line 133).

### 2.1 Overview Page

File: `frontend/src/components/OverviewPage.jsx`

The home dashboard shows:

- **Hero stat card**: Total revenue recovered (amount + count of recovered payments)
- **Three summary cards**: At Risk (total amount at risk + event count), Pending (pending amount + count in pipeline), Stopped (exhausted count + skipped count). Each card is clickable and navigates to the Events page.
- **Recovery vs Industry Baseline**: Side-by-side comparison of Recovery Router's recovery rate against a 15% industry baseline, with improvement in percentage points and additional revenue recovered shown.
- **Channel Performance**: Ranked list of channels (WhatsApp, Email, SMS) by recovery rate, with progress bars.
- **Recovery by Type**: Three cards for payment failures, cart abandonment, and invoice overdue - each showing event count, total amount, recovered count, and recovery rate.
- **Recent Events table**: Last 8 events with type badge, amount, failure category, channel, status badge, and relative time. Clicking a row navigates to the Events page with that event selected.

### 2.2 Recovery Events Page

File: `frontend/src/components/EventsPage.jsx`

A full event management interface with:

**Status tabs** (line 9): All Events, In Progress, On Hold, Paid, Gave Up, Cancelled, Skipped - each showing a count badge. Switching tabs resets to page 1.

**Event table**: Columns for ID, Type, Amount, Category, Channel, Messages (sent/limit), Status, and Next/Created time. Pending events show "in Xh Ym" until next attempt; others show relative time. Paginated with 25 events per page, full pagination controls (First, Prev, numbered pages, Next, Last).

**Event detail panel** (420px slide-in, line 293): Opens when you click any event row. Shows:
- Amount with currency
- Next attempt countdown (for pending events)
- Status banners (paused, exhausted, cancelled) with explanations
- **Recovery Pipeline visualization**: 4-step vertical pipeline (Classified -> Routed -> Message Sent -> Result) with green checkmarks for completed steps
- **Attempt History**: Every recovery attempt with attempt number, channel, outcome badge (sent/cooldown/failed), action description, degradation info, payment link, and timestamp. Customer payment attempts are highlighted separately with a blue "Customer" badge.
- **Event Details section**: Type, method, error code/description, payment ID, order ID
- **Customer section**: Name, email, phone
- **AI Classification section**: Category, recovery chance, channel, messages sent/limit, recommended action, reasoning (in a highlighted box), backup plan, skip reason
- **Timeline section**: Created, last message, next message, stop trying after, paid at, source, follow-up round, current approach

**Pause/Resume/Cancel controls** (lines 307-351): Buttons appear in the detail panel header based on current status:
- Pending events show "Pause" and "Cancel"
- Paused events show "Resume" and "Cancel"
- Exhausted events show "Cancel"

Cancel requires a browser confirmation dialog.

**Auto-refresh**: Events and counts refresh every 30 seconds (line 80).

### 2.3 Analytics (Reports) Page

File: `frontend/src/components/AnalyticsPage.jsx`

Shows:

**KPI cards row** (5 cards): Total Events, Recovery Rate (%), Avg Attempts to Recover, Avg Recovery Time (hours), Assisted Recovery (multiplier).

**Recovery by Event Type table**: Type, event count, total amount, recovered count, and recovery rate.

**Channel Performance chart**: Ranked channels with progress bars showing recovery rate, plus recovered/total counts and amounts.

**Failure Category Breakdown grid**: A card for each of the 12 failure categories showing event count, recovery rate, and a progress bar. Categories with zero events are not shown.

### 2.4 Simulator Page

File: `frontend/src/components/SimulatorPage.jsx`

**10 built-in scenarios** organized in three groups (lines 7-18):

Payment Failure group:
1. **UPI Timeout** - Retryable, high recovery odds (amount range 499-4,999)
2. **Card Expired** - Needs new card details (1,999-8,999)
3. **Insufficient Funds** - Delayed retry works best (2,499-12,999)
4. **Bank Downtime** - Retry after outage clears (999-4,999)
5. **Gateway Error** - Immediate retry likely to succeed (799-3,999)
6. **Fraud Decline** - Unrecoverable, system skips action (9,999-24,999)

Cart Abandonment group:
7. **High-Value Cart** - Worth chasing, email + link (2,999-14,999)
8. **Low-Value Cart** - Below action threshold, no spend (99-199)

Invoice Overdue group:
9. **Recent Invoice** - Friendly nudge, high recovery (5,000-50,000)
10. **Old Invoice** - Escalated tone, lower odds (15,000-75,000)

Each scenario is a clickable card showing the label, description, and randomized amount range. Clicking fires a real event through the live pipeline.

**Custom recipient fields** (lines 68-159): An expandable "Customer Details" section lets you override the default test recipient with custom name, email, and phone. Shows a "Custom" badge when any field is filled.

**Simulation Log**: Shows the last 20 simulation results with scenario name, status (green dot for queued, red for error), message, and timestamp.

**Pipeline Results table**: Shows the last 20 events from the database with ID, type, amount, AI category, routed-to channel, probability, status, and time. Has a pulsing green dot labeled "Live from Supabase".

### 2.5 Live Payment Feature

File: `frontend/src/components/SimulatorPage.jsx`, `LivePaymentSection` component (line 280)

A special section within the Simulator page bordered in Razorpay blue:

- **Amount input**: Defaults to 499, range 1-50,000
- **Customer fields**: Name, email (required), phone
- **"Open Razorpay Checkout" button**: Creates a real Razorpay test-mode order via `POST /api/live-checkout`, then opens the Razorpay Standard Checkout modal in the browser
- **Test card helper text**: Tells you to use `4111 1111 1111 1111` with any future expiry

When the checkout succeeds, the Razorpay webhook fires `payment.captured` which flows through the recovery tracker and marks the event as recovered. When it fails, the `payment.failed` webhook triggers the recovery pipeline - creating a new recovery event, classifying it, and sending recovery messages.

**Backend endpoint** (`backend/app/routers/events.py`, line 334, `create_live_checkout`):
- Rate limited to 5 requests per minute
- Amount validation: 1 to 500,000
- Creates Razorpay order via `POST https://api.razorpay.com/v1/orders`
- Returns order_id, amount, currency, and razorpay_key for the frontend checkout SDK

### 2.6 Audit Logs Page

File: `frontend/src/components/AuditLogsPage.jsx`

Shows every recovery attempt with full provider chain detail:

**Table columns**: ID, Event (clickable link), Attempt number, Channel (with degradation info), Outcome (badge), Provider Chain (e.g., "green_api -> twilio_whatsapp -> resend"), Error message, Message ID, Time.

**Filter by Event ID**: Text input that strips non-numeric characters.

**Auto-refresh**: Every 15 seconds (line 254), shown with a pulsing green dot labeled "Auto-refresh 15s".

**Pagination**: 30 logs per page with full pagination controls.

**Trace Panel** (line 63): Clicking any row opens a 520px fixed slide-in panel showing the full event trace. The panel shows:
- Event details (type, amount, category, channel, status, probability, customer info)
- AI reasoning
- Pipeline steps - each attempt with outcome badge, channel, time, message ID, degradation info, errors, payment link URL, and full provider chain (each provider shown as a step with colored left border and dot: green for sent, red for failed, yellow for skipped)
- Timeline (created, last attempt, next action, window closes, recovered)

---

## 3. Webhook Endpoints

File: `backend/app/routers/webhooks.py`

### 3.1 Recovery Router Webhook

`POST /webhook/recovery-router` - Entry point for all recovery events. Public (no auth), but requires a valid Razorpay webhook signature.

Flow:
1. Rate limit check (100 requests/60 seconds)
2. Body size check (max 256KB)
3. HMAC-SHA256 signature verification against `RAZORPAY_WEBHOOK_SECRET`
4. Redis-based deduplication (1-hour TTL)
5. Payload normalization (handles both raw Razorpay `payment.failed` format and custom format)
6. If the failed payment came from a recovery link Recovery Router sent (detected via notes or order_id matching in `recovery_attempts`), log it as a retry failure on the parent event instead of creating a duplicate
7. Otherwise, dispatch `process_recovery_event` Celery task

### 3.2 Recovery Tracker Webhook

`POST /webhook/recovery-tracker` - Feedback loop for payment success. Same signature verification.

Handles `payment.captured` and `payment_link.paid` events. Calls `process_payment_captured` to match the payment to a recovery event and mark it as recovered or organic_recovery.

### 3.3 Recovery Retry Failure Tracking

When a customer clicks a recovery link but their payment _fails again_ (e.g., wrong UPI PIN on retry), Recovery Router detects this via the `_find_parent_recovery_event` function (line 116). It looks up the order_id in `recovery_attempts` metadata. If found, it dispatches `handle_recovery_retry_failure` (in `backend/app/tasks/recovery.py`, line 315) which logs the failure as a `payment_link` channel attempt on the parent event, rather than creating a new recovery event.

The task also detects user-initiated cancellations by checking for keywords like "cancelled", "canceled", "user aborted" in the error description.

---

## 4. Event Management

### 4.1 Pause/Resume/Cancel

File: `backend/app/routers/events.py`, `control_event` endpoint (line 384)

`PATCH /api/events/{event_id}/control` - Authenticated.

- **Pause** (only pending -> paused): Clears `next_action_at`, sets strategy to "merchant_paused". The escalation engine won't pick it up.
- **Resume** (only paused -> pending): Sets `next_action_at` to now (so escalation picks it up immediately), sets strategy to "resumed".
- **Cancel** (pending/paused/exhausted -> cancelled): Sets status to "cancelled", clears next_action_at and recovery_window_ends, sets skip_reason to "Cancelled by merchant". Cannot cancel events already in terminal states (recovered, organic_recovery, cancelled).

All three use optimistic concurrency - the update includes a status check in the WHERE clause, and if the status changed between the read and the write, it returns 409 Conflict.

### 4.2 Event Detail Panel

See Section 2.2 above. The 420px slide-in panel shows the complete lifecycle of an event including AI decisions, provider attempts, state transitions, and timing.

### 4.3 Event Trace API

`GET /api/events/{event_id}/trace` (line 206) - Returns the event, all its attempts, and a structured timeline.

The timeline (`_build_trace_timeline`, line 231) builds an ordered list of steps:
- `event_received` - When the event was created
- `classified` - AI classification results
- `payment_link_created` - For each attempt that generated a payment link
- `outreach_attempt` - Each message send attempt with channel, outcome, reasoning, degradation path
- `recovered` / `exhausted` / `cancelled` / `next_action_scheduled` - Terminal or current state

---

## 5. Safety Features

### 5.1 Three-Layer Give-Up Prevention

Recovery Router has three layers preventing premature abandonment of recovery events:

**Layer 1 - AI override in escalation** (`backend/app/services/escalation.py`, line 310): If the AI says "give_up" but `attempt_count < max_attempts`, and either (a) not all outreach attempts truly failed, or (b) it's the first escalation, Recovery Router overrides to "send" and picks a different channel.

**Layer 2 - Direct budget check in run_escalation** (`backend/app/services/escalation.py`, line 139): Even after the AI decision, if give_up is returned and `attempt_count < max_attempts`, it forces a send with a safety override message.

**Layer 3 - Database trigger in escalation task** (`backend/app/tasks/escalation.py`, lines 75-125): The `_mark_window_expired` function (line 75) checks before marking an event as exhausted: if `attempt_count == 0` and `max_attempts > 0`, it extends the recovery window by 24 hours instead of giving up. Similarly, `_mark_attempts_exhausted` (line 106) skips exhaustion if `attempt_count == 0` even when max_attempts is technically reached.

### 5.2 Quiet Hours

Files: `backend/app/services/escalation.py` (lines 22-38) and `backend/app/tasks/recovery.py` (lines 20-32)

No recovery messages are sent between **9 PM and 9 AM IST** (Indian Standard Time). This is enforced in two places:

- During initial event processing: if the event is classified as "send_now" but it's quiet hours, the event is rescheduled to 9 AM IST the next morning.
- During escalation: before sending any follow-up, the engine checks quiet hours and reschedules to the next permitted time.

The event's status stays "pending" and `current_strategy` is set to "quiet_hours_rescheduled".

### 5.3 Per-Resource Cooldowns

File: `backend/app/utils/rate_limiter.py`, `check_per_resource_cooldown` (line 25)

Each phone number and email address has a 5-minute (300 second) cooldown after receiving a message. This prevents message flooding if multiple events trigger for the same customer.

Implementation: Redis SET with NX (only if not exists) and EX (expiry) flags. If the key already exists, the cooldown is active and the message is blocked. The messenger records this as a "blocked" outcome with "Cooldown active" error, and the degradation chain moves to the next channel/provider.

### 5.4 Recovery Window + Extension

File: `backend/app/tasks/recovery.py` (line 95) and `backend/app/tasks/escalation.py` (line 75)

Every event gets a **72-hour recovery window** from creation. When the window expires:

- If at least one outreach attempt was sent: the event is marked `exhausted` with reason "Recovery window expired without payment"
- If zero outreach attempts were sent (all were blocked/failed): the window is **extended by 24 hours** and the event stays pending with `current_strategy = "retry_after_window"`. This ensures every event gets at least one real attempt.

### 5.5 Rate Limiting

File: `backend/app/utils/rate_limiter.py`, `check_rate_limit` (line 5)

Sliding window rate limiter using Redis sorted sets. Each API endpoint has its own limit:

- Webhook endpoints: 100 requests / 60 seconds
- Events list: 60 / 60s
- Event counts: 60 / 60s
- Analytics: 30 / 60s
- Audit logs: 30 / 60s
- Simulate: 10 / 60s
- Live checkout: 5 / 60s

---

## 6. Monitoring and Operations

### 6.1 Health Endpoint

File: `backend/app/routers/health.py`

`GET /api/health` - Public (no auth required). Returns overall status and individual service statuses.

Checks three components:
- **Redis**: `ping()` command
- **Celery**: `inspect().ping()` with a 5-second timeout (runs in thread pool to avoid blocking the async event loop)
- **Supabase**: `select count from recovery_events limit 0`

Overall status is "ok" if Redis and Supabase are both ok. Celery can be "no workers" or "timeout" without degrading the overall status to "degraded" - only Redis and Supabase failures cause degradation.

Response model (`HealthResponse` in `models.py`, line 118):
```
{status: "ok"|"degraded", version: "1.0.0", services: {redis: "ok", celery: "ok", supabase: "ok"}}
```

### 6.2 Health Badge (Frontend)

File: `frontend/src/components/HealthBadge.jsx`

A component that polls the health endpoint every 30 seconds and shows a colored dot (green for ok, red for degraded/down) with a label ("all systems operational", "X services degraded", or "backend unreachable"). Each service name appears as a small badge. Hovering shows the raw service statuses as a tooltip.

_Note: This component exists but is not currently wired into the Layout - it was likely an earlier version of the health display._

### 6.3 Audit Logs with Auto-Refresh

The audit logs page refreshes every 15 seconds (see Section 2.6). The backend endpoint (`GET /api/audit-logs`) returns recovery attempts with full metadata including the provider degradation path and error traces.

### 6.4 Recovery Retry Failure Tracking

When a customer clicks a recovery link and their payment fails, Recovery Router logs it as a `payment_link` channel attempt on the parent recovery event (see Section 3.3). This creates a complete trace of customer interaction attempts visible in the event detail panel and audit logs.

---

## 7. Testing and Demo Tools

### 7.1 Simulator (10 Built-in Scenarios)

See Section 2.4 for the full list. Each scenario fires a real event through the live pipeline with randomized amounts (different each time, using `random.choice` in `build_scenarios` at `backend/app/routers/events.py`, line 17).

### 7.2 Bulk Data Generator

File: `backend/tests/generate_test_data.py`

A standalone script that generates 100 diverse recovery events via the webhook API:
- 50 payment failures (8 error types, 30 Indian names, random amounts from 199 to 24,999)
- 30 cart abandonments (60% high-value with 2-10 items, 40% low-value with 1-2 items)
- 20 overdue invoices (1-90 days late, amounts 5,000 to 100,000)

Each event gets a unique payment_id, random customer name, randomly generated email (name + random number @ Indian domain), and random Indian phone number. Events are sent with 100ms delays to avoid overwhelming the API.

After generation, the script fetches and prints analytics including total events, recovery rate, amounts, AI lift metrics, breakdown by event type, and channel ranking.

### 7.3 Custom Recipient Fields

In the Simulator page, there's a collapsible "Customer Details" panel that lets you set a custom name, email, and phone for test events. This overrides the default test recipient configured in `TEST_CUSTOMER_EMAIL` and `TEST_CUSTOMER_PHONE` environment variables. A "Reset to defaults" button clears the custom values.

### 7.4 Debug Endpoints

Two debug endpoints exist for troubleshooting (lines 554-600 in `events.py`):

- `POST /api/debug/escalate/{event_id}` - Manually triggers escalation for a single event and returns the before/after state plus all attempts.
- `POST /api/debug/test-update/{event_id}` - Tests if Supabase updates persist by writing, reading immediately, reading after 500ms, and reading after 2500ms.

### 7.5 Data Reset

`DELETE /api/reset/all-data?confirm=yes-delete-everything` (line 603) - Deletes all recovery events and attempts, resets ID sequences to start from 1. Requires the exact confirmation string.

### 7.6 Migration Endpoints

Two one-time migration endpoints for fixing data issues:

- `POST /api/migrate/fix-exhausted` (line 442) - Backfills missing `skip_reason` on old exhausted events and clears stale `next_action_at` and `recovery_window_ends` fields.
- `POST /api/migrate/fix-premature-exhaustion` (line 495) - Fixes events that were prematurely exhausted because cooldown blocks were counted as real failures. Reclassifies "failed" attempts with "Cooldown active" error as "blocked" and reopens the events.

---

## 8. API Endpoints (Complete List)

### Public (no auth)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | API info (name, version, docs link, health link) |
| GET | `/api/health` | System health check (Redis, Celery, Supabase) |
| POST | `/api/login` | Authenticate with APP_PASSWORD, returns token |
| POST | `/webhook/recovery-router` | Ingest recovery events (signature-verified) |
| POST | `/webhook/recovery-tracker` | Payment captured feedback loop (signature-verified) |
| GET | `/pay/{order_id}` | Self-hosted checkout page (renders HTML) |

### Authenticated (Bearer token via APP_PASSWORD)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/events` | List events with filters (status, event_type, date range, pagination) |
| GET | `/api/events/counts` | Event counts by status |
| GET | `/api/events/{event_id}/trace` | Full event trace with timeline |
| PATCH | `/api/events/{event_id}/control` | Pause/resume/cancel recovery |
| POST | `/api/simulate` | Fire a test scenario through the pipeline |
| POST | `/api/live-checkout` | Create a Razorpay test-mode order |
| GET | `/api/analytics` | Aggregate recovery analytics (cached 120s in Redis) |
| GET | `/api/audit-logs` | Recovery attempt logs with degradation paths |
| POST | `/api/debug/escalate/{event_id}` | Debug: manual escalation trigger |
| POST | `/api/debug/test-update/{event_id}` | Debug: test Supabase persistence |
| POST | `/api/migrate/fix-exhausted` | Migration: backfill exhausted events |
| POST | `/api/migrate/fix-premature-exhaustion` | Migration: fix cooldown misclassification |
| DELETE | `/api/reset/all-data` | Delete all data (requires confirmation) |

---

## 9. Frontend Features

### 9.1 Authentication

File: `frontend/src/App.jsx` (LoginPage component, line 37) + `frontend/src/lib/api.js`

Password-based login. The frontend sends the password to `POST /api/login`, receives the token, stores it in `sessionStorage`, and includes it as `Authorization: Bearer {token}` on all subsequent API calls. If any API call returns 401, the token is cleared and the login page is shown.

Logout button in the top navbar clears the token and returns to login.

### 9.2 Razorpay UI Design System

The frontend closely follows Razorpay's dashboard design language:

- **Navbar**: Dark navy (`#1B1F36`) with the exact Razorpay SVG wordmark logo (inline SVG path in `Layout.jsx`, line 22)
- **Sidebar**: White background, 240px width, with section dividers and icon-labeled navigation items
- **Typography**: Inter font family, consistent weight hierarchy (400/500/600/700)
- **Color palette**: Razorpay blue (`#528FF0`), navy (`#1B1F36`), surface grey (`#F7F8FA`), border grey (`#E8EAED`)
- **Status badges**: Color-coded pill badges - green for Paid, amber for In Progress, red for Gave Up, blue for On Hold, grey for Skipped
- **Type badges**: Red background for Payment, amber for Cart, blue for Invoice
- **Cards**: White with 1px border and 8px border radius
- **Tables**: Alternating hover states, sticky headers, horizontal scroll for responsive

### 9.3 Mobile Responsive

File: `frontend/src/index.css` (lines 98-155)

Three breakpoints:
- **Desktop** (>1024px): Full sidebar (240px) + content
- **Tablet** (768-1024px): Narrower sidebar (220px) + content
- **Mobile** (<768px): Sidebar becomes a slide-out drawer with hamburger menu button in navbar. A dark overlay covers the content when the drawer is open. The sidebar slides in from the left with a 0.25s ease transition and box shadow.

Additional mobile adjustments at 480px: tighter navbar padding, smaller logo.

### 9.4 Loading Bar

File: `frontend/src/components/LoadingBar.jsx`

A thin (3px) animated loading bar at the very top of the viewport. Uses a gradient animation that sweeps left-to-right and a growth animation that goes from 0% to 95% width over 8 seconds. The loading state is managed via React context - `setLoadingHooks` in `api.js` wires every API call to trigger the bar.

### 9.5 Date Range Picker

File: `frontend/src/components/DateRangePicker.jsx`

A dropdown date picker in the top navbar with preset options:
- Today, Yesterday, Last 7 Days, Last 30 Days, All Time

Plus a custom range section with two date inputs and an "Apply" button. The picker auto-closes when clicking outside (via `mousedown` event listener on document). All pages respect the selected date range for filtering data.

### 9.6 Error Boundary

File: `frontend/src/App.jsx` (ErrorBoundary class, line 12)

A React error boundary wrapping the entire app. If any component throws, it shows a centered error message with a "Reload" button that reloads the page.

### 9.7 Auto-Refresh

Data stays fresh across all pages:
- App-level data (analytics + events): 30 seconds (`App.jsx`, line 133)
- Events page (events + counts): 30 seconds (`EventsPage.jsx`, line 80)
- Audit logs: 15 seconds (`AuditLogsPage.jsx`, line 254)

---

## 10. Background Tasks

### 10.1 Celery Workers

File: `backend/app/celery_app.py`

Celery configuration:
- Broker and backend: Redis
- Serializer: JSON
- Late acknowledgement (`acks_late=True`): Tasks are acknowledged only after completion, so if a worker dies mid-task, the task is retried.
- Prefetch multiplier: 1 (one task at a time per worker)
- `task_reject_on_worker_lost=True`: If a worker dies, the task is requeued.

### 10.2 Celery Beat Schedule

Two periodic tasks:
- **Escalation cycle**: Every 300 seconds (5 minutes) - `app.tasks.escalation.run_escalation_cycle`
- **Invoice scan**: Every 21600 seconds (6 hours) - `app.tasks.invoice_scan.scan_overdue_invoices`

### 10.3 Invoice Scanner

File: `backend/app/services/invoice_scanner.py`

Every 6 hours, Recovery Router polls the Razorpay Invoices API (`GET /v1/invoices?type=invoice&status=issued`) for issued invoices that are past their due date. For each overdue invoice not already tracked in the database, it creates a recovery event with the invoice details and dispatches it through the standard pipeline.

The scanner paginates through all invoices (100 per page), calculates days overdue, and batch-checks which invoice IDs are already tracked to avoid duplicates.

---

## 11. Data Layer

### 11.1 Deduplication

File: `backend/app/utils/dedup.py`

Two-layer dedup:
- **Redis-based** (line 8): 1-hour TTL key per event identifier. Catches webhook retries within the same hour.
- **Database-based** (`_check_durable_dedup` in `backend/app/tasks/recovery.py`, line 56): Checks for existing events with the same payment_id, order_id, or invoice_id. Skips TEST_ prefixed IDs (simulator events are intentionally non-unique).

### 11.2 Webhook Normalization

File: `backend/app/utils/normalizer.py`

Handles two payload formats:
- Raw Razorpay `payment.failed` webhooks: Extracts fields from the nested `payload.payment.entity` structure, converts amount from paise to rupees.
- Custom format: Direct mapping to `RecoveryEventInput` fields.

### 11.3 Concurrency Control

Redis-based distributed locks are used throughout:
- **Event-level lock** (`lock:event:{id}`, 300s TTL) in escalation - prevents two escalation cycles from processing the same event simultaneously.
- **Escalation cycle lock** (`lock:escalation`, 240s TTL) - prevents overlapping escalation cycles.
- **Delayed send lock** (`lock:event:{id}`, 300s TTL) - prevents race between delayed send and escalation.

### 11.4 Analytics Caching

File: `backend/app/services/analytics.py`

Analytics queries are cached in Redis for 120 seconds (line 9). The cache key includes the date range parameters, so different date filters get separate cache entries. The analytics service paginates through all events (1000 per page) and computes:

- Summary: total events, recovered/pending/exhausted/no-action counts, recovery rate, total/recovered/pending amounts, average attempts to recover, average recovery time in hours
- AI Lift: comparison against a 15% industry baseline (sourced from Razorpay blog data), improvement in percentage points, lift multiplier, additional revenue recovered
- Breakdowns: by event type, by channel, by failure category - each with event count, amount, recovered count, and recovery rate
- Channel ranking: sorted by recovery rate

---

## 12. Infrastructure

### 12.1 Tech Stack

- **Backend**: FastAPI + Celery + Redis
- **Database**: Supabase (PostgreSQL)
- **Frontend**: React (Vite) with inline styles (no CSS framework beyond base CSS)
- **AI**: OpenRouter (multi-model)
- **Messaging**: Green API (WhatsApp), Twilio (WhatsApp + SMS), Resend (Email)
- **Payments**: Razorpay Orders API + Standard Checkout

### 12.2 CORS Configuration

File: `backend/app/main.py` (lines 22-36)

Allowed origins:
- Frontend URL from env
- localhost:5173 and localhost:3000 (development)
- albertabishek.com and subdomains
- Any `recovery-router*.vercel.app` domain (regex match)

### 12.3 Webhook Security

HMAC-SHA256 signature verification on all webhook endpoints. The raw request body is hashed with the `RAZORPAY_WEBHOOK_SECRET` and compared using `hmac.compare_digest` (timing-safe comparison) against the `X-Razorpay-Signature` header.

Body size is capped at 256KB to prevent abuse.

---

## 13. What's Not Built Yet

There are no TODO/FIXME comments in the codebase. The project is functionally complete for the buildathon. A few areas that are designed but not fully implemented:

- **Account & Settings page**: The sidebar shows an "Account & Settings" item (`Layout.jsx`, line 77) but clicking it does nothing - there's no settings page component.
- **Supabase Realtime**: The `LiveFeed.jsx` component and the Simulator page's "Pipeline Results" section reference "Live from Supabase" but the frontend uses polling (30-second intervals) rather than Supabase Realtime WebSocket subscriptions. The data stays current through polling.
- **HealthBadge component**: Exists (`frontend/src/components/HealthBadge.jsx`) but is not rendered in the current Layout - it was likely replaced by simpler health indicators.
- **StatTiles, ChannelRanking, RecoveryByType, SimulatorPanel, AILift components**: These files exist in `frontend/src/components/` but appear to be earlier versions of what's now built directly into OverviewPage and AnalyticsPage. They're not imported anywhere in the current app.

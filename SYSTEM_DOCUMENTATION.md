# Recovery Router — Complete System Documentation

> **Razorpay AI Buildathon — Track 3: Intelligent Revenue Recovery**
> Built by Albert Abishek I (study1only2@gmail.com)

---

## 1. What is Recovery Router?

Recovery Router is an **AI-powered revenue recovery engine** that plugs into Razorpay's payment ecosystem to automatically detect, classify, and recover failed payments, abandoned carts, and overdue invoices.

**The Problem:** Indian merchants lose 15-20% of revenue to payment failures, cart abandonment, and overdue invoices. Manual recovery is slow, generic, and misses the optimal timing window.

**The Solution:** Recovery Router uses GPT-4o-mini to classify each revenue leak, determine the best recovery channel (WhatsApp/Email/SMS), optimal timing, and probability of recovery — then executes the recovery action automatically with Razorpay Payment Links.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RECOVERY ROUTER                              │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │ Razorpay │───▶│ Webhook  │───▶│ Celery   │───▶│ AI Classify  │  │
│  │ Webhooks │    │ Endpoint │    │ Worker   │    │ (GPT-4o-mini)│  │
│  └──────────┘    └──────────┘    └──────────┘    └──────┬───────┘  │
│                                                         │          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────▼───────┐  │
│  │ Customer │◀───│ Twilio / │◀───│ Messenger│◀───│   Router     │  │
│  │          │    │ Resend   │    │ Service  │    │ (Channel +   │  │
│  │          │    │ SendGrid │    │          │    │  Timing)     │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────┬───────┘  │
│                                                         │          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────▼───────┐  │
│  │ Supabase │◀───│ Recovery │◀───│ Payment  │◀───│ Payment Link │  │
│  │ Database │    │ Tracker  │    │ Links    │    │ Generator    │  │
│  │ + Realtime│   │          │    │ (Razorpay│    │              │  │
│  └──────────┘    └──────────┘    │  API)    │    └──────────────┘  │
│                                  └──────────┘                      │
│  ┌──────────┐    ┌──────────┐                                      │
│  │ Upstash  │    │ Celery   │  Periodic Tasks:                     │
│  │ Redis    │    │ Beat     │  • Escalation Agent (every 5 min)    │
│  │ (Cache + │    │          │  • Invoice Scanner (every 6 hours)   │
│  │  Queue)  │    │          │                                      │
│  └──────────┘    └──────────┘                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend API | FastAPI (Python) | REST API, webhook handlers |
| Task Queue | Celery + Upstash Redis | Async processing, scheduling |
| AI Engine | OpenRouter (Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini) | Event classification, escalation, message personalization |
| Database | Supabase (PostgreSQL) | Event storage, real-time subscriptions |
| Cache / Queue | Upstash Redis | Rate limiting, dedup, cooldowns, task queue |
| Payment Links | Razorpay Orders API | Generate payment links + hosted checkout |
| WhatsApp (Primary) | Green API | WhatsApp with AI-personalized text |
| WhatsApp (Fallback) | Twilio | WhatsApp via content_sid template |
| SMS | Twilio | SMS messaging (trial: falls back to WhatsApp) |
| Email | Resend | AI-personalized HTML recovery emails |
| Frontend | React + Vite | Dashboard UI (Razorpay Blade-styled) |
| Realtime | Supabase Realtime | Live event updates in dashboard |

---

## 3. What Was in n8n vs What's Now in Our Codebase

### Originally Built in n8n (5 Workflows)

We prototyped the entire pipeline in n8n first, then rebuilt everything as production-grade Python code.

| n8n Workflow | What It Did | Now Lives In |
|---|---|---|
| **Recovery Router** | Webhook → AI Classify → Route → Payment Link → Send Message → Log | `tasks/recovery.py` (single Celery task) |
| **Escalation Agent** | Periodic: find pending events → AI decides next step → re-send or exhaust | `tasks/escalation.py` + `services/escalation.py` |
| **Recovery Tracker** | payment.captured webhook → match to pending event → mark recovered | `routers/webhooks.py` (recovery-tracker endpoint) + `services/recovery_tracker.py` |
| **Recovery Analytics API** | Query Supabase → compute stats → return JSON | `services/analytics.py` + `routers/analytics.py` |
| **Invoice Overdue Scanner** | Periodic: poll Razorpay invoices API → find overdue → feed into Recovery Router | `tasks/invoice_scan.py` + `services/invoice_scanner.py` |

### Why We Moved from n8n to Code

1. **Rate limiting & dedup** — n8n has no built-in Redis-backed sliding window rate limiter or deduplication
2. **Channel degradation** — If WhatsApp fails (Twilio trial restrictions), automatically fall back to email. This multi-step fallback logic is complex in n8n
3. **Concurrent AI calls** — Escalation uses `asyncio.gather()` to classify multiple events in parallel
4. **Per-resource cooldowns** — Don't message the same phone/email within 1 hour (Redis-backed)
5. **Ghost recovery prevention** — Only mark an event as "recovered" if `attempt_count > 0`; otherwise mark as "organic_recovery"
6. **Production reliability** — Celery with `acks_late`, `max_retries=3`, distributed locking

### n8n Workflows Are Still in the Repo

The 5 n8n workflow JSON files are kept in `n8n_workflow/` as reference/documentation. They show the original visual pipeline design and can be imported into n8n to demonstrate the architecture.

---

## 4. Complete Pipeline — How the System Works

### Stage 1: Event Ingestion

**Trigger:** A webhook hits `POST /webhook/recovery-router`

The system accepts 3 types of events:

1. **Razorpay `payment.failed` webhooks** — native Razorpay format, auto-normalized
2. **Cart abandonment events** — from merchant's frontend/backend
3. **Invoice overdue events** — from the Invoice Scanner or merchant API

**Processing:**
1. Rate limit check (100 req/min per endpoint)
2. Deduplication via Redis (1-hour TTL, keyed on payment_id/order_id/invoice_id)
3. Normalize payload (Razorpay's nested format → flat RecoveryEventInput)
4. Dispatch to Celery worker

### Stage 2: AI Classification

**Service:** `services/classifier.py`

The AI (via OpenRouter's 3-model chain: Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini) analyzes the event and returns:

| Field | Description |
|-------|-------------|
| `failure_category` | One of 11 categories (upi_timeout, card_expired, insufficient_funds, etc.) |
| `recovery_probability` | 0.0 to 1.0 (how likely recovery is) |
| `recommended_channel` | whatsapp, email, sms, or none |
| `recommended_timing` | immediate, 5_minutes, 30_minutes, 1_hour, 4_hours |
| `reasoning` | AI's explanation of why this classification |
| `skip_reason` | Why no action (for unrecoverable events) |

**Fallback:** If all 3 AI models fail (rate limits, timeouts, errors), a rule-based classifier kicks in using error code pattern matching. Fallback probabilities are penalized (× 0.7) and `fallback_used=True` is set on the classification result.

### 11 Failure Categories

| Category | Event Type | Recovery Prob | Channel | Timing |
|----------|-----------|--------------|---------|--------|
| `upi_timeout` | Payment Failure | 75-85% | WhatsApp | Immediate |
| `bank_downtime` | Payment Failure | 70-85% | WhatsApp | 30 min |
| `gateway_error` | Payment Failure | 80-90% | WhatsApp | 5 min |
| `card_expired` | Payment Failure | 40-60% | Email | Immediate |
| `insufficient_funds` | Payment Failure | 30-50% | SMS | 4 hours |
| `unrecoverable_decline` | Payment Failure | 0% | None | — |
| `high_intent_abandonment` | Cart Abandonment | 30-50% | WhatsApp | 1 hour |
| `browse_only_abandonment` | Cart Abandonment | 5-10% | None | — |
| `recently_overdue` | Invoice Overdue | 60-80% | WhatsApp | Immediate |
| `moderately_overdue` | Invoice Overdue | 30-50% | Email | Immediate |
| `long_overdue` | Invoice Overdue | 10-20% | Email | — |

### Stage 3: Action Routing

**Service:** `services/router.py`

Deterministic routing based on classification:

- `recommended_channel == "none"` → **No action** (event logged, status = `no_action_needed`)
- `recommended_timing == "immediate"` → **Send now**
- `recommended_timing != "immediate"` → **Delayed** (event scheduled for `next_action_at`, picked up by Escalation Agent)

### Stage 4: Payment Link Generation

**Service:** `services/payment_links.py`

Calls **Razorpay Payment Links API** (`POST /v1/payment_links/`):

- Amount converted to paise (× 100)
- Customer details attached
- `reference_id` links back to the recovery event
- `notes` contain source, event_type, failure_category, recovery_event_id
- `expire_by` set to recovery window end (72 hours)
- If API fails → fallback URL used

### Stage 5: Message Delivery

**Service:** `services/messenger.py`

Multi-channel delivery with intelligent degradation and AI-personalized messages:

```
WhatsApp chain:
    ├── Green API (AI-personalized text) → Success → Done
    ├── Twilio WhatsApp (content_sid template) → Success → Done
    └── Degrade to Email (Resend) → Success → Done

SMS chain:
    ├── Twilio SMS (AI-personalized text) → Success → Done
    ├── Green API WhatsApp (fallback) → Success → Done
    ├── Twilio WhatsApp (fallback) → Success → Done
    └── Degrade to Email (Resend) → Success → Done

Email chain:
    └── Resend (AI-personalized HTML) → Success → Done
```

Every provider attempt is logged in the `degradation_path` array for full audit trail.

**AI Message Personalization:** `services/message_generator.py` generates channel-appropriate messages using AI based on failure category, amount, customer name, attempt number, and tone. Falls back to templates when AI is unavailable.

**Per-resource cooldowns (Redis):**
- WhatsApp: 1 message per phone per 5 minutes
- SMS: 1 message per phone per 5 minutes
- Email: 1 email per address per 5 minutes

### Stage 6: Logging & Tracking

Every action is logged to Supabase:

- **`recovery_events` table** — master record with status, classification, attempts
- **`recovery_attempts` table** — each attempt with channel, outcome, message_id, payment link

### Stage 7: Escalation Agent (Periodic)

**Task:** `tasks/escalation.py` — runs every 5 minutes via Celery Beat

1. Acquires distributed Redis lock (prevents duplicate runs)
2. Queries Supabase for events where `status = "pending"` AND `next_action_at <= now`
3. Filters out: opted-out customers, expired windows, max attempts reached, unrecoverable declines, 0% probability
4. For each event, AI decides next action:

| Attempt | Strategy |
|---------|----------|
| 0-1 | Use original channel, friendly tone |
| 2 | Switch channel (WhatsApp↔Email), firm tone |
| 3 | SMS with urgent language |
| 4+ | Give up → mark as `exhausted` |

5. Generates new payment link, sends message, logs attempt
6. Schedules next action in 4 hours

**Concurrent AI calls:** Uses `asyncio.gather()` to make parallel OpenAI calls for all events in the batch.

### Stage 8: Recovery Tracking (Feedback Loop)

**Endpoint:** `POST /webhook/recovery-tracker`

When a customer pays via the recovery link, Razorpay sends `payment.captured` or `payment_link.paid`:

1. Extract payment_id/order_id from the webhook
2. Find matching pending recovery event in Supabase
3. **Ghost recovery check:** If `attempt_count == 0`, mark as `organic_recovery` (not attributable to Recovery Router)
4. If `attempt_count > 0`, mark as `recovered` with timestamp and amount

**Pending captures:** If the payment arrives before the event is logged (race condition), it's stored in `pending_captures` table for later matching.

### Stage 9: Invoice Scanner (Periodic)

**Task:** `tasks/invoice_scan.py` — runs every 6 hours via Celery Beat

1. Calls Razorpay Invoices API (`GET /v1/invoices?status=issued`)
2. Calculates `days_overdue` from due_date
3. Checks if invoice is already tracked (dedup)
4. Feeds new overdue invoices into the Recovery Router pipeline

---

## 5. End-to-End Examples

### Example 1: UPI Timeout Recovery (Immediate WhatsApp)

**Scenario:** Customer Ravi tries to pay ₹2,999 via UPI on a Razorpay merchant's checkout. The payment times out.

```
1. Razorpay fires `payment.failed` webhook to Recovery Router
2. Normalizer extracts: method=upi, error_code=TIMEOUT, amount=₹2,999
3. Celery worker picks up the task
4. AI Classification:
   - failure_category: "upi_timeout"
   - recovery_probability: 0.82
   - recommended_channel: "whatsapp"
   - recommended_timing: "immediate"
   - reasoning: "UPI timeout during standard hours — high retry success rate"
5. Router: action = "send_now", channel = "whatsapp"
6. Payment Link: Razorpay creates https://rzp.io/i/abc123 (₹2,999, expires in 72h)
7. Messenger: Twilio sends WhatsApp to Ravi:
   "Hi Ravi, your payment of INR 2,999.00 didn't go through.
    Complete it here: https://rzp.io/i/abc123"
8. Logged: recovery_events (status=pending, attempt_count=1)
9. Ravi clicks the link 10 minutes later, pays successfully
10. Razorpay fires `payment.captured` to /webhook/recovery-tracker
11. Recovery Tracker: matches order_id, attempt_count=1 → status="recovered"
12. Dashboard shows: ₹2,999 recovered, 1 attempt, 10 min recovery time
```

**Result:** ₹2,999 recovered in 10 minutes via 1 WhatsApp message.

### Example 2: Card Expired → Email → Escalation

**Scenario:** Customer Priya's card expired. She tries to pay ₹5,999 — payment fails.

```
1. Webhook received: error_code=CARD_EXPIRED, amount=₹5,999
2. AI Classification:
   - failure_category: "card_expired"
   - recovery_probability: 0.52
   - recommended_channel: "email"
   - recommended_timing: "immediate"
   - reasoning: "Expired card — customer needs to update card details"
3. Payment Link generated: https://rzp.io/i/def456
4. Email sent via Resend to priya@email.com:
   "Hi Priya, your payment of INR 5,999.00 didn't go through..."
   with "Complete Payment" button
5. Status: pending, attempt_count=1, next_action_at=now+4h

--- 4 hours later, Priya hasn't paid ---

6. Escalation Agent picks up the event (next_action_at <= now)
7. AI Escalation Decision (attempt 1):
   - action: "send"
   - channel: "email" (same channel, friendly reminder)
   - tone: "friendly"
8. New payment link generated, follow-up email sent
9. Status: attempt_count=2, next_action_at=now+4h

--- 4 more hours later ---

10. Escalation Agent (attempt 2):
    - AI decides: switch to WhatsApp, firm tone
    - WhatsApp message sent via Twilio
11. Status: attempt_count=3

--- 4 more hours later ---

12. Escalation Agent (attempt 3):
    - AI decides: SMS, urgent tone
    - SMS sent: "Payment of INR 5,999 failed. Retry: https://rzp.io/i/ghi789"
13. Priya pays via the SMS link
14. Recovery Tracker marks: status=recovered, 3 attempts, ~12h recovery time
```

**Result:** ₹5,999 recovered after 3 attempts across 3 channels over 12 hours.

### Example 3: High-Value Cart Abandonment

**Scenario:** Customer Amit adds ₹12,999 worth of items to cart, reaches checkout, but leaves without paying.

```
1. Merchant's frontend sends cart_abandonment event:
   {event_type: "cart_abandonment", cart_value: 12999, items_in_cart: 4,
    customer_name: "Amit", customer_email: "amit@email.com",
    customer_phone: "+91..."}
2. AI Classification:
   - failure_category: "high_intent_abandonment"
   - recovery_probability: 0.42
   - recommended_channel: "whatsapp"
   - recommended_timing: "1_hour"
   - reasoning: "High-value cart (₹12,999) with 4 items indicates
     purchase intent. 1-hour delay avoids pressure."
3. Router: action = "send_delayed", delay_seconds = 3600
4. Event saved: status=pending, next_action_at=now+1h

--- 1 hour later ---

5. Escalation Agent picks it up
6. Generates payment link for ₹12,999
7. WhatsApp sent: "Hi Amit, your payment of INR 12,999.00 didn't go
   through. Complete it here: https://rzp.io/i/jkl012"
8. Amit completes checkout → recovered
```

**Result:** ₹12,999 cart recovered via WhatsApp after strategic 1-hour delay.

### Example 4: Fraud Decline — No Action (Intelligent Skip)

**Scenario:** A stolen card is used to attempt a ₹24,999 payment. Razorpay declines it.

```
1. Webhook: error_code=FRAUD_SUSPECTED, amount=₹24,999
2. AI Classification:
   - failure_category: "unrecoverable_decline"
   - recovery_probability: 0.0
   - recommended_channel: "none"
   - recommended_action: "flag_and_block"
   - skip_reason: "Fraud suspected — do not attempt recovery"
3. Router: action = "no_action"
4. Event saved: status = "no_action_needed"
5. No payment link generated, no message sent
6. Dashboard shows event with skip_reason
```

**Result:** System correctly identifies fraud and takes zero action. No wasted resources, no contact with potential fraudster.

---

## 6. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook/recovery-router` | Main entry: accepts payment failures, cart abandonment, invoice events (HMAC verified) |
| `POST` | `/webhook/recovery-tracker` | Feedback loop: handles `payment.captured` / `payment_link.paid` (HMAC verified) |
| `GET` | `/api/events` | List recovery events (filters: status, event_type, from_date, to_date, limit, offset) |
| `GET` | `/api/events/{id}/trace` | Full event trace with all attempts and degradation paths |
| `GET` | `/api/audit-logs` | Recovery attempts audit trail (filters: event_id, from_date, to_date, limit, offset) |
| `POST` | `/api/simulate` | Fire test events through the live pipeline (rate limited: 10/min) |
| `GET` | `/api/analytics` | Aggregate analytics with date range filtering (cached in Redis) |
| `GET` | `/api/health` | Health check (Supabase, Redis, Celery worker status) |
| `GET` | `/pay/{order_id}` | Hosted checkout page (XSS-protected, regex-validated) |
| `GET` | `/` | API info |
| `GET` | `/docs` | Auto-generated Swagger docs |

---

## 7. Database Schema (Supabase)

### `recovery_events` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial (PK) | Auto-increment ID |
| `event_type` | text | payment_failure / cart_abandonment / invoice_overdue |
| `payment_id` | text | Razorpay payment ID |
| `order_id` | text | Razorpay order ID |
| `invoice_id` | text | Razorpay invoice ID |
| `amount` | numeric | Amount in rupees |
| `currency` | text | INR |
| `method` | text | upi / card / netbanking / wallet |
| `error_code` | text | TIMEOUT, CARD_EXPIRED, etc. |
| `error_description` | text | Human-readable error |
| `customer_email` | text | Customer email |
| `customer_phone` | text | Customer phone (+91...) |
| `customer_name` | text | Customer name |
| `leak_type` | text | = event_type |
| `failure_category` | text | AI-classified category |
| `recovery_probability` | numeric | 0.0 to 1.0 |
| `recommended_action` | text | AI-recommended action |
| `recommended_channel` | text | whatsapp / email / sms / none |
| `recommended_timing` | text | immediate / 5_minutes / etc. |
| `reasoning` | text | AI's reasoning |
| `skip_reason` | text | Why no action was taken |
| `status` | text | pending / recovered / exhausted / no_action_needed / organic_recovery |
| `attempt_count` | integer | Number of recovery attempts |
| `max_attempts` | integer | Default 5 |
| `escalation_level` | integer | Current escalation level |
| `current_strategy` | text | initial / friendly / firm / urgent / final / exhausted |
| `recovery_window_ends` | timestamptz | 72 hours from creation |
| `next_action_at` | timestamptz | When to take next action |
| `last_attempt_at` | timestamptz | Last attempt timestamp |
| `recovered_at` | timestamptz | When payment was recovered |
| `recovered_amount` | numeric | Actual recovered amount |
| `source` | text | api / simulator / razorpay_webhook |
| `created_at` | timestamptz | Row creation time |
| `updated_at` | timestamptz | Last update time |

### `recovery_attempts` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial (PK) | Auto-increment |
| `recovery_event_id` | integer (FK) | Links to recovery_events.id |
| `attempt_number` | integer | 1, 2, 3... |
| `channel_used` | text | Actual channel (may differ from recommended if degraded) |
| `action_taken` | text | Description of action |
| `message_id` | text | Twilio SID or Resend/SendGrid ID |
| `outcome` | text | sent / failed |
| `notes` | text | AI reasoning |
| `metadata` | jsonb | payment_link_id, payment_link_url, send_error, degraded_from |
| `created_at` | timestamptz | Attempt timestamp |

### `pending_captures` table

| Column | Type | Description |
|--------|------|-------------|
| `payment_id` | text | Razorpay payment ID |
| `order_id` | text | Razorpay order ID |
| `amount` | numeric | Captured amount |
| `method` | text | Payment method |
| `captured_at` | timestamptz | When payment was captured |

---

## 8. Safety & Reliability Features

### Rate Limiting (Sliding Window)
- Webhooks: 100 req/min per endpoint
- OpenAI: 50 req/min
- Simulate API: 10 req/min
- Analytics API: 30 req/min

### Deduplication
- Redis-backed, 1-hour TTL
- Keyed on payment_id → order_id → invoice_id
- Prevents double-processing of the same webhook

### Per-Resource Cooldowns
- WhatsApp: 1 msg/phone/5 min
- SMS: 1 msg/phone/5 min
- Email: 1 msg/address/5 min
- Prevents spam bombing customers

### Channel Degradation
- WhatsApp: Green API → Twilio WhatsApp → Email (Resend)
- SMS: Twilio SMS → Green API WhatsApp → Twilio WhatsApp → Email (Resend)
- Email: Resend
- Cooldown hit → no degradation (deliberate suppression)
- Full `degradation_path` logged on every attempt for audit trail

### Ghost Recovery Prevention
- `attempt_count == 0` at recovery time → `organic_recovery` status
- Ensures Recovery Router only takes credit for recoveries it actually caused

### Distributed Locking
- Escalation cycle uses Redis `SET NX` lock (240s TTL)
- Prevents multiple Celery workers from running escalation simultaneously

### Task Reliability
- `acks_late=True`: tasks acknowledged only after completion
- `max_retries=3` with exponential backoff (60s, 120s, 240s)
- `task_reject_on_worker_lost=True`: re-queue if worker dies

### AI Fallback
- 3-model chain via OpenRouter: Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini
- If all 3 models fail → rule-based classifier with error code pattern matching (`fallback_used=True`)
- If escalation AI fails → deterministic channel rotation (whatsapp→email→sms→email)
- Fallback probabilities penalized (× 0.7) to reflect lower confidence
- AI message generator also has template fallback when AI is unavailable

---

## 9. Frontend Dashboard

### 5 Pages

1. **Home (Overview)**
   - Revenue Recovered hero card (total ₹ amount)
   - At Risk / Pending / Exhausted summary cards
   - AI Lift vs Baseline comparison (17.5% industry baseline)
   - Channel Performance ranked bars
   - Recovery by Type grid
   - Recent Events table with live updates

2. **Recovery Events**
   - Filterable table with tabs (All / Pending / Recovered / Exhausted / No Action)
   - Server-side pagination (25 per page)
   - Date range filtering via global DateRangePicker

3. **Reports (Analytics)**
   - KPI strip: Total Events, Recovery Rate, Avg Attempts, Avg Time, AI Lift
   - Recovery by Event Type table
   - Channel Performance with ranked progress bars
   - Failure Category Breakdown grid

4. **Simulator**
   - 10 scenario cards across 3 groups (Payment Failure, Cart Abandonment, Invoice Overdue)
   - Fire real events through the live pipeline
   - Simulation Log shows results
   - Pipeline Results table with live Supabase updates

5. **Audit Logs**
   - Full recovery attempt history with degradation paths
   - Server-side pagination (30 per page)
   - Date range filtering
   - Shows: channel used, outcome, message_id, payment link, send errors, degraded_from

### Global Features
- **Date Range Picker** — Presets (Today, Yesterday, Last 7 Days, Last 30 Days, All Time) + custom range, applied across Overview, Events, and Audit Logs
- **Loading Bar** — Animated gradient progress bar at top during all API calls, reference-counted for concurrent fetches
- **Responsive Tables** — Horizontal scroll on all data tables, no column crunching
- **Supabase Realtime** — Live event updates via WebSocket, auto-refreshes on INSERT/UPDATE
- **No full-page reloads** — Loading bar replaces full-page loading spinners

### Responsive Design
- Desktop: sidebar + content layout (240px sidebar)
- Tablet: narrower sidebar (220px)
- Mobile: hamburger menu with slide-out sidebar overlay

---

## 10. External Services & Credentials

| Service | Purpose | Env Variable |
|---------|---------|-------------|
| Razorpay | Orders API + hosted checkout, Invoice API, webhooks | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` |
| OpenRouter | 3-model AI chain (Claude Haiku → Gemini Flash → GPT-4o-mini) | `OPENROUTER_API_KEY` |
| Green API | WhatsApp messaging (personalized text, primary) | `GREEN_API_INSTANCE_ID`, `GREEN_API_TOKEN`, `GREEN_API_URL` |
| Twilio | WhatsApp (template, fallback) + SMS | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` |
| Resend | AI-personalized HTML email delivery | `RESEND_API_KEY`, `RESEND_FROM_EMAIL` |
| Supabase | PostgreSQL database + Realtime subscriptions | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY` |
| Upstash Redis | Task queue, cache, rate limiting, dedup, cooldowns, locks | `UPSTASH_REDIS_URL` |

---

## 11. Running the System

### Backend (3 processes)

```bash
# 1. FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. Celery worker (processes recovery tasks)
celery -A app.celery_app worker --loglevel=info

# 3. Celery beat (scheduled tasks: escalation every 5min, invoice scan every 6h)
celery -A app.celery_app beat --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### Environment

All credentials must be in `backend/.env` (never committed to git).
Frontend env: `frontend/.env` (VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE).

---

## 12. Key Metrics & AI Lift

| Metric | Industry Baseline | Recovery Router |
|--------|------------------|-----------------|
| Recovery Rate | 15-20% (simple retries) | Higher (AI-optimized) |
| Channels | Usually email only | WhatsApp + Email + SMS |
| Timing | Fixed schedule | AI-optimized per event |
| Personalization | Generic | Category-specific messaging |
| Escalation | Manual | Automated 4-step with tone progression |
| Fraud Handling | Retry everything | Intelligent skip (zero waste) |

**AI Lift Formula:**
```
lift_multiplier = ai_recovery_rate / baseline_rate (17.5%)
additional_revenue = recovered_amount - (total_amount × 17.5%)
```

---

## 13. File Structure

```
Razorpay_buildathon/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app + CORS config
│   │   ├── config.py              # Settings from .env
│   │   ├── models.py              # Pydantic models (11 models)
│   │   ├── database.py            # Supabase client (thread-safe singleton)
│   │   ├── redis_client.py        # Redis client (thread-safe singleton)
│   │   ├── celery_app.py          # Celery config + beat schedule
│   │   ├── routers/
│   │   │   ├── webhooks.py        # Webhook endpoints with HMAC verification
│   │   │   ├── events.py          # Events API + simulator + audit logs + event trace
│   │   │   ├── analytics.py       # Analytics endpoint with date filtering
│   │   │   ├── health.py          # Health check (Supabase + Redis + Celery)
│   │   │   └── checkout.py        # Hosted checkout page (XSS-protected)
│   │   ├── services/
│   │   │   ├── ai_client.py       # OpenRouter client with 3-model fallback chain
│   │   │   ├── classifier.py      # AI classification + rule-based fallback
│   │   │   ├── router.py          # Action routing logic (send/delay/skip)
│   │   │   ├── payment_links.py   # Razorpay Orders API integration
│   │   │   ├── messenger.py       # Multi-provider messaging with fallback chains
│   │   │   ├── message_generator.py # AI-personalized message content
│   │   │   ├── analytics.py       # Analytics aggregation + Redis caching
│   │   │   ├── invoice_scanner.py # Razorpay invoice scanner (Celery Beat)
│   │   │   ├── escalation.py      # AI escalation engine (Celery Beat)
│   │   │   └── recovery_tracker.py # Recovery attribution + ghost prevention
│   │   ├── tasks/
│   │   │   ├── recovery.py        # Main Celery task (full pipeline)
│   │   │   ├── escalation.py      # Escalation scheduled task
│   │   │   └── invoice_scan.py    # Invoice scan scheduled task
│   │   └── utils/
│   │       ├── normalizer.py      # Webhook payload normalization
│   │       ├── dedup.py           # Redis-based deduplication
│   │       ├── rate_limiter.py    # Sliding window rate limiter + cooldowns
│   │       └── templates.py       # Legacy message templates
│   ├── tests/
│   │   ├── e2e_test.py            # 31 automated E2E tests
│   │   ├── generate_test_data.py  # Bulk test data via API
│   │   ├── generate_and_process.py # Direct processing (no Celery)
│   │   └── process_queue.py       # Manual queue processing
│   ├── requirements.txt
│   ├── .env                       # Credentials (gitignored)
│   └── .env.example               # Template
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Main app with 5 pages + realtime
│   │   ├── main.jsx               # Entry point with LoadingProvider
│   │   ├── index.css              # TailwindCSS entry
│   │   ├── components/
│   │   │   ├── Layout.jsx         # Sidebar nav + header with DateRangePicker
│   │   │   ├── OverviewPage.jsx   # Dashboard overview
│   │   │   ├── EventsPage.jsx     # Events list with tabs + pagination
│   │   │   ├── AnalyticsPage.jsx  # Reports/analytics
│   │   │   ├── SimulatorPage.jsx  # Test scenario simulator
│   │   │   ├── AuditLogsPage.jsx  # Audit trail with pagination
│   │   │   ├── DateRangePicker.jsx # Global date range filter
│   │   │   ├── LoadingBar.jsx     # Global loading progress bar
│   │   │   ├── StatTiles.jsx      # Stat cards
│   │   │   ├── AILift.jsx         # AI vs baseline comparison
│   │   │   ├── ChannelRanking.jsx # Channel performance chart
│   │   │   ├── RecoveryByType.jsx # Recovery breakdown by type
│   │   │   ├── LiveFeed.jsx       # Live event feed
│   │   │   ├── HealthBadge.jsx    # System health indicator
│   │   │   └── SimulatorPanel.jsx # Simulator controls
│   │   └── lib/
│   │       ├── api.js             # API client with loading hooks
│   │       └── supabase.js        # Supabase client
│   ├── package.json
│   ├── vite.config.js             # Vite config with API proxy
│   ├── .env                       # Frontend env vars (gitignored)
│   └── .env.example               # Template
├── AUDIT.md                       # Security audit (31 findings, all fixed)
├── SECURITY.md                    # Security model documentation
├── E2E_TEST_REPORT.md             # E2E test results
├── SYSTEM_DOCUMENTATION.md        # Complete system documentation
├── BUILD_PLAN.md                  # Build plan with critical fixes
├── VERIFY_LOG.md                  # Build verification log
└── README.md
```

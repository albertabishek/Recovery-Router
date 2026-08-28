# Recovery Router — Complete Build Plan

**Project:** Recovery Router — Razorpay AI Buildathon Track 3  
**Author:** Albert Abishek I  
**Deadline:** September 5, 2026  
**Date:** August 26, 2026 (Updated with Gemini review fixes)  
**Status:** n8n workflows DONE (5 workflows running on Railway) → Now building FastAPI + React code version

---

## Critical Fixes Applied (From Technical Review)

> These fixes address 5 critical blind spots identified during technical review. Each one would be caught by a Razorpay engineer evaluating the code.

### Fix 1: Celery + Upstash Redis (NOT custom asyncio queue)
**Problem:** Custom `brpop` loop in asyncio has no ACK/NACK — if Railway container restarts mid-task, the task is popped and lost forever.  
**Fix:** Use **Celery** with Upstash Redis URL as broker and result backend. Celery handles task retries, worker crashes, and acknowledgment safely. No Docker needed — Celery worker connects to Upstash over SSL (`rediss://`), deployed as a separate Railway service.

### Fix 2: Payment Link Expiry (`expire_by`)
**Problem:** Razorpay payment link payload had no `expire_by` parameter. A payment link for a 72-hour recovery window would stay valid forever.  
**Fix:** Add `"expire_by": <unix_timestamp>` matching the event's `recovery_window_ends`. Proves the agent's guardrails extend into the actual financial gateway.

### Fix 3: Ghost Recovery Attribution
**Problem:** If AI decides "No Action" but the customer pays organically, the tracker matches by `order_id` and marks it as "Recovered" — inflating AI Lift metrics with a recovery the system didn't facilitate.  
**Fix:** In `recovery_tracker`, only update status to `recovered` IF `attempt_count > 0`. If zero attempts were made, log as `organic_recovery` — do NOT pad AI metrics.

### Fix 4: Cart Abandonment Integration Dependency
**Problem:** Razorpay sends webhooks for failed payments but NOT for abandoned carts (cart state lives on merchant's frontend/backend).  
**Fix:** Explicitly document: "Cart Abandonment events require the merchant to POST to `/webhook/recovery-router` from their frontend tracking pixel or backend checkout service." Include a sample integration snippet in docs.

### Fix 5: Concurrent OpenAI Calls in Escalation
**Problem:** Escalation agent fetches up to 20 events. Sequential OpenAI calls at ~1.5s each = 30-second blocking loop.  
**Fix:** Use `asyncio.gather()` to make all 20 OpenAI API calls concurrently, dropping total time from ~30s to ~2s.

### Fix 6: Merge Classify + Route into Single Celery Task
**Problem:** Splitting classify → route → generate link → send into 4 separate Redis queues is over-engineering for a buildathon and introduces failure points between steps.  
**Fix:** One Celery task `process_recovery_event` handles the full pipeline: Classify → Route → Generate Payment Link → Send Message → Log. Single atomic execution thread per event.

---

## What Already Exists (DONE)

### n8n Workflows (Running on Railway at n8n.betiwonthearback.com)

| # | Workflow | ID | Status | What It Does |
|---|----------|----|--------|-------------|
| 1 | **Recovery Router** | `qWboQxSvPDSiyg4d` | ACTIVE | Webhook → Normalize → AI Classify (GPT-5 Mini) → Log to Supabase → Generate Razorpay Payment Link → Route by Channel → Send (WhatsApp/Email/SMS/No-Action) → Log Attempt |
| 2 | **Invoice Overdue Scanner** | `iCqvY2FsG4qwnrH5` | ACTIVE | Every 6h → GET Razorpay /v1/invoices → Split → POST to Recovery Router webhook |
| 3 | **Recovery Tracker** | `i0Nku6eWdDUj05Dx` | ACTIVE | Webhook receives payment.captured + payment_link.paid → Find recovery event by order_id → Mark recovered |
| 4 | **Escalation Agent** | `PaPzRiBHQaAw5nF0` | ACTIVE | Every 5min → Fetch due events (≤20) → Filter actionable → Generate Payment Link → AI Escalation Decision → Route → Send → Log Attempt → Update State |
| 5 | **Recovery Analytics API** | `N0qClQhURICRTvbU` | ACTIVE | GET webhook → Fetch all events → Compute analytics (JS) → Respond with JSON (CORS enabled) |

### Supabase Database (DONE — Tables exist and have 29+ events)

**Table: `recovery_events`** — event data + AI classification + agent state  
**Table: `recovery_attempts`** — every recovery action taken (agent memory)

### Credentials Available

| Service | Key Detail |
|---------|-----------|
| **Razorpay** | Test mode keys configured in `.env` |
| **OpenAI** | API key configured in `.env` |
| **Twilio** | SID + auth token configured in `.env` (trial — verified numbers only) |
| **SendGrid** | API key configured in `.env` (dropped — using Resend only) |
| **Resend** | API key configured in `.env`, domain: `mail.albertabishek.com` (verified) |
| **Supabase** | Project configured in `.env`, using session pooler connection |
| **Upstash Redis** | URL configured in `.env` (rediss:// SSL) |

---

## What We're Building Now

Port all n8n logic to a **FastAPI backend + React frontend** deployed on **Railway**. The n8n version proved the logic works. The code version handles scale, adds the dashboard, and makes a production-grade submission.

### Why Code Version

1. n8n workflows ARE the product and will stay running — they prove it works
2. Code version handles concurrency, rate limits, retries properly
3. React dashboard is the demo centerpiece for judges
4. Shows judges: "I prototyped in n8n, then built production code — ready for Razorpay scale"
5. GitHub repo with clean code is a submission requirement

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND                          │
│  Recovery Dashboard (Vite + React + Tailwind)               │
│  - 3 stat tiles: At Risk / Recovered / Recovery Rate        │
│  - Live event feed (Supabase realtime)                      │
│  - Recovery by type breakdown                               │
│  - Channel effectiveness ranking                            │
│  - AI Lift comparison (vs 17.5% baseline)                   │
│  - Test event simulator panel                               │
│  Deployed on: Railway (static serve) or Vercel              │
└──────────────────────────┬──────────────────────────────────┘
                           │ API calls
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                          │
│  Deployed on: Railway                                        │
│                                                              │
│  Endpoints:                                                  │
│  POST /webhook/recovery-router     ← payment.failed + cart   │
│  POST /webhook/recovery-tracker    ← payment.captured        │
│  GET  /api/analytics               ← dashboard data          │
│  POST /api/simulate                ← test event generator    │
│  GET  /api/events                  ← paginated event list    │
│  GET  /api/health                  ← health check            │
│                                                              │
│  Celery Workers (via Upstash Redis broker):                   │
│  - process_recovery_event          ← classify→route→send     │
│  - run_escalation_cycle            ← periodic escalation     │
│  - scan_overdue_invoices           ← periodic invoice poll   │
│  Beat schedules escalation (5min) + invoice scan (6h)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Supabase    │  │  Upstash     │  │  External    │
│  PostgreSQL  │  │  Redis       │  │  APIs        │
│              │  │              │  │              │
│ recovery_    │  │ Task queue   │  │ Razorpay API │
│ events       │  │ Rate limit   │  │ OpenAI API   │
│ recovery_    │  │ counters     │  │ Twilio API   │
│ attempts     │  │ Dedup cache  │  │ Resend API   │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## Tech Stack (Verified Versions — August 2026)

| Layer | Technology | Version | Why |
|-------|-----------|---------|-----|
| **Backend** | FastAPI | `0.141.1` | Async, fast, type hints, easy to understand |
| **Task Queue** | Celery | `5.6.3` | Production task queue with ACK/NACK, retry, crash safety |
| **Broker/Cache** | Upstash Redis (via `redis` lib) | `redis>=5.3.0` | Serverless Redis, no Docker needed, Celery broker + result backend + rate limiting + dedup + caching |
| **Database** | Supabase PostgreSQL (via `supabase`) | `2.31.0` | Already has data, realtime subscriptions for frontend |
| **AI** | OpenAI GPT-5 Mini (via `openai`) | `3.3.0` | Same model as n8n workflows, structured outputs via Pydantic |
| **Email** | Resend (primary, via `resend`) | `2.10.0` | Verified domain `mail.albertabishek.com` |
| **Email Fallback** | SendGrid (via `sendgrid`) | `6.11.0` | Backup if Resend fails |
| **WhatsApp/SMS** | Twilio (via `twilio`) | `9.10.9` | Already configured in n8n (trial — verified numbers only) |
| **Payment Links** | Razorpay API (via `httpx`) | `0.28.1` | Generate one-tap payment links per recovery |
| **HTTP Client** | httpx | `0.28.1` | Async HTTP for Razorpay API calls |
| **Frontend** | React + Vite | `19.x` / `6.x` | Fast build, modern, clean |
| **CSS** | Tailwind CSS v4 (via `@tailwindcss/vite`) | `4.3.3` | Utility-first, responsive, Vite plugin |
| **Realtime** | `@supabase/supabase-js` | `2.x` | Live event feed without polling |
| **Deployment** | Railway | — | n8n already there, single platform |
| **Python** | Python | `3.11+` | Required by all dependencies |

### Python requirements.txt (Pinned)
```
fastapi==0.141.1
uvicorn[standard]==0.34.0
celery[redis]==5.6.3
redis>=5.3.0
supabase==2.31.0
openai==3.3.0
resend==2.10.0
sendgrid==6.11.0
twilio==9.10.9
httpx==0.28.1
pydantic==2.11.0
python-dotenv==1.1.0
```

### Celery + Upstash Redis Configuration
```python
import ssl

UPSTASH_REDIS_URL = "rediss://default:<password>@grown-bluegill-112695.upstash.io:6379"

celery_app = Celery(
    "recovery_router",
    broker=UPSTASH_REDIS_URL,
    backend=UPSTASH_REDIS_URL,
)

celery_app.conf.update(
    broker_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
    redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
    broker_transport_options={"visibility_timeout": 3600},
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,           # Don't ACK until task completes
    worker_prefetch_multiplier=1,  # One task at a time per worker
    task_reject_on_worker_lost=True,  # Re-queue if worker crashes
    task_default_retry_delay=60,
    task_max_retries=3,
)
```

### Railway Deployment (Procfile)
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: celery -A app.celery_app worker --loglevel=info --concurrency=4
beat: celery -A app.celery_app beat --loglevel=info
```
Three Railway services: `web` (FastAPI), `worker` (Celery), `beat` (periodic scheduler). All connect to the same Upstash Redis URL.

---

## Project Structure

```
recovery-router/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, CORS, lifespan
│   │   ├── config.py               # Environment variables, settings
│   │   ├── models.py               # Pydantic models (request/response)
│   │   ├── database.py             # Supabase client + helpers
│   │   ├── celery_app.py            # Celery app config (Upstash Redis broker)
│   │   ├── redis_client.py         # Upstash Redis connection (rate limit, dedup, cache)
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── webhooks.py         # POST /webhook/recovery-router, /recovery-tracker
│   │   │   ├── analytics.py        # GET /api/analytics
│   │   │   ├── events.py           # GET /api/events, POST /api/simulate
│   │   │   └── health.py           # GET /api/health
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── classifier.py       # AI classification (OpenAI structured output)
│   │   │   ├── router.py           # Action routing logic (deterministic)
│   │   │   ├── messenger.py        # Send WhatsApp/Email/SMS (Twilio + Resend)
│   │   │   ├── payment_links.py    # Razorpay payment link generation
│   │   │   ├── escalation.py       # Escalation agent logic
│   │   │   ├── invoice_scanner.py  # Razorpay invoice polling
│   │   │   ├── recovery_tracker.py # Match payments to recovery events
│   │   │   └── analytics.py        # Compute analytics aggregations
│   │   │
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── recovery.py         # Celery task: process_recovery_event (classify→route→send)
│   │   │   ├── escalation.py       # Celery task: run_escalation_cycle (periodic, every 5min)
│   │   │   └── invoice_scan.py     # Celery task: scan_overdue_invoices (periodic, every 6h)
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── normalizer.py       # Normalize webhook payloads (Razorpay raw + custom)
│   │       ├── rate_limiter.py     # Rate limiting via Upstash Redis
│   │       ├── dedup.py            # Idempotency / deduplication
│   │       └── templates.py        # Email HTML templates, SMS/WhatsApp message templates
│   │
│   ├── requirements.txt
│   ├── Procfile                    # Railway deployment
│   ├── railway.toml
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── components/
│   │   │   ├── Dashboard.jsx       # Main dashboard layout
│   │   │   ├── StatTiles.jsx       # 3 big numbers: At Risk / Recovered / Rate
│   │   │   ├── LiveFeed.jsx        # Scrolling event feed (realtime)
│   │   │   ├── RecoveryByType.jsx  # Breakdown by leak type
│   │   │   ├── ChannelRanking.jsx  # Channel effectiveness
│   │   │   ├── AILift.jsx          # AI vs baseline comparison
│   │   │   ├── SimulatorPanel.jsx  # Test event generator UI
│   │   │   └── EventDetail.jsx     # Single event detail view
│   │   ├── lib/
│   │   │   ├── supabase.js         # Supabase client (realtime)
│   │   │   └── api.js              # Backend API calls
│   │   └── styles/
│   │       └── index.css           # Tailwind + custom styles
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── scripts/
│   ├── setup_db.sql                # Supabase table creation (idempotent)
│   ├── generate_test_data.py       # Generate realistic test events
│   └── seed_events.py              # Seed Supabase with test data
│
├── n8n_workflows/                  # Existing n8n JSON exports (already done)
│   ├── Recovery Router.json
│   ├── Escalation Agent.json
│   ├── Recovery Tracker.json
│   ├── Recovery Analytics API.json
│   └── Invoice Overdue Scanner.json
│
├── docs/
│   ├── architecture.md             # System diagram + component docs
│   ├── classification_taxonomy.md  # All failure categories with rules
│   ├── routing_matrix.md           # Input → action mapping
│   └── api_reference.md            # API endpoint documentation
│
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

---

## Detailed Component Specifications

### 1. Webhook Endpoints

#### POST /webhook/recovery-router

**Purpose:** Entry point for all three event types.

**Accepts:**
```json
{
  "event_type": "payment_failure | cart_abandonment | invoice_overdue",
  "payment_id": "pay_xxx",
  "order_id": "order_xxx",
  "invoice_id": "inv_xxx",
  "amount": 4200,
  "currency": "INR",
  "method": "upi | card | netbanking | wallet",
  "error_code": "TIMEOUT | INSUFFICIENT_FUNDS | CARD_EXPIRED | BANK_DOWNTIME | FRAUD | GATEWAY_ERROR",
  "error_description": "...",
  "customer_email": "customer@example.com",
  "customer_phone": "+919042824369",
  "customer_name": "Customer Name",
  "cart_value": 4200,
  "items_in_cart": 3,
  "days_overdue": 5
}
```

**Also accepts raw Razorpay `payment.failed` webhook payload:**
- Detects `body.event === 'payment.failed'`
- Extracts from `payload.payment.entity.*`
- Normalizes to same internal format

**Flow:**
1. Receive webhook → validate payload
2. Dedup check (Redis: `dedup:{payment_id}` with 1h TTL) → reject if duplicate
3. Normalize event data (15 fields with null-safe defaults)
4. Dispatch Celery task `process_recovery_event.delay(event_data)`
5. Return 200 immediately (webhook must respond fast)
6. **Celery worker picks up:** AI classify → Log to Supabase → Generate payment link → Route → Send message → Log attempt (single atomic task)

**Error handling:**
- Invalid payload → 400 with error details
- Duplicate event → 200 with `{"status": "duplicate", "message": "Event already processed"}`
- Celery broker unavailable → 503 with retry-after header
- Any internal error → 500, log error, don't lose the event (write raw to Supabase `raw_events` table as fallback)

#### POST /webhook/recovery-tracker

**Purpose:** Feedback loop — mark events as recovered when payment is captured.

**Accepts:** Razorpay `payment.captured` and `payment_link.paid` webhook payloads.

**Flow:**
1. Parse webhook event type
2. For `payment.captured`: extract payment_id, amount, order_id, method
3. For `payment_link.paid`: extract payment_link_id, reference_id, payment details
4. Query Supabase: `recovery_events WHERE order_id = ? AND status = 'pending'` (LIMIT 1)
5. If found AND `attempt_count > 0`: UPDATE → `status='recovered'`, `recovered_at=now`, `recovered_amount=amount`, `payment_id=new_payment_id`
6. If found AND `attempt_count == 0`: Log as `organic_recovery` — do NOT pad AI metrics (Ghost Recovery Fix)
7. If not found: Log as organic payment (not a recovery)

**Edge cases:**
- Multiple pending events with same order_id → recover the most recent one
- Payment amount differs from original (partial payment) → still mark recovered, log amount difference
- Webhook arrives before classification completes → event doesn't exist yet → store in `pending_captures` table, recheck in 5 minutes

### 2. Classification Engine (services/classifier.py)

**Purpose:** The brain. Takes normalized event data, returns structured classification.

**Model:** OpenAI GPT-5 Mini with structured output (JSON mode)

**System prompt:** Same as n8n workflow (proven, tested with 29+ events). Contains:
- 12 classification categories with rules
- Recovery probability ranges per category
- Channel recommendations per category
- Timing recommendations per category
- Skip reasons for unrecoverable declines

**Input:** Normalized event data (event_type, method, error_code, amount, currency, customer_name, days_overdue, cart_value, items_in_cart)

**Output schema:**
```python
class ClassificationResult(BaseModel):
    leak_type: Literal["payment_failure", "cart_abandonment", "invoice_overdue"]
    failure_category: str  # e.g., "upi_timeout", "insufficient_funds", etc.
    recovery_probability: float  # 0.0 to 1.0
    recommended_action: str  # e.g., "whatsapp_retry_link"
    recommended_channel: Literal["whatsapp", "email", "sms", "none"]
    recommended_timing: str  # "immediate", "5_minutes", "30_minutes", "1_hour", "4_hours"
    reasoning: str  # Why this action was chosen
    alternative_action: Optional[str]
    skip_reason: Optional[str]  # Only for no-action events
```

**Classification categories (12 total):**

| Category | Event Type | Probability | Channel | Timing |
|----------|-----------|-------------|---------|--------|
| upi_timeout | payment_failure | 0.75-0.85 | WhatsApp | Immediate |
| bank_downtime | payment_failure | 0.70-0.85 | WhatsApp | 30 min |
| card_expired | payment_failure | 0.40-0.60 | Email | Immediate |
| insufficient_funds | payment_failure | 0.30-0.50 | SMS | 4 hours |
| gateway_error | payment_failure | 0.80-0.90 | WhatsApp | 5 min |
| unrecoverable_decline | payment_failure | 0 | None | — |
| high_intent_abandonment | cart_abandonment | 0.30-0.50 | WhatsApp | 1 hour |
| browse_only_abandonment | cart_abandonment | 0.05-0.10 | None | — |
| recently_overdue | invoice_overdue | 0.60-0.80 | WhatsApp | Immediate |
| moderately_overdue | invoice_overdue | 0.30-0.50 | Email | Immediate |
| long_overdue | invoice_overdue | 0.10-0.20 | Email | — |

**Rate limiting for OpenAI:**
- Max 50 classifications per minute (Upstash Redis counter)
- On rate limit: enqueue with delay, don't drop
- On API error: retry 3 times with exponential backoff (1s, 4s, 16s)
- On persistent failure: log event with `classification_failed` status, alert

**Fallback classification (if AI is down):**
- Rule-based fallback using error_code mapping
- Lower confidence scores (multiply by 0.7)
- Flag as `fallback_classification: true` in the event record

### 3. Action Router (services/router.py)

**Purpose:** Deterministic routing based on classification output. No AI needed here.

**Logic:**
```python
def route_action(classification: ClassificationResult) -> ActionPlan:
    if classification.recommended_channel == "none":
        return ActionPlan(action="no_action", skip_reason=classification.skip_reason)
    
    # Calculate next_action_at based on timing
    timing_map = {
        "immediate": timedelta(seconds=0),
        "5_minutes": timedelta(minutes=5),
        "30_minutes": timedelta(minutes=30),
        "1_hour": timedelta(hours=1),
        "4_hours": timedelta(hours=4),
    }
    delay = timing_map.get(classification.recommended_timing, timedelta(seconds=0))
    
    if delay.total_seconds() == 0:
        # Execute immediately
        return ActionPlan(action="send_now", channel=classification.recommended_channel)
    else:
        # Schedule for later
        return ActionPlan(action="send_delayed", channel=classification.recommended_channel, delay=delay)
```

### 4. Message Sender (services/messenger.py)

**Channels:**

#### WhatsApp (via Twilio)
- From: `+17372508034` (Twilio sandbox number)
- To: customer_phone (must be verified on trial)
- Message includes: customer name, amount, failure category, payment link URL
- `toWhatsapp: false` on trial (sends as SMS instead)
- **Limitation:** Trial account — only verified numbers. Document this honestly.

#### Email (via Resend — PRIMARY)
- From: `noreply@mail.albertabishek.com` (verified domain)
- To: customer_email
- HTML template with: heading, personalized body, "Complete Payment" CTA button, AI reasoning
- Resend has higher deliverability than SendGrid on trial

#### Email (via SendGrid — FALLBACK)
- Used if Resend fails
- From: `abishekialbert@gmail.com`
- Same HTML template

#### SMS (via Twilio)
- From: `+17372508034`
- To: customer_phone
- Short message (<160 chars) with payment link
- **Limitation:** Indian numbers need templates on trial

**Rate limiting per channel:**
- WhatsApp/SMS (Twilio): max 1 message per phone number per hour (Redis key: `msg:{phone}:{channel}`)
- Email (Resend): max 1 email per email address per 2 hours
- Global: max 100 messages per hour across all channels

**Error handling per channel:**
- Twilio error → log as `outcome: 'failed'`, try next channel in fallback order
- Resend error → fallback to SendGrid
- All channels fail → log event as `delivery_failed`, schedule retry in 1 hour
- Channel fallback order: WhatsApp → SMS → Email (or as recommended by AI)

### 5. Payment Link Generation (services/payment_links.py)

**Purpose:** Create unique Razorpay payment links for every recovery message.

**API:** `POST https://api.razorpay.com/v1/payment_links/`

**Auth:** HTTP Basic Auth (Key ID + Secret)

**Payload:**
```json
{
  "amount": 420000,  // paise (amount * 100)
  "currency": "INR",
  "description": "Complete your payment - Recovery Router",
  "customer": {
    "name": "Customer Name",
    "email": "customer@example.com",
    "contact": "+919042824369"
  },
  "expire_by": 1724700000,  // unix timestamp matching recovery_window_ends
  "notify": { "sms": false, "email": false },
  "reference_id": "order_xxx",
  "notes": {
    "source": "recovery_router",
    "event_type": "payment_failure",
    "failure_category": "upi_timeout",
    "recovery_event_id": "uuid"
  }
}
```

**Returns:** `{ id, short_url, status }` — the `short_url` is the one-tap payment link.

**Error handling:**
- API error → use fallback URL: `https://rzp.io/i/recovery` (generic)
- Rate limit (Razorpay: 25 req/sec on test) → queue with backoff
- Store `payment_link_id` and `payment_link_url` in `recovery_attempts.metadata`

### 6. Escalation Agent (services/escalation.py)

**Purpose:** Autonomous agent that periodically reviews pending events and decides next action.

**Schedule:** Every 5 minutes (via Celery Beat periodic task)

**Flow:**
1. Fetch from Supabase: `recovery_events WHERE status='pending' AND next_action_at <= now()` LIMIT 20
2. Filter actionable (code logic — same as n8n):
   - Skip if `opted_out = true`
   - Skip if `recovery_window_ends <= now` (72h window expired)
   - Skip if `attempt_count >= max_attempts` (default 5)
   - Skip if `failure_category = 'unrecoverable_decline'` or `recovery_probability = 0`
3. For all actionable events (batch via `asyncio.gather()` — 20 events in ~2s instead of ~30s):
   a. Generate fresh Razorpay payment link (with `expire_by`)
   b. Call AI (GPT-5 Mini) for escalation decision — all calls concurrent
   c. Route to channel (WhatsApp/Email/SMS/Give Up)
   d. Send message
   e. Log attempt to `recovery_attempts`
   f. Update event state: `attempt_count++`, `escalation_level`, `next_action_at=now+4h`, `current_strategy`

**Escalation strategy matrix:**

| Attempt | Channel Strategy | Tone |
|---------|-----------------|------|
| 0 (first) | Use originally recommended channel | Friendly reminder |
| 1 | Switch channel (WhatsApp↔Email, SMS→WhatsApp) | Firm follow-up |
| 2 | SMS with urgent language | Urgent — time-sensitive |
| 3 | Email final notice | Formal — mentions escalation |
| 4+ | Give up → status='exhausted' | — |

**Concurrency control:**
- Redis lock: `escalation:lock` with 4-minute TTL (prevents overlapping runs)
- If lock exists, skip this run (next run in 5 min will pick up)

### 7. Invoice Overdue Scanner (services/invoice_scanner.py)

**Purpose:** Polls Razorpay for overdue invoices and feeds them into the pipeline.

**Schedule:** Every 6 hours

**Flow:**
1. `GET https://api.razorpay.com/v1/invoices?type=invoice&status=issued&count=100`
2. Auth: HTTP Basic Auth (Razorpay credentials)
3. For each invoice:
   - Convert amount from paise to rupees (`amount / 100`)
   - Calculate `days_overdue = floor((now - due_date * 1000) / 86400000)`
   - Extract customer details from `customer_details.{name, email, contact}`
   - POST to internal recovery pipeline (same as webhook handler)
4. Dedup: check if invoice_id already exists in `recovery_events` → skip if so

### 8. Analytics Engine (services/analytics.py)

**Purpose:** Compute aggregate metrics for the dashboard.

**Output structure (same as n8n Analytics API):**
```json
{
  "summary": {
    "total_events": 29,
    "recovered_count": 8,
    "pending_count": 15,
    "exhausted_count": 4,
    "no_action_count": 2,
    "recovery_rate_percent": 27.6,
    "total_amount": 272000,
    "recovered_amount": 85000,
    "pending_amount": 150000,
    "avg_attempts_to_recover": 1.8,
    "avg_recovery_time_hours": 4.2
  },
  "ai_lift": {
    "baseline_rate_percent": 17.5,
    "ai_recovery_rate_percent": 27.6,
    "improvement_points": 10.1,
    "lift_multiplier": 1.58,
    "additional_revenue_recovered": 25000,
    "baseline_source": "Razorpay blog: 15-20% recovery via simple retries"
  },
  "by_event_type": { ... },
  "by_channel": { ... },
  "channel_ranking": [ ... ],
  "by_failure_category": { ... },
  "generated_at": "2026-08-26T10:00:00Z"
}
```

**Caching:** Redis cache with 30-second TTL (dashboard polls every 10s but analytics query is expensive)

### 9. React Frontend (Dashboard)

**One page. Not a feature showcase. A recovery engine control panel.**

#### Layout (top to bottom):

**Header bar:**
- "Recovery Router" title + "Razorpay AI Buildathon" badge
- Connection status indicator (realtime connected / disconnected)
- Last updated timestamp

**Stat tiles row (3 big numbers):**
- **Revenue at Risk** — sum of all event amounts (red-tinted)
- **Revenue Recovered** — sum of recovered amounts (green-tinted)
- **Recovery Rate** — recovered/total as percentage (with trend arrow)

**AI Lift comparison card:**
- Side-by-side: "Razorpay Baseline: 17.5%" vs "Recovery Router: X%"
- Improvement: "+Y percentage points"
- Additional revenue recovered: "₹Z more than baseline"

**Live event feed (realtime via Supabase):**
- Scrolling list of events
- Each row shows: timestamp, amount, leak type badge, failure category, action taken, channel, outcome (pending/recovered/exhausted)
- New events animate in from the top
- Color-coded by status: green (recovered), yellow (pending), red (exhausted), gray (no action)

**Recovery by type (3 mini-cards):**
- Payment Failures: count, amount, recovery rate
- Cart Abandonment: count, amount, recovery rate
- Invoice Overdue: count, amount, recovery rate

**Channel effectiveness (horizontal bar chart or ranking):**
- WhatsApp: X% recovery rate, Y events
- Email: X% recovery rate, Y events
- SMS: X% recovery rate, Y events

**Simulator panel (bottom — for demo):**
- Dropdown: event type (payment_failure / cart_abandonment / invoice_overdue)
- Dropdown: scenario preset (UPI Timeout, Card Expired, Fraud, High-Value Cart, etc.)
- "Send Test Event" button
- Shows the event flowing through the system in real-time on the feed above

#### Frontend tech:
- Vite + React 18
- Tailwind CSS (utility-first, responsive)
- `@supabase/supabase-js` for realtime subscriptions
- `fetch` for API calls (no axios needed)
- Responsive: works on mobile (judges may view on phone)
- Dark/light mode support

---

## Database Schema (Existing — May Need Updates)

### recovery_events (PRIMARY TABLE)
```sql
CREATE TABLE IF NOT EXISTS recovery_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Event data
  event_type TEXT NOT NULL,  -- payment_failure | cart_abandonment | invoice_overdue
  payment_id TEXT,
  order_id TEXT,
  invoice_id TEXT,
  amount DECIMAL NOT NULL,
  currency TEXT DEFAULT 'INR',
  method TEXT,
  error_code TEXT,
  error_description TEXT,
  customer_email TEXT,
  customer_phone TEXT,
  customer_name TEXT,
  cart_value DECIMAL,
  items_in_cart INTEGER,
  days_overdue INTEGER,
  
  -- AI classification
  leak_type TEXT,
  failure_category TEXT,
  recovery_probability FLOAT,
  recommended_action TEXT,
  recommended_channel TEXT,
  recommended_timing TEXT,
  reasoning TEXT,
  alternative_action TEXT,
  skip_reason TEXT,
  
  -- Status tracking
  status TEXT DEFAULT 'pending',  -- pending | recovered | exhausted | no_action_needed
  recovered_at TIMESTAMPTZ,
  recovered_amount DECIMAL,
  
  -- Agent state (escalation loop)
  attempt_count INTEGER DEFAULT 0,
  last_attempt_at TIMESTAMPTZ,
  max_attempts INTEGER DEFAULT 5,
  current_strategy TEXT DEFAULT 'initial',
  next_action_at TIMESTAMPTZ,
  opted_out BOOLEAN DEFAULT false,
  recovery_window_ends TIMESTAMPTZ,  -- created_at + 72h
  escalation_level INTEGER DEFAULT 0,
  
  -- Metadata
  source TEXT DEFAULT 'api',  -- api | n8n | simulator
  razorpay_raw BOOLEAN DEFAULT false,
  fallback_classification BOOLEAN DEFAULT false,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_recovery_events_status ON recovery_events(status);
CREATE INDEX IF NOT EXISTS idx_recovery_events_next_action ON recovery_events(status, next_action_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_recovery_events_order_id ON recovery_events(order_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_recovery_events_payment_id ON recovery_events(payment_id);

-- Enable realtime for frontend
ALTER PUBLICATION supabase_realtime ADD TABLE recovery_events;
```

### recovery_attempts (AGENT MEMORY)
```sql
CREATE TABLE IF NOT EXISTS recovery_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recovery_event_id UUID REFERENCES recovery_events(id),
  attempt_number INTEGER NOT NULL,
  channel_used TEXT,  -- whatsapp | email | sms | none
  action_taken TEXT,
  message_content TEXT,
  message_id TEXT,  -- Twilio SID or Resend ID
  sent_at TIMESTAMPTZ DEFAULT now(),
  outcome TEXT DEFAULT 'sent',  -- sent | delivered | failed | responded
  response_received_at TIMESTAMPTZ,
  notes TEXT,
  metadata JSONB DEFAULT '{}',  -- payment_link_id, payment_link_url, escalation_level
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recovery_attempts_event ON recovery_attempts(recovery_event_id);

-- Enable realtime
ALTER PUBLICATION supabase_realtime ADD TABLE recovery_attempts;
```

### pending_captures (NEW — handles race condition)
```sql
CREATE TABLE IF NOT EXISTS pending_captures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id TEXT NOT NULL,
  order_id TEXT,
  amount DECIMAL,
  method TEXT,
  captured_at TIMESTAMPTZ,
  matched BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Edge Cases & Error Handling

### Webhook Edge Cases
1. **Duplicate webhooks** — Razorpay may send the same webhook multiple times → Redis dedup with `{payment_id}` key, 1h TTL
2. **Out-of-order webhooks** — `payment.captured` arrives before `payment.failed` → store in `pending_captures`, match later
3. **Missing fields** — Normalize with null-safe defaults (amount=0, currency='INR', customer_name='Unknown')
4. **Raw Razorpay payload** — Detect `body.event === 'payment.failed'` and extract from nested structure
5. **Extremely large payloads** — Limit request body to 1MB
6. **Invalid event_type** — Return 400 with allowed values

### AI Classification Edge Cases
7. **OpenAI API down** — Fallback to rule-based classification using error_code mapping
8. **AI returns invalid JSON** — Retry once, then use fallback classification
9. **AI returns unknown failure_category** — Map to closest known category, flag as `classification_uncertain`
10. **AI returns recovery_probability outside 0-1** — Clamp to [0, 1]
11. **Classification takes >10 seconds** — Timeout, use fallback
12. **Token limit exceeded** — Truncate event data, retry

### Message Sending Edge Cases
13. **Customer has no phone** — Skip WhatsApp/SMS, try email only
14. **Customer has no email** — Skip email, try SMS only
15. **No contact info at all** — Log as `uncontactable`, status='exhausted'
16. **Twilio trial: unverified number** — Error logged, mark attempt as failed, try email
17. **Invalid phone format** — Normalize phone (add +91 if missing country code)
18. **Email bounced** — Mark attempt outcome as 'failed'
19. **Rate limit hit on messaging API** — Queue with exponential backoff

### Payment Link Edge Cases
20. **Razorpay payment link API fails** — Use fallback generic URL
21. **Amount is 0 or negative** — Skip payment link, log error
22. **Currency not INR** — Still create link (Razorpay supports multi-currency)

### Escalation Edge Cases
23. **Event recovered between fetch and send** — Re-check status before sending
24. **All channels failed for an event** — Mark as `delivery_failed`, retry in next cycle
25. **Recovery window expired during processing** — Check before each action
26. **Customer opted out** — Skip immediately, respect preference
27. **Max attempts reached** — Mark as 'exhausted', stop trying

### Concurrency Edge Cases
28. **Two escalation runs overlap** — Redis distributed lock prevents this
29. **Webhook + escalation try to update same event** — Supabase handles with row-level locking
30. **Multiple payment.captured for same order** — Only first one matches (status changes from pending)

---

## Rate Limiting Strategy

### External API Rate Limits

| API | Limit | Our Throttle | Implementation |
|-----|-------|-------------|----------------|
| Razorpay (test mode) | 25 req/sec | 10 req/sec | Redis sliding window counter |
| OpenAI GPT-5 Mini | Varies by tier | 50 req/min | Redis token bucket |
| Twilio (trial) | 1 msg/sec, verified numbers only | 1 msg/2sec | Redis per-number cooldown |
| Resend | 100 emails/day (free), 2/sec | 1/sec | Redis counter |
| SendGrid | 100 emails/day (free) | 1/sec | Redis counter |

### Internal Rate Limits

| Endpoint | Limit | Why |
|----------|-------|-----|
| POST /webhook/recovery-router | 100 req/min | Prevent abuse |
| POST /webhook/recovery-tracker | 100 req/min | Prevent abuse |
| GET /api/analytics | 30 req/min | Expensive query |
| POST /api/simulate | 10 req/min | Prevent test spam |

### Implementation
- Upstash Redis sliding window counters
- Return 429 Too Many Requests with `Retry-After` header
- Rate limits are per-IP for API endpoints, per-resource for external APIs

---

## Upstash Redis Usage

Upstash Redis serves two roles: **Celery broker/backend** (task queue) and **direct Redis** (rate limiting, dedup, caching, locks).

### 1. Celery Broker + Result Backend
Celery connects to Upstash via `rediss://` (SSL). See "Celery + Upstash Redis Configuration" section above. Tasks are dispatched with `.delay()` and executed by Celery workers. No custom queue management needed — Celery handles ACK/NACK, retries, and crash recovery.

### 2. Rate Limiting
Sliding window counters:
```python
key = f"ratelimit:{api}:{window}"
count = await redis.incr(key)
if count == 1:
    await redis.expire(key, window_seconds)
```

### 3. Deduplication
Idempotency keys with TTL:
```python
key = f"dedup:{payment_id}"
if await redis.set(key, "1", nx=True, ex=3600):
    # New event, process it
else:
    # Duplicate, skip
```

### 4. Distributed Locks
For escalation agent:
```python
lock = f"lock:escalation"
if await redis.set(lock, "1", nx=True, ex=240):
    try:
        await run_escalation()
    finally:
        await redis.delete(lock)
```

### 5. Caching
Analytics response cache:
```python
cached = await redis.get("cache:analytics")
if cached:
    return json.loads(cached)
# ... compute ...
await redis.set("cache:analytics", json.dumps(result), ex=30)
```

---

## Celery Tasks & Beat Schedule

Three Railway services — `web` (FastAPI), `worker` (Celery), `beat` (periodic scheduler) — all connect to Upstash Redis.

### Celery Tasks (tasks/)

#### `process_recovery_event` — The Merged Pipeline
```python
@celery_app.task(bind=True, max_retries=3, acks_late=True)
def process_recovery_event(self, event_data: dict):
    """Single atomic task: Classify → Route → Generate Link → Send → Log"""
    # 1. AI classify (OpenAI GPT-5 Mini structured output)
    classification = classify_event(event_data)
    # 2. Log event + classification to Supabase
    event_id = save_to_supabase(event_data, classification)
    # 3. Route action (deterministic)
    action = route_action(classification)
    if action.action == "no_action":
        return {"status": "no_action", "event_id": event_id}
    # 4. Generate Razorpay payment link (with expire_by)
    payment_link = generate_payment_link(event_data, event_id)
    # 5. Send message (WhatsApp/Email/SMS)
    result = send_message(action.channel, event_data, payment_link)
    # 6. Log attempt to recovery_attempts
    log_attempt(event_id, action, result, payment_link)
    return {"status": "sent", "event_id": event_id, "channel": action.channel}
```

#### `run_escalation_cycle` — Periodic (every 5 min via Beat)
```python
@celery_app.task
def run_escalation_cycle():
    """Fetch due events, AI decides next action, send concurrently."""
    events = fetch_pending_events(limit=20)  # next_action_at <= now
    actionable = filter_actionable(events)   # skip opted_out, expired, maxed
    if not actionable:
        return {"processed": 0}
    # Concurrent OpenAI calls via asyncio.gather()
    decisions = run_concurrent_ai_decisions(actionable)
    for event, decision in zip(actionable, decisions):
        link = generate_payment_link(event)
        send_message(decision.channel, event, link)
        log_attempt_and_update_state(event, decision, link)
    return {"processed": len(actionable)}
```

#### `scan_overdue_invoices` — Periodic (every 6h via Beat)
```python
@celery_app.task
def scan_overdue_invoices():
    """Poll Razorpay for overdue invoices, feed into pipeline."""
    invoices = fetch_razorpay_invoices()  # GET /v1/invoices?status=issued
    for inv in invoices:
        if not already_tracked(inv["id"]):
            event_data = normalize_invoice(inv)
            process_recovery_event.delay(event_data)
    return {"scanned": len(invoices)}
```

### Beat Schedule Configuration
```python
celery_app.conf.beat_schedule = {
    "escalation-every-5min": {
        "task": "app.tasks.escalation.run_escalation_cycle",
        "schedule": 300.0,  # 5 minutes
    },
    "invoice-scan-every-6h": {
        "task": "app.tasks.invoice_scan.scan_overdue_invoices",
        "schedule": 21600.0,  # 6 hours
    },
}
```

---

## Environment Variables

```env
# See backend/.env.example for all required variables
# Copy backend/.env.example to backend/.env and fill in your credentials
# NEVER commit real credentials to git
```

---

## Build Order (What to Build First)

### Phase 1: Backend Core (Day 1-2)
1. Project scaffold (FastAPI + Celery + requirements.txt + config)
2. Celery app configuration (`celery_app.py` — Upstash Redis broker with SSL)
3. Supabase client + database helpers
4. Redis client (direct — for rate limiting, dedup, caching, locks)
5. Pydantic models (all request/response schemas)
6. Normalizer (handle both raw Razorpay and custom format)
7. Deduplication logic (Redis SET NX with TTL)
8. Webhook endpoint: POST /webhook/recovery-router (receive → normalize → `process_recovery_event.delay()`)

### Phase 2: Classification + Routing (Day 2-3)
9. OpenAI classifier service (structured output with Pydantic model)
10. Fallback rule-based classifier (error_code mapping)
11. Action router (deterministic channel routing)
12. Celery task: `process_recovery_event` (merged pipeline: classify → route → link → send → log)
13. Rate limiter for OpenAI (Redis sliding window)

### Phase 3: Message Delivery (Day 3-4)
14. Razorpay payment link generator (with `expire_by` matching recovery window)
15. Resend email sender (with HTML template)
16. Twilio WhatsApp/SMS sender
17. SendGrid fallback email sender
18. Per-channel rate limiting (Redis per-number/per-email cooldowns)

### Phase 4: Escalation + Scanner (Day 4-5)
19. Escalation agent service (AI decision + concurrent `asyncio.gather()`)
20. Celery task: `run_escalation_cycle` (Beat schedule: every 5 min)
21. Invoice overdue scanner (Razorpay API polling)
22. Celery task: `scan_overdue_invoices` (Beat schedule: every 6h)
23. Recovery tracker webhook: POST /webhook/recovery-tracker (with ghost recovery fix: `attempt_count > 0`)

### Phase 5: Analytics + API (Day 5)
24. Analytics computation service
25. GET /api/analytics endpoint (with Redis caching, 30s TTL)
26. GET /api/events endpoint (paginated, filterable)
27. POST /api/simulate endpoint (test event generator)
28. GET /api/health endpoint

### Phase 6: React Frontend (Day 6-7)
29. Project scaffold (Vite + React + Tailwind CSS v4)
30. Supabase realtime client setup
31. StatTiles component (3 big numbers)
32. LiveFeed component (realtime event stream)
33. RecoveryByType component (3 mini-cards)
34. ChannelRanking component
35. AILift component (baseline comparison)
36. SimulatorPanel component (test event generator)
37. Responsive layout + dark/light mode

### Phase 7: Deploy + Test (Day 7-8)
38. Railway deployment: 3 services (web, worker, beat) + frontend
39. Environment variables configuration on Railway
40. End-to-end testing (webhook → Celery task → classify → send → track)
41. Generate 100+ test events via simulator
42. Verify analytics data + AI Lift metrics
43. Configure Razorpay webhook (payment.captured → recovery-tracker)

### Phase 8: Polish + Submit (Day 8-9)
44. README with architecture diagram
45. API documentation
46. Test data generator script
47. GitHub repo cleanup
48. Record 5-minute pitch video
49. Submit via Google Form

---

## Design Principles (From Our Strategy)

1. **One rupee recovered > ten features built** — Every component must directly recover revenue or measure recovery
2. **Think like Razorpay, not like a hackathon participant** — Would a Razorpay PM approve this for production?
3. **Smarter than doing nothing** — Know when NOT to act. Skipping unrecoverable events is a feature.
4. **Measurable or it didn't happen** — Recovery rate by failure type. False positive rate. Every claim backed by a number.
5. **Honest about what doesn't work** — Surface limitations. Quantify them. Judges reward this.
6. **One engine, not three products** — Three input types, one classify → route → act → measure pipeline
7. **Complement Razorpay, don't compete** — "Vulcan prevents failures. Recovery Router handles the ones that still happen."
8. **Ship beats perfect** — Working system with honest metrics beats polished system that's half-built

---

## NEVER Rules

- NEVER build a feature without answering: "How much revenue does this recover?"
- NEVER show a metric without showing how it was measured
- NEVER hide a limitation — surface it, quantify it, explain why
- NEVER duplicate what Razorpay already does well (Vulcan routing, at-checkout retry)
- NEVER send a recovery action without the system having a reason it chose THAT action
- NEVER treat all failures the same — differentiated treatment IS our value proposition
- ALWAYS ask: "Would a Razorpay PM ship this?" If no, cut it
- ALWAYS ask: "Is this one engine or am I building a second product?" If second, merge or cut

---

## Known Limitations (We Surface These Honestly)

1. **Twilio trial account** — WhatsApp/SMS only to verified numbers. In production: upgrade account or use WhatsApp Business API directly.
2. **Simulated data** — Metrics come from synthetic events. Real-world recovery rates will differ. Test methodology stated transparently.
3. **Classification accuracy depends on LLM** — We report classification accuracy alongside recovery rates.
4. **Recovery attribution is imperfect** — Customer pays 3 days after WhatsApp — did our message cause it? Acknowledge correlation-vs-causation gap.
5. **Single-merchant scope** — No multi-tenant isolation. Scale path: add tenant_id column, per-merchant configuration.
6. **n8n throughput limits** — For Razorpay-scale (millions), logic moves to async workers (which is what this code version IS).
7. **No A/B testing** — Can't prove channel X beats channel Y without controlled experiments. Future improvement.
8. **WhatsApp Business templates** — Need Meta approval for production. Using Twilio sandbox for demo.

---

## The 5-Minute Pitch Structure

- **0:00-0:30** — The problem (Razorpay's own numbers: 25% failure, 70% never return, 80% unrecovered)
- **0:30-1:00** — The insight ("Vulcan routes payments. I route failures.")
- **1:00-2:30** — Live demo (3 different events → 3 different intelligent routing decisions on the dashboard)
- **2:30-3:30** — Architecture (system diagram, classification example, routing logic)
- **3:30-4:15** — Results (recovery rates by type, total recovered, actions skipped, AI lift over baseline)
- **4:15-5:00** — Limitations and scale path (honest, quantified)

---

## What's NOT In This Build

- No merchant onboarding flow
- No settings/configuration UI
- No historical analytics charts
- No user authentication
- No multi-tenant isolation
- No chatbot or RAG advisor
- No retry-at-checkout (Razorpay already does this)
- No reconciliation
- No payment plan negotiation
- No A/B testing framework

Every one of those is a feature. None of them recover revenue. They're cut.

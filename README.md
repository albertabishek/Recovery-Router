# Recovery Router

**AI-powered revenue recovery engine for Razorpay merchants**

Recovery Router classifies revenue leaks across payment failures, cart abandonment, and overdue invoices — then routes each to the optimal recovery action via the best channel at the right time, with AI-personalized messages and intelligent multi-attempt escalation.

Built for **Razorpay AI Buildathon 2026 — Track 3** (Revenue Recovery).

**Live:** [app.albertabishek.com](https://app.albertabishek.com) | **API:** [api.albertabishek.com](https://api.albertabishek.com/docs)

---

## The Problem

Indian merchants on Razorpay lose revenue from three separate holes:

| Leak | Scale | Current Fix |
|------|-------|-------------|
| Payment Failures | 20-25% of all payments fail on Indian gateways | Same payment link sent to everyone, regardless of failure reason |
| Cart Abandonment | 70% of customers never return | No automated recovery |
| Overdue Invoices | Unpaid invoices pile up | Manual follow-up |

**80% of recoverable revenue is left on the table** because current approaches are unintelligent — no classification, no channel optimization, no timing intelligence.

## The Solution

Recovery Router is a single engine that:

1. **Classifies** each event using a 3-model AI chain (Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini) via OpenRouter, with rule-based fallback, into 12 failure categories
2. **Routes** to the optimal recovery action (send now / delay / no action) with dynamic attempt budgets based on amount, probability, and failure type
3. **Generates** a Razorpay payment link via Orders API + hosted checkout with server-side PII protection
4. **Sends** AI-personalized recovery messages through the best channel with multi-provider fallback chains
5. **Escalates** unrecovered events with AI-driven channel rotation, quiet hours enforcement, and race-safe state management
6. **Tracks** organic vs. AI-driven recoveries with reconciliation checks (currency match, amount tolerance, double-attribution prevention)

### AI Classification Categories

| Category | Recovery Probability | Channel | Timing | Max Attempts |
|----------|---------------------|---------|--------|-------------|
| UPI Timeout | 75-85% | WhatsApp | Immediate | 3-5 |
| Bank Downtime | 70-85% | WhatsApp | 30 min delay | 3-5 |
| Gateway Error | 80-90% | WhatsApp | 5 min | 3-5 |
| Card Expired | 40-60% | Email | Immediate | 3-4 |
| Insufficient Funds | 30-50% | SMS | 4 hour delay | 3 |
| User Cancelled | 20-40% | WhatsApp | 1 hour | 2 |
| Unrecoverable Decline | 0% | None | — | 0 |
| High Intent Abandonment | 30-50% | WhatsApp | 1 hour | 3 |
| Browse Only Abandonment | 5-10% | None | — | 0 |
| Recently Overdue (1-7d) | 60-80% | WhatsApp | Immediate | 3-5 |
| Moderately Overdue (8-30d) | 30-50% | Email | Immediate | 3-4 |
| Long Overdue (30d+) | 10-20% | Email | — | 2 |

Max attempts are computed dynamically: `compute_max_attempts(amount, recovery_probability, failure_category)`.

---

## Architecture

```
                    ┌──────────────┐
                    │   Razorpay   │
                    │   Webhooks   │
                    └──────┬───────┘
                           │ HMAC-SHA256 verified
              ┌────────────▼────────────┐
              │   Recovery Router API   │
              │      (FastAPI)          │
              ├─────────────────────────┤
              │  /webhook/recovery-     │ ← Ingest failures, abandonment, invoices
              │    router               │   Dedup (Redis + DB unique indexes)
              │  /webhook/recovery-     │ ← payment.captured / payment_link.paid
              │    tracker              │   Reconciliation + attribution
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │   Celery +   │
                    │    Redis     │
                    │   (Broker)   │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌────────────────┐
│ process_recovery│ │ escalation   │ │ invoice_scan   │
│ _event          │ │ _cycle       │ │ (every 6h)     │
│ (single atomic  │ │ (every 5min) │ │ Razorpay API   │
│  Celery task)   │ │ AI-driven    │ │ polling        │
├─────────────────┤ │ re-escalate  │ └────────────────┘
│ 1. Classify(AI) │ │ with channel │
│ 2. Route action │ │ rotation     │
│ 3. Gen pay link │ └──────────────┘
│ 4. AI message   │
│ 5. Send message │
│ 6. Log attempt  │
└────────┬────────┘
         │
    ┌────┼────────────────┐
    ▼    ▼                ▼
┌────────┐ ┌──────┐ ┌────────┐
│WhatsApp│ │ SMS  │ │ Email  │
│Green → │ │Twilio│ │ Resend │
│Twilio →│ │  →WA │ │  (AI   │
│Email   │ │  →Em │ │  HTML) │
└────────┘ └──────┘ └────────┘
```

### Provider Fallback Chains

```
WhatsApp: Green API (personalized text) → Twilio WhatsApp (template) → Email
SMS:      Twilio SMS → Green API WhatsApp → Twilio WhatsApp → Email
Email:    Resend (AI-personalized HTML with branded template)
```

Every provider attempt is logged in the `degradation_path` array for full audit trail visibility.

### Escalation Engine

The escalation engine runs every 5 minutes via Celery Beat and processes pending events whose `next_action_at` has passed:

1. **AI decision** — Analyzes full attempt history (channels used, outcomes, blocked/failed channels) and decides: send on which channel with what tone, or give up
2. **Safety overrides** — Three layers prevent premature give-up:
   - Schema default: action defaults to "send"
   - AI override: checks for untried channels before allowing give-up
   - Hard guard: blocks give-up when `attempt_count < max_attempts`, forces channel switch
3. **Quiet hours** — No messages between 9 PM and 9 AM IST; reschedules to 9 AM next day
4. **Category-specific delays** — Retry intervals match the failure type:
   - 1h: UPI timeout, gateway error
   - 2h: bank downtime, high intent abandonment
   - 6h: card expired
   - 8h: insufficient funds
   - 12h: user cancelled
   - 24-48h: overdue invoices

### Payment Link Generation

- Uses **Razorpay Orders API** (not Payment Links API) to avoid the 30-link test-mode limit
- Customer PII (name, email, phone) stored server-side in Redis with a 24h-TTL token
- Checkout URL: `{API_BASE_URL}/pay/{order_id}?t={token}` — PII never appears in the URL
- If payment link creation fails, outreach is blocked and rescheduled (no homepage links sent to customers)

### Recovery Reconciliation

When a `payment.captured` or `payment_link.paid` webhook arrives:

1. **Multi-strategy matching**: `notes.recovery_event_id` → `reference_id` → `order_id` → `payment_id`
2. **Validation checks**: entity status must be "captured", currency must match, amount within 1% tolerance
3. **Double-attribution prevention**: `recovered_payment_id` unique column prevents the same payment from being credited to multiple events
4. **Ghost recovery prevention**: events with `attempt_count == 0` are marked `organic_recovery`, not `recovered` — AI lift metrics only count events where outreach was actually sent

---

## Tech Stack

### Backend
- **FastAPI** — API server with Swagger docs at `/docs`
- **Celery** — Distributed task queue (acks_late, prefetch=1, reject_on_worker_lost)
- **Redis** — Message broker, caching, dedup, rate limiting, distributed locks
- **Supabase** — PostgreSQL database with Realtime subscriptions
- **OpenRouter** — AI gateway: Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini fallback chain
- **Razorpay Orders API** — Payment link generation + hosted checkout
- **Green API** — WhatsApp messaging (personalized text)
- **Twilio** — WhatsApp (template) + SMS
- **Resend** — Email delivery with AI-personalized HTML

### Frontend
- **React 19** — UI framework
- **Vite 8** — Build tool with HMR
- **TailwindCSS 4** — Utility-first styling
- **Supabase Realtime** — Live event updates via WebSocket

### Infrastructure
- **Cloudflare Tunnel** — Public HTTPS access (app.albertabishek.com, api.albertabishek.com)
- **Server-side pagination** — Supabase `.range()` with `count="exact"` for all list endpoints
- **Windows service scripts** — `start.bat` / `stop.bat` for local development

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Redis (local or Upstash)

### 1. Clone and install

```bash
git clone <repo-url>
cd Razorpay_buildathon
```

**Backend:**
```bash
cd backend
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### 2. Database setup

Run the migration SQL files in order in the Supabase SQL Editor:

1. `backend/migrations/001_initial_schema.sql` — Creates `recovery_events` and `recovery_attempts` tables
2. `backend/migrations/002_reset_sequences_function.sql` — Reset sequences function
3. `backend/migrations/003_durable_idempotency.sql` — Unique indexes for dedup + `recovered_payment_id` column

### 3. Environment variables

Copy the example files and fill in your credentials:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

**Backend `.env` requires:**

| Variable | Source |
|----------|--------|
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Razorpay Dashboard → Settings → API Keys |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay Dashboard → Webhooks → Secret |
| `OPENROUTER_API_KEY` | openrouter.ai → API Keys |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_ANON_KEY` | Supabase → Project Settings → API |
| `REDIS_URL` | Redis connection string (e.g., `rediss://...` for Upstash) |
| `GREEN_API_INSTANCE_ID` / `GREEN_API_TOKEN` | green-api.com → Instance Settings |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Twilio Console |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | Resend Dashboard → API Keys |
| `API_BASE_URL` / `FRONTEND_URL` | Your deployed URLs |
| `APP_PASSWORD` | Dashboard login password (your choice) |
| `TEST_CUSTOMER_EMAIL` / `TEST_CUSTOMER_PHONE` | Default simulator customer details |

**Frontend `.env` requires:**

| Variable | Source |
|----------|--------|
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | Supabase → Project Settings → API |
| `VITE_API_BASE` | Backend URL (empty for local dev — Vite proxies to localhost:8000) |

### 4. Razorpay webhook setup

In the Razorpay Dashboard → Webhooks, create two webhooks pointing to your API:

| Webhook URL | Events |
|-------------|--------|
| `https://your-api.com/webhook/recovery-router` | `payment.failed` |
| `https://your-api.com/webhook/recovery-tracker` | `payment.captured`, `payment_link.paid` |

### 5. Run locally

**Option A — Using start script (Windows):**
```bash
start.bat
```
This launches Redis, Celery Worker, Celery Beat, and Uvicorn in separate windows.

**Option B — Manual (any OS):**

```bash
# Terminal 1 — API server
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Celery worker
cd backend
celery -A app.celery_app worker --loglevel=info --pool=solo --concurrency=1

# Terminal 3 — Celery beat (scheduled tasks)
cd backend
celery -A app.celery_app beat --loglevel=info

# Terminal 4 — Frontend
cd frontend
npm run dev
```

Open http://localhost:5173 for the dashboard.

To stop services (Windows): `stop.bat` — kills Celery and Uvicorn, leaves Redis running.

---

## API Endpoints

### Public (no auth)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | API info (name, version, docs link) |
| `GET` | `/docs` | Swagger UI (interactive API docs) |
| `GET` | `/api/health` | Service health check — Redis, Celery workers, Supabase, queue depth |
| `POST` | `/api/login` | Password login, returns auth token |
| `GET` | `/pay/{order_id}?t={token}` | Hosted checkout page — opens Razorpay payment modal |

### Webhooks (HMAC-SHA256 signature verified)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/webhook/recovery-router` | Ingest payment failures, cart abandonment, invoice overdue events |
| `POST` | `/webhook/recovery-tracker` | Mark events as recovered on `payment.captured` / `payment_link.paid` |

### Dashboard API (auth required)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/events` | List events — filters: status, event_type, date range, limit, offset |
| `GET` | `/api/events/counts` | Event counts by status |
| `GET` | `/api/events/{id}/trace` | Full event trace — event data + all attempts + timeline |
| `PATCH` | `/api/events/{id}/control` | Pause / resume / cancel recovery for an event |
| `GET` | `/api/analytics` | Aggregate analytics with date range filtering (cached 120s) |
| `GET` | `/api/audit-logs` | Recovery attempts audit trail — filters: event_id, date range |
| `POST` | `/api/simulate` | Fire test scenarios (10 built-in scenarios) |
| `POST` | `/api/live-checkout` | Create a Razorpay test-mode order for live payment testing |

### Webhook Payload (recovery-router)

```json
{
  "event_type": "payment_failure",
  "payment_id": "pay_abc123",
  "order_id": "order_xyz789",
  "amount": 1499,
  "currency": "INR",
  "method": "upi",
  "error_code": "TIMEOUT",
  "error_description": "UPI payment timed out",
  "customer_email": "customer@example.com",
  "customer_phone": "+919876543210",
  "customer_name": "Rahul Sharma"
}
```

Supported `event_type` values: `payment_failure`, `cart_abandonment`, `invoice_overdue`

Also accepts raw Razorpay `payment.failed` webhook payloads directly — they are normalized automatically.

### Merchant Integration (Cart Abandonment)

Razorpay does not send cart abandonment webhooks. Merchants POST from their backend:

```javascript
fetch('https://api.albertabishek.com/webhook/recovery-router', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    event_type: 'cart_abandonment',
    amount: 2999,
    cart_value: 2999,
    items_in_cart: 3,
    customer_email: 'customer@example.com',
    customer_phone: '+919876543210',
    customer_name: 'Customer Name'
  })
});
```

---

## Security

- **HMAC-SHA256 webhook verification** — validates `X-Razorpay-Signature` header on both webhook endpoints
- **XSS prevention** — regex `^order_[A-Za-z0-9]{8,30}$` validation on checkout order_id, HTML escaping on all user inputs
- **AI input sanitization** — truncate fields to 200 chars max, strip control characters before AI calls
- **Two-level deduplication** — Redis (fast path, 1h TTL) + DB unique partial indexes (permanent, excludes TEST_ prefixes)
- **Rate limiting** — sliding window per-endpoint (Redis sorted sets): 100/min on webhooks, 10/min on simulator, 5/min on live checkout
- **Per-resource cooldown** — 5 min WhatsApp/SMS, 5 min email per customer phone/email to prevent spam
- **Race condition protection** — all database updates use conditional status filters (`.eq("status", "pending")`) to prevent interleaved writes from concurrent processes (Celery tasks, webhooks, API calls). Per-event Redis locks (300s TTL) serialize processing across escalation and delayed send tasks
- **Atomic state transitions** — `_update_event_state` checks if `new_attempt_count >= max_attempts` and atomically marks exhausted in a single write
- **CORS** — restricted to specific origins, methods (GET/POST/PATCH/OPTIONS/DELETE), and headers
- **SSL** — `CERT_REQUIRED` for all Redis connections
- **No hardcoded credentials** — all secrets via `.env`, `.gitignore` excludes `.env*`, `*.pem`, `*.key`
- **Server-side PII** — customer details stored in Redis with 24h-TTL token, never exposed in payment URLs
- **Ghost recovery prevention** — only counts recovered events where `attempt_count > 0`; organic recoveries tracked separately
- **Double-attribution prevention** — unique index on `recovered_payment_id` prevents the same payment from crediting multiple events
- **Reconciliation checks** — payment status must be "captured", currency must match, amount within 1% tolerance

---

## Testing

### Automated E2E tests (31 tests)

```bash
cd backend
python tests/e2e_test.py
```

Covers: webhooks (all event types, dedup, invalid payloads), events API (pagination, filters), analytics (response structure, caching), simulator (all 10 scenarios), checkout (XSS, path traversal, SQL injection), rate limiting, edge cases (unicode, large amounts, minimal payloads).

### Generate bulk test data

```bash
# Via API (requires Celery worker running)
cd backend
python tests/generate_test_data.py

# Direct processing (bypasses Celery — good for local testing)
python tests/generate_and_process.py
```

### Process queued tasks without a worker

```bash
cd backend
python tests/process_queue.py
```

---

## Scheduled Tasks (Celery Beat)

| Task | Schedule | What It Does |
|------|----------|-------------|
| Escalation Engine | Every 5 minutes | Fetches due events, runs AI escalation decision (send/give_up), rotates channels, enforces quiet hours, respects attempt budgets |
| Invoice Scanner | Every 6 hours | Polls Razorpay Invoices API for overdue invoices, dedup-checks, creates recovery events |

---

## Frontend Pages

| Page | Description |
|------|-------------|
| **Overview** | Revenue recovered hero stat, at-risk/pending/recovery rate cards, live event feed, channel ranking, recovery by type breakdown |
| **Recovery Events** | Filterable event list with status tabs (All / Pending / Recovered / Exhausted / No Action), event trace drill-down with full timeline, pause/resume/cancel controls |
| **Reports** | Analytics breakdown by event type, channel effectiveness ranking, failure category distribution, AI lift vs 17.5% industry baseline |
| **Simulator** | 10 built-in test scenarios across 3 event types, custom customer details, live Razorpay checkout testing (test mode) |
| **Audit Logs** | Full recovery attempt history with AI reasoning, provider degradation paths, delivery status |

### Frontend Features
- **Global date range filtering** — presets (Today, Yesterday, Last 7 Days, Last 30 Days, All Time) and custom range
- **Global loading bar** — animated progress bar during API calls, reference-counted for concurrent fetches
- **Supabase Realtime** — live event updates via WebSocket subscription
- **Auto-refresh** — dashboard data refreshes every 30 seconds
- **Responsive tables** — horizontal scroll on all data tables

---

## Project Structure

```
Razorpay_buildathon/
├── start.bat / stop.bat           # Windows service management
├── backend/
│   ├── .env.example               # Environment template
│   ├── requirements.txt
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_reset_sequences_function.sql
│   │   └── 003_durable_idempotency.sql
│   ├── app/
│   │   ├── main.py                # FastAPI app + CORS + routers
│   │   ├── config.py              # Settings from .env
│   │   ├── models.py              # Pydantic models
│   │   ├── database.py            # Supabase client (thread-safe singleton)
│   │   ├── redis_client.py        # Redis client (thread-safe singleton)
│   │   ├── celery_app.py          # Celery config + Beat schedule
│   │   ├── auth.py                # HMAC password auth
│   │   ├── routers/
│   │   │   ├── webhooks.py        # Webhook endpoints (HMAC verified)
│   │   │   ├── events.py          # Events API, simulator, audit logs, live checkout
│   │   │   ├── analytics.py       # Analytics with Redis caching
│   │   │   ├── health.py          # Health check (Redis + Celery + Supabase)
│   │   │   └── checkout.py        # Hosted checkout page (XSS-protected)
│   │   ├── services/
│   │   │   ├── ai_client.py       # OpenRouter 3-model fallback chain
│   │   │   ├── classifier.py      # AI classification + rule-based fallback
│   │   │   ├── router.py          # Action routing + dynamic max_attempts
│   │   │   ├── payment_links.py   # Razorpay Orders API + server-side PII
│   │   │   ├── messenger.py       # Multi-provider messaging with fallback chains
│   │   │   ├── message_generator.py # AI-personalized message content
│   │   │   ├── escalation.py      # AI escalation engine + quiet hours
│   │   │   ├── recovery_tracker.py # Reconciliation + ghost prevention
│   │   │   ├── analytics.py       # Analytics aggregation
│   │   │   └── invoice_scanner.py # Razorpay invoice polling
│   │   ├── tasks/
│   │   │   ├── recovery.py        # Main pipeline task + delayed send
│   │   │   ├── escalation.py      # Beat: escalation cycle (5 min)
│   │   │   └── invoice_scan.py    # Beat: invoice scan (6 hours)
│   │   └── utils/
│   │       ├── normalizer.py      # Razorpay webhook normalization
│   │       ├── dedup.py           # Redis deduplication (1h TTL)
│   │       ├── rate_limiter.py    # Sliding window + per-resource cooldown
│   │       └── templates.py       # Fallback message templates
│   └── tests/
│       ├── e2e_test.py            # 31 automated E2E tests
│       ├── test_api.py, test_errors.py, test_security.py
│       ├── test_pipeline.py, test_load.py
│       ├── generate_test_data.py  # Bulk test data
│       └── process_queue.py       # Manual queue processing
├── frontend/
│   ├── .env.example
│   ├── package.json, vite.config.js
│   └── src/
│       ├── App.jsx                # Auth gate + page routing + data loading
│       ├── main.jsx               # Entry point with LoadingProvider
│       ├── index.css              # TailwindCSS
│       ├── components/
│       │   ├── Layout.jsx         # Sidebar nav + header
│       │   ├── OverviewPage.jsx   # Dashboard overview
│       │   ├── EventsPage.jsx     # Events list + trace drill-down
│       │   ├── AnalyticsPage.jsx  # Reports/analytics
│       │   ├── SimulatorPage.jsx  # Test scenario simulator
│       │   ├── AuditLogsPage.jsx  # Audit trail
│       │   ├── AILift.jsx         # AI vs baseline comparison
│       │   ├── ChannelRanking.jsx # Channel effectiveness
│       │   ├── RecoveryByType.jsx # Recovery by type breakdown
│       │   ├── LiveFeed.jsx       # Real-time event feed
│       │   ├── HealthBadge.jsx    # Service health indicator
│       │   ├── DateRangePicker.jsx, LoadingBar.jsx, StatTiles.jsx
│       │   └── SimulatorPanel.jsx
│       └── lib/
│           ├── api.js             # API client with auth + loading hooks
│           └── supabase.js        # Supabase client for realtime
└── n8n_workflow/                   # Alternative n8n workflow implementations
    ├── Recovery Router.json
    ├── Escalation Agent.json
    ├── Recovery Tracker.json
    ├── Recovery Analytics API.json
    └── Invoice Overdue Scanner.json
```

---

## Key Design Decisions

1. **Single atomic Celery task** — Classify → Route → Payment Link → AI Message → Send → Log in one task, not a chain of queues. Simpler, no inter-step failures, with exponential backoff retry (60s → 120s → 240s).

2. **3-model AI chain via OpenRouter** — Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini with automatic fallback. Each model gets 1 retry with 0.5s backoff. If all AI fails, rule-based classification kicks in with 0.7x confidence penalty. The system never blocks on AI.

3. **Orders API over Payment Links** — Razorpay Payment Links API has a 30-link test limit. Orders API + hosted checkout is unlimited and gives us full control over the payment page with XSS-safe, regex-validated order IDs.

4. **Server-side PII protection** — Customer details are stored in Redis with a 24h-TTL token, referenced via the `t` query parameter. PII never appears in URLs that could be logged, cached, or shared.

5. **Ghost recovery prevention** — If Recovery Router sent no outreach (attempt_count == 0) but the customer pays organically, it's logged as `organic_recovery`, not `recovered`. AI Lift metrics only count events where outreach was actually delivered.

6. **Race-safe state management** — Every database update on `recovery_events` includes a conditional status filter (`.eq("status", "pending")`) so concurrent processes (webhooks, escalation cycles, delayed sends, API calls) can't create inconsistent states. Per-event Redis locks serialize processing within the escalation engine.

7. **Dynamic attempt budgets** — `max_attempts` is computed per event based on amount, recovery probability, and failure category. High-value, high-probability events get up to 5 attempts; user-cancelled gets 2; unrecoverable gets 0. The AI escalation engine respects this budget with hard guards that block premature give-up.

8. **Multi-provider fallback with full audit trail** — Each messaging attempt logs every provider tried, whether it succeeded or failed, and the error. The `degradation_path` array in every recovery attempt provides complete observability.

9. **AI-personalized messages** — Every recovery message (WhatsApp, SMS, email) is generated by AI based on failure category, amount, customer name, attempt number, and tone escalation (friendly → firm → urgent → final). Template fallback if AI is unavailable.

10. **Two-level deduplication** — Redis provides a fast-path dedup cache (1h TTL). DB-level unique partial indexes on `payment_id`, `order_id`, `invoice_id` (excluding `TEST_` prefixes) are the durable fallback that survives Redis restarts.

---

## Author

**Albert Abishek I**
Razorpay AI Buildathon 2026 — Track 3 (Revenue Recovery)

# Recovery Router

**Intelligent revenue recovery engine for Razorpay merchants**

Recovery Router classifies revenue leaks across payment failures, cart abandonment, and overdue invoices — then routes each to the optimal recovery action via the best channel at the right time, with AI-personalized messages.

Built for **Razorpay AI Buildathon — Track 3** (Revenue Recovery).

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

1. **Classifies** each event using a 3-model AI chain (Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini) via OpenRouter, with rule-based fallback, into 11 failure categories
2. **Routes** to the optimal recovery action (send now / delay / no action) with timing intelligence
3. **Generates** a Razorpay payment link via Orders API + hosted checkout
4. **Sends** AI-personalized recovery messages through the best channel with multi-provider fallback
5. **Escalates** unrecovered events with AI-driven channel rotation (up to 5 attempts)
6. **Tracks** organic vs. AI-driven recoveries to measure real impact (ghost recovery prevention)

### AI Classification Categories

| Category | Recovery Probability | Channel | Timing |
|----------|---------------------|---------|--------|
| UPI Timeout | 75-85% | WhatsApp | Immediate |
| Bank Downtime | 70-85% | WhatsApp | 30 min delay |
| Gateway Error | 80-90% | WhatsApp | 5 min |
| Card Expired | 40-60% | Email | Immediate |
| Insufficient Funds | 30-50% | SMS | 4 hour delay |
| Unrecoverable Decline | 0% | None | — |
| High Intent Abandonment | 30-50% | WhatsApp | 1 hour |
| Browse Only Abandonment | 5-10% | None | — |
| Recently Overdue (1-7d) | 60-80% | WhatsApp | Immediate |
| Moderately Overdue (8-30d) | 30-50% | Email | Immediate |
| Long Overdue (30d+) | 10-20% | Email | — |

---

## Architecture

```
                    ┌──────────────┐
                    │   Razorpay   │
                    │   Webhooks   │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │   Recovery Router API   │
              │      (FastAPI)          │
              ├─────────────────────────┤
              │  Webhook Endpoints      │
              │  • /webhook/recovery-   │
              │    router (ingest)      │
              │  • /webhook/recovery-   │
              │    tracker (mark paid)  │
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │    Celery    │
                    │    Queue     │
                    │  (Upstash    │
                    │   Redis)     │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │  process_recovery_event │
              │  (single atomic task)   │
              ├─────────────────────────┤
              │  1. Normalize payload   │
              │  2. Dedup check (Redis) │
              │  3. AI Classify         │
              │     (3-model chain)     │
              │  4. Route action        │
              │  5. Generate pay link   │
              │  6. AI-personalize msg  │
              │  7. Send message        │
              │  8. Log to Supabase     │
              └─────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │  WhatsApp   │ │    SMS      │ │   Email     │
   │ Green API → │ │ Twilio SMS  │ │   Resend    │
   │   Twilio    │ │ → Green API │ │             │
   │             │ │ → Twilio WA │ │             │
   └─────────────┘ └─────────────┘ └─────────────┘
```

### Provider Fallback Chains

```
WhatsApp: Green API (personalized text) → Twilio WhatsApp (template) → Email
SMS:      Twilio SMS → Green API WhatsApp → Twilio WhatsApp → Email
Email:    Resend (AI-personalized HTML)
```

Every provider attempt is logged in the `degradation_path` for full audit trail visibility.

---

## Tech Stack

### Backend
- **FastAPI** — API server with Swagger docs at `/docs`
- **Celery** — Distributed task queue with Redis broker (acks_late, prefetch=1)
- **Upstash Redis** — Message broker, caching, dedup, rate limiting (SSL CERT_REQUIRED)
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

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Redis (or Upstash Redis account)

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

### 2. Environment variables

Copy the example files and fill in your credentials:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

**Backend `.env` requires:**
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — Razorpay dashboard
- `RAZORPAY_WEBHOOK_SECRET` — Webhook secret from Razorpay dashboard
- `OPENROUTER_API_KEY` — OpenRouter.ai API key
- `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` — Supabase project settings
- `UPSTASH_REDIS_URL` — Upstash Redis connection string (rediss://)
- `GREEN_API_INSTANCE_ID` / `GREEN_API_TOKEN` — green-api.com
- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` — Twilio console
- `RESEND_API_KEY` / `RESEND_FROM_EMAIL` — Resend dashboard
- `FRONTEND_URL` / `API_BASE_URL` — Your deployed URLs

**Frontend `.env` requires:**
- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — Supabase project
- `VITE_API_BASE` — Backend API URL (e.g., `https://api.albertabishek.com`)

**SECURITY: Credentials must NEVER be committed to git. Use .env files only.**

### 3. Run locally

**Terminal 1 — API server:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Celery worker:**
```bash
cd backend
celery -A app.celery_app worker --loglevel=info --pool=solo
```

**Terminal 3 — Celery beat (scheduled tasks):**
```bash
cd backend
celery -A app.celery_app beat --loglevel=info
```

**Terminal 4 — Frontend:**
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 for the dashboard.

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | API info |
| `GET` | `/docs` | Swagger UI (interactive API docs) |
| `GET` | `/api/health` | Service health check (Supabase + Redis + Celery) |
| `GET` | `/api/events` | List recovery events (filters: status, event_type, from_date, to_date, limit, offset) |
| `GET` | `/api/events/{id}/trace` | Full event trace with all attempts and degradation paths |
| `GET` | `/api/analytics` | Aggregate analytics with date range filtering (from_date, to_date) |
| `GET` | `/api/audit-logs` | Recovery attempts audit trail (filters: event_id, from_date, to_date, limit, offset) |
| `POST` | `/api/simulate` | Fire test scenarios (10 built-in scenarios) |
| `POST` | `/webhook/recovery-router` | Ingest payment failure / cart abandonment / invoice overdue |
| `POST` | `/webhook/recovery-tracker` | Mark event as recovered (from Razorpay payment.captured) |
| `GET` | `/pay/{order_id}` | Hosted checkout page (XSS-protected, regex-validated order_id) |

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

### Merchant Integration (Cart Abandonment)

Razorpay does not send cart abandonment webhooks. Merchants POST from their frontend:

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
- **Deduplication** — Redis-based with payment_id/order_id/invoice_id + SHA256 hash fallback (1-hour TTL)
- **Rate limiting** — sliding window per-endpoint (Redis sorted sets): 100/min on webhooks, 10/min on simulator
- **Per-resource cooldown** — 5 min WhatsApp/SMS, 5 min email per customer phone/email
- **Race condition prevention** — optimistic concurrency with `.eq("status", "pending")` on all status updates
- **CORS** — restricted to specific origins, methods (GET/POST/OPTIONS), and headers (Content-Type/Authorization)
- **SSL** — `CERT_REQUIRED` for all Redis/Upstash connections
- **No hardcoded credentials** — all secrets via `.env`, `.gitignore` excludes `.env*`, `*.pem`, `*.key`
- **Ghost recovery prevention** — only counts recovered events where `attempt_count > 0`; organic recoveries tracked separately

See [SECURITY.md](SECURITY.md) for the full security model.

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
python tests/generate_test_data.py

# Direct processing (bypasses Celery — good for local testing)
python tests/generate_and_process.py
```

### Process queued tasks without a worker

```bash
python tests/process_queue.py
```

---

## Scheduled Tasks (Celery Beat)

| Task | Schedule | What It Does |
|------|----------|-------------|
| Invoice Scanner | Every 6 hours | Fetches overdue invoices from Razorpay API, dedup-checks, creates recovery events |
| Escalation Engine | Every 5 minutes | Re-classifies unrecovered events via AI, rotates channels, sends follow-ups (up to 5 attempts) |

---

## Frontend Pages

| Page | Description |
|------|-------------|
| **Overview** | Revenue recovered, at-risk amount, pending events, AI Lift vs Razorpay baseline, channel performance, recovery by type |
| **Recovery Events** | Full event list with filter tabs (All / Pending / Recovered / Exhausted / No Action), server-side pagination |
| **Reports** | Analytics breakdown by event type, channel, failure category |
| **Simulator** | 10 built-in test scenarios to fire through the full pipeline and see results |
| **Audit Logs** | Full recovery attempt history with degradation paths, paginated (30 per page) |

### Frontend Features
- **Global date range filtering** — presets (Today, Yesterday, Last 7 Days, Last 30 Days, All Time) and custom range, applied across Overview, Events, and Audit Logs
- **Global loading bar** — animated progress bar at top during all API calls, reference-counted for concurrent fetches
- **Supabase Realtime** — live event updates via WebSocket subscription
- **Responsive tables** — horizontal scroll on all data tables, no column crunching

---

## Project Structure

```
Razorpay_buildathon/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app + CORS
│   │   ├── config.py              # Settings from .env
│   │   ├── models.py              # Pydantic models (11 models)
│   │   ├── database.py            # Supabase client (thread-safe singleton)
│   │   ├── redis_client.py        # Redis client (thread-safe singleton)
│   │   ├── celery_app.py          # Celery config + beat schedule
│   │   ├── routers/
│   │   │   ├── webhooks.py        # Webhook endpoints with HMAC verification
│   │   │   ├── events.py          # Events API + simulator + audit logs
│   │   │   ├── analytics.py       # Analytics endpoint with date filtering
│   │   │   ├── health.py          # Health check (Supabase + Redis + Celery)
│   │   │   └── checkout.py        # Hosted checkout page (XSS-protected)
│   │   ├── services/
│   │   │   ├── ai_client.py       # OpenRouter client with 3-model fallback
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
│   └── .env.example
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
│   ├── vite.config.js
│   └── .env.example
├── AUDIT.md                       # Security audit (31 findings, all fixed)
├── SECURITY.md                    # Security model documentation
├── E2E_TEST_REPORT.md             # E2E test results
├── SYSTEM_DOCUMENTATION.md        # Complete system documentation
├── BUILD_PLAN.md                  # Build plan with critical fixes
├── VERIFY_LOG.md                  # Build verification log
└── README.md
```

---

## Key Design Decisions

1. **Single Celery task** — Classify → Route → Pay Link → Personalize → Send → Log in one atomic task, not a chain of queues. Simpler, no inter-step failures, with exponential backoff retry (60s, 120s, 240s).

2. **3-model AI chain** — OpenRouter routes through Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini with automatic fallback. If all AI fails, rule-based classification with 0.7x confidence penalty kicks in. Never blocks on AI.

3. **Orders API over Payment Links** — Razorpay Payment Links API has a 30-link test limit. Orders API + hosted checkout is unlimited and gives us XSS-safe payment pages with regex-validated order IDs.

4. **Ghost recovery prevention** — If AI decided "no action" but customer pays organically, we log it as `organic_recovery`, not `recovered`. AI Lift metrics only count events where `attempt_count > 0`.

5. **Multi-provider fallback with full audit trail** — Each messaging attempt logs every provider tried, whether it succeeded or failed, and the error. The `degradation_path` array in every recovery attempt provides complete observability for debugging and demo.

6. **AI-personalized messages** — Every recovery message (WhatsApp, SMS, email) is generated by AI based on failure category, amount, customer name, attempt number, and tone escalation. Template fallback if AI is unavailable.

---

## Author

**Albert Abishek I**
Razorpay AI Buildathon — Track 3 (Revenue Recovery)
Deadline: September 5, 2026

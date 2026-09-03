# Recovery Router -- Tech Stack Analysis

Built by **Albert Abishek I** for the Razorpay AI Buildathon 2026, Track 3 (Reduce Revenue Leaks).

---

## Stack Overview

| Layer | Technology | Version | Role |
|-------|-----------|---------|------|
| Language | Python | 3.11+ | Backend runtime (type hints, `X | None` union syntax throughout) |
| Web framework | FastAPI | >=0.141.1 | Async API server |
| Task queue | Celery | >=5.6.3 (with redis extra) | Background recovery tasks, periodic beats |
| Broker / cache | Redis | >=5.3.0 (client); managed instance on Railway | Celery broker, result backend, cache, rate limiter, dedup store, cooldown tracker, checkout-token store |
| Database | Supabase (PostgreSQL) | supabase-py >=2.31.0 | Persistent storage, RLS, REST API |
| Frontend framework | React | 19.2.8 | Dashboard SPA |
| Build tool | Vite | 8.2.2 | Dev server with HMR, production bundler |
| CSS | Tailwind CSS | 4.3.3 (via @tailwindcss/vite plugin) | Utility-first styling |
| AI gateway | OpenRouter | API v1 | Single endpoint for three LLM providers |
| Payments | Razorpay Orders API | v1 | Order creation, webhook verification, checkout |
| WhatsApp (primary) | Green API | HTTP REST | Personalized text messages |
| WhatsApp + SMS (fallback) | Twilio | twilio-py >=9.10.9 | Template WhatsApp via content_sid, SMS |
| Email | Resend | resend-py >=2.10.0 | Transactional email delivery |
| HTTP client | httpx | >=0.28.1 | Async/sync HTTP for Razorpay, Green API, OpenRouter |
| Validation | Pydantic | >=2.11.0 | Request/response models, settings validation |
| Backend hosting | Railway | Nixpacks auto-detect | Python app + Celery worker + beat scheduler |
| Frontend hosting | Vercel | Vite framework preset | Static SPA with API proxy rewrites |
| Linter | oxlint | 1.79.0 | Fast Rust-based JS/TS linter (replaces ESLint) |

---

## Backend Stack

### FastAPI >=0.141.1

**Why FastAPI over Django or Flask:**

Django is a batteries-included framework built around synchronous request handling and an ORM. Recovery Router does not need an ORM (Supabase handles the database), does not need Django's admin panel, and does not need its template engine. Django would have been dead weight.

Flask is lightweight but lacks built-in async support, automatic request validation, and auto-generated OpenAPI docs. Every endpoint in Recovery Router uses Pydantic models for input validation and response typing -- FastAPI gets that for free via its `response_model` parameter.

FastAPI's async capability matters here because the webhook endpoint receives bursts of payment failure events from Razorpay. The async handler can accept and queue events without blocking on I/O, then hand off to Celery for actual processing.

The auto-generated `/docs` endpoint (Swagger UI) is valuable during the buildathon for rapid API testing without Postman.

**Key configuration from `main.py`:**

```python
app = FastAPI(
    title="Recovery Router API",
    description="Intelligent revenue recovery engine -- Razorpay AI Buildathon Track 3",
    version="1.0.0",
)
```

CORS is configured with explicit origin allowlists for the production domains (`albertabishek.com` subdomains), localhost dev ports (5173, 3000), and a regex pattern for Vercel preview deployments (`recovery-router*.vercel.app`). Methods are limited to GET, POST, PATCH, DELETE, OPTIONS -- no PUT, which matches the API's actual surface area.

### Celery >=5.6.3

**Why Celery for the task queue:**

Recovery Router processes payment failures asynchronously. When a webhook arrives, the system needs to classify the failure, generate a personalized message, and send it via WhatsApp/SMS/email -- all of which involve external API calls that can take seconds. Doing this synchronously in the webhook handler would time out Razorpay's webhook delivery.

Celery was chosen over lighter alternatives (like `rq` or `dramatiq`) because it has mature support for periodic tasks via Celery Beat, which Recovery Router uses for two scheduled jobs.

**Configuration deep-dive (from `celery_app.py`):**

```python
celery_app.conf.update(
    broker_transport_options={"visibility_timeout": 3600},
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    timezone="UTC",
)
```

What each setting does and why:

| Setting | Value | Why |
|---------|-------|-----|
| `task_acks_late` | `True` | Tasks are acknowledged only after completion, not when picked up. If a worker crashes mid-task, the message goes back to the queue instead of being lost. Critical for payment recovery where losing a task means losing revenue. |
| `task_reject_on_worker_lost` | `True` | If a worker process dies (OOM kill, segfault), the task is rejected and re-queued. Pairs with `task_acks_late` for at-least-once delivery. |
| `worker_prefetch_multiplier` | `1` | Workers only grab one task at a time. Prevents a slow AI classification from blocking other tasks sitting in a worker's local buffer. |
| `visibility_timeout` | `3600` | A task that has been picked up but not acknowledged within 1 hour becomes visible again. Safety net for zombie workers. |
| `task_serializer` / `accept_content` | `json` | JSON-only serialization. No pickle, which would be a security risk since webhook payloads are untrusted input. |
| `task_default_retry_delay` | `60` | Failed tasks wait 60 seconds before retry. Gives transient issues (API rate limits, network blips) time to clear. |
| `task_max_retries` | `3` | Cap at 3 retries to prevent infinite loops on permanently failing tasks. |
| `broker_connection_retry_on_startup` | `True` | Worker retries Redis connection on startup instead of crashing. Important for Railway deployments where Redis might start slightly after the worker. |

**Beat schedule (periodic tasks):**

| Task | Schedule | Purpose |
|------|----------|---------|
| `run_escalation_cycle` | Every 300s (5 min) | Checks pending recovery events and escalates ones that haven't been resolved -- bumps attempt count, tries a different channel. |
| `scan_overdue_invoices` | Every 21600s (6 hours) | Scans Razorpay for overdue invoices and creates recovery events for ones not yet tracked. Proactive leak detection. |

**Task modules included:**
- `app.tasks.recovery` -- Core recovery processing (classify, route, message)
- `app.tasks.escalation` -- Periodic escalation of unresolved events
- `app.tasks.invoice_scan` -- Periodic overdue invoice scanning

### Redis >=5.3.0

Redis serves six distinct roles in Recovery Router, all through a single URL (`REDIS_URL` env var, defaulting to `redis://localhost:6379/0`):

| Role | Key Pattern | TTL | Why Redis |
|------|------------|-----|-----------|
| Celery broker | Celery internal keys | N/A | Standard Celery broker; low latency for task dispatch |
| Celery result backend | Celery internal keys | N/A | Task result storage for status checks |
| Analytics cache | `cache:analytics`, `cache:analytics:{from}:{to}` | 120s | Avoids recomputing aggregate analytics on every dashboard refresh |
| Event deduplication | `dedup:{event_type}:{identifier}` | 3600s (1 hour) | Prevents processing the same Razorpay webhook twice (Razorpay retries failed deliveries) |
| Rate limiting | `ratelimit:{key}` | Sliding window | Sliding-window rate limiter using sorted sets. Webhook endpoint is limited to 100 requests/60s. |
| Per-resource cooldowns | `cooldown:{resource_type}:{resource_id}` | 300s (5 min) | Prevents spamming the same phone/email. One message per channel per contact per 5 minutes. |
| Checkout token store | `checkout:{token}` | 86400s (24 hours) | Stores customer PII (name, email, phone) server-side, referenced by a random token in the checkout URL. Keeps PII out of URLs. |

The connection pool is lazily initialized with thread-safe double-checked locking (`redis_client.py`), and the pool is shared across all Redis consumers in the process.

### Supabase (PostgreSQL) -- supabase-py >=2.31.0

**Why Supabase over raw PostgreSQL or SQLAlchemy:**

1. **Managed infrastructure.** No need to provision, backup, or patch a PostgreSQL instance. Supabase handles it. The frontend keeps the dashboard current by polling the backend REST API at 15-30 second intervals.

3. **Row-level security.** Supabase's RLS policies can restrict what the frontend (using the anon key) can read. The backend uses the service key to bypass RLS for write operations.

4. **Client libraries.** Both the Python backend (`supabase-py`) and the React frontend (`@supabase/supabase-js`) have official SDKs with consistent APIs.

The backend initializes a singleton Supabase client with thread-safe lazy initialization (`database.py`), using the service key for full access.

### Other Python Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `uvicorn[standard]` | >=0.34.0 | ASGI server for FastAPI. The `standard` extra includes `uvloop` and `httptools` for better performance. |
| `httpx` | >=0.28.1 | HTTP client for external APIs (Razorpay, Green API, OpenRouter). Used instead of `requests` because it supports both sync and async, has built-in timeout handling, and a cleaner API. The AI client uses a persistent `httpx.Client` with connection pooling. |
| `pydantic` | >=2.11.0 | Data validation and serialization. Every API request/response has a Pydantic model. Used for `RecoveryEventInput`, `ClassificationResult`, `AnalyticsResponse`, etc. |
| `python-dotenv` | >=1.1.0 | Loads `.env` files in development. |
| `openai` | >=3.3.0 | Listed in requirements but not directly used in the current code -- OpenRouter is accessed via raw httpx calls instead. Likely kept as a dependency for potential direct OpenAI API fallback. |
| `sendgrid` | >=6.11.0 | Listed as a dependency but Resend is the active email provider. Kept as a potential fallback. |
| `twilio` | >=9.10.9 | Twilio SDK for SMS and WhatsApp template messages. |
| `resend` | >=2.10.0 | Resend SDK for transactional email. |

---

## Frontend Stack

### React 19.2.8

**Why React over Vue, Svelte, or Next.js:**

This is a single-page dashboard application with five views (Overview, Events, Analytics, Simulator, Audit Logs). The routing is handled with simple state (`activePage` state variable) rather than a router library -- hash or history routing would be overkill for five tabs.

React 19 was chosen because:
- The ecosystem is the largest, which matters when you are building under buildathon time pressure.
- React 19's automatic batching handles the polling-based event feed without manual optimization.

Vue or Svelte would work fine here but offer no specific advantage. Next.js would add server-side rendering complexity that a dashboard does not need -- there is no SEO requirement and no public-facing content.

### Vite 8.2.2

**Why Vite over Create React App or Webpack:**

Create React App is deprecated. Webpack requires significant configuration. Vite provides instant dev server startup via native ES modules and fast HMR. The config is 15 lines:

```javascript
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    allowedHosts: ['razorpay.albertabishek.com', 'app.albertabishek.com', 'localhost'],
    proxy: {
      '/api': 'http://localhost:8000',
      '/webhook': 'http://localhost:8000',
    },
  },
})
```

The dev proxy forwards `/api` and `/webhook` requests to the FastAPI backend, matching the production Vercel rewrite rules. This means the frontend code uses the same relative paths in development and production.

### Tailwind CSS 4.3.3

Used via the `@tailwindcss/vite` plugin (v4.3.3), which integrates Tailwind directly into Vite's build pipeline. Tailwind 4 uses a new CSS-first configuration approach (no `tailwind.config.js` needed) and compiles to standard CSS at build time.

Why Tailwind: rapid UI development without writing custom CSS files. Every component uses utility classes inline, which is ideal for a buildathon where speed matters more than design system architecture.

### Key Frontend Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^19.2.8 | UI framework |
| `react-dom` | ^19.2.8 | React DOM renderer |
| `@supabase/supabase-js` | ^2.112.4 | Supabase client -- included but not actively used; all data flows through the backend REST API |
| `tailwindcss` | ^4.3.3 | Utility-first CSS |
| `@tailwindcss/vite` | ^4.3.3 | Vite plugin for Tailwind 4 |
| `@vitejs/plugin-react` | ^6.1.0 | React Fast Refresh for Vite |
| `vite` | ^8.2.2 | Build tool |
| `oxlint` | ^1.79.0 | Rust-based linter (replaces ESLint -- 50-100x faster) |

**Notable absence:** No router library (react-router, tanstack-router). Navigation between the five pages is managed by a simple `activePage` state in `App.jsx`. This keeps the bundle small and avoids the complexity of client-side routing for what is essentially a tabbed dashboard.

**Frontend Supabase client (`lib/supabase.js`):**

```javascript
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY
export const supabase = SUPABASE_URL && SUPABASE_ANON_KEY
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  : null
```

The client uses the anon key (not the service key) and gracefully degrades to `null` if the environment variables are missing. It is currently unused -- the dashboard fetches all data via the backend REST API with 15-30 second polling intervals.

---

## AI / ML Stack

### OpenRouter as AI Gateway

**Why a single gateway instead of direct model APIs:**

Recovery Router uses three different AI models from three different providers (Anthropic, Google, OpenAI). Without OpenRouter, you would need:
- Three different API keys
- Three different SDK integrations
- Three different request/response formats
- Three different error handling patterns

OpenRouter provides a single endpoint (`https://openrouter.ai/api/v1/chat/completions`) with a unified OpenAI-compatible format. One API key, one request format, one error handling path. The entire AI client is 191 lines instead of what would be 400+.

### Model Fallback Chain

```python
MODEL_CHAIN = [
    {"id": "anthropic/claude-haiku-4.5", "name": "Claude Haiku 4.5", "timeout": 12, "max_retries": 1},
    {"id": "google/gemini-3.7-flash",    "name": "Gemini 3.7 Flash", "timeout": 10, "max_retries": 1},
    {"id": "openai/gpt-4o-mini",         "name": "GPT-4o-mini",      "timeout": 12, "max_retries": 1},
]
```

**Why this specific order:**

1. **Claude Haiku 4.5** (primary): Best quality-to-speed ratio for classification tasks. Haiku models are optimized for fast inference on structured outputs. 12-second timeout with 1 retry.

2. **Gemini 3.7 Flash** (first fallback): Google's speed-optimized model. Slightly faster (10-second timeout) and cheaper. Good enough for classification when Haiku is rate-limited or down.

3. **GPT-4o-mini** (second fallback): OpenAI's lightweight model. The most widely available -- if both Anthropic and Google are having issues, OpenAI is likely still up. 12-second timeout.

4. **Rule-based fallback** (final): If all three AI models fail, the system falls back to deterministic rules (`ai_call` returns `None`, and the caller uses hardcoded classification logic). Recovery never stops because AI is down.

**AI call parameters:**
- `temperature: 0.1` -- Near-deterministic output for consistent classification
- `max_tokens: 600` -- Enough for JSON classification responses, not wasteful
- `response_format: {"type": "json_object"}` -- Forces structured JSON output from all models
- Each model gets `max_retries: 1` (so 2 total attempts) with 0.5s backoff between retries

**What the AI does:**

The AI is used for two tasks:
1. **Event classification** (`classifier.py`): Determines the failure category, urgency, recommended channel, and personalization hint for each recovery event.
2. **Message generation** (`message_generator.py`): Creates personalized recovery messages tailored to the failure type and customer context.

---

## External Services

### Razorpay

**APIs used:**
- **Orders API** (`POST /v1/orders`): Creates payment orders for recovery checkout links. Deliberately chosen over the Payment Links API because Payment Links has a 30-link limit in test mode, while Orders has no such limit.
- **Webhooks**: Receives `payment.failed` events signed with HMAC-SHA256. The webhook handler verifies the signature before processing.

**Authentication:** HTTP Basic Auth with `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.

**Webhook security:** HMAC-SHA256 signature verification using `RAZORPAY_WEBHOOK_SECRET`. If the secret is not configured, webhooks are rejected (fail-closed, not fail-open).

### Green API (WhatsApp -- Primary)

**What it does:** Sends WhatsApp messages with AI-personalized text content. Unlike Twilio's WhatsApp, Green API allows free-form text messages, which means the AI-generated personalized content actually reaches the customer.

**How it works:** REST API call to `POST /waInstance{id}/sendMessage/{token}` with the chat ID (phone number + `@c.us`) and message body.

**Why Green API over Twilio for primary WhatsApp:** Twilio's WhatsApp requires pre-approved templates (via `content_sid`). You cannot send dynamic, AI-personalized text. Green API allows sending any text, which is the whole point of AI-personalized recovery messages.

### Twilio (SMS + WhatsApp Template Fallback)

**What it does:**
- **SMS**: Sends text messages with AI-generated content via `client.messages.create()`.
- **WhatsApp template**: Sends a pre-approved template message via `content_sid` (`HXfe5ab5f00277942d4d4200328b4d403c`). This is the fallback when Green API fails -- the customer gets a generic template instead of a personalized message.

**Trial limitations:** Twilio trial accounts can only send to verified numbers, which limits testing. The system handles this gracefully -- if Twilio fails, it falls through to the next provider in the chain.

### Resend (Email)

**What it does:** Sends transactional email with AI-personalized HTML content via `resend.Emails.send()`.

**Why Resend over SendGrid:** Resend has a simpler API, generous free tier (100 emails/day), and better developer experience. SendGrid is listed in `requirements.txt` as a dependency but is not actively used in the messenger code -- it is kept as a potential fallback.

**From address:** `noreply@mail.albertabishek.com` (custom domain for deliverability).

### Provider Fallback Chains

The messenger implements multi-provider fallback with per-resource cooldowns:

**WhatsApp chain:** Green API (personalized text) -> Twilio WhatsApp (template) -> Email fallback

**SMS chain:** Twilio SMS -> Green API WhatsApp -> Twilio WhatsApp -> Email fallback

**Email chain:** Resend (no fallback currently)

Each contact has a 5-minute cooldown per channel (`check_per_resource_cooldown`) to prevent message spam if retries fire rapidly.

---

## Infrastructure

### Railway (Backend)

**What runs on Railway:**
- **Web process:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Worker process:** `celery -A app.celery_app worker --loglevel=info --pool=prefork --concurrency=2`
- **Beat process:** `celery -A app.celery_app beat --loglevel=info`

These are defined in the `Procfile` for multi-process deployment.

**Build configuration (`railway.toml`):**
```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
```

Nixpacks auto-detects the Python runtime from `requirements.txt` -- no Dockerfile needed. The health check endpoint at `/api/health` verifies Redis, Supabase, and Celery worker connectivity. Automatic restart on failure with a 5-retry cap prevents crash loops.

### Vercel (Frontend)

**Configuration (`vercel.json`):**
```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [
    {"source": "/api/:path*", "destination": "https://api.albertabishek.com/api/:path*"},
    {"source": "/webhook/:path*", "destination": "https://api.albertabishek.com/webhook/:path*"}
  ]
}
```

Vercel serves the static SPA from the `dist` directory and proxies API requests to the Railway backend at `api.albertabishek.com`. This avoids CORS issues for the frontend's REST calls while keeping the architecture split.

### Redis Provider

Redis is provisioned as a managed add-on on Railway. The `REDIS_URL` environment variable is set automatically by Railway's Redis plugin. Default fallback is `redis://localhost:6379/0` for local development.

### Supabase (Managed PostgreSQL)

Supabase provides the managed PostgreSQL database with:
- Automatic backups
- Dashboard for data inspection
- Row-level security policies
- REST API auto-generated from the schema

---

## Development Tools

| Tool | Purpose | Configuration |
|------|---------|---------------|
| Vite dev server | Frontend HMR with API proxy | `vite.config.js` -- proxies `/api` and `/webhook` to `localhost:8000` |
| uvicorn `--reload` | Backend auto-reload on file changes | Via Procfile or manual `uvicorn app.main:app --reload` |
| oxlint | JavaScript/TypeScript linting | `npm run lint` -- Rust-based, 50-100x faster than ESLint |
| Python logging | Structured application logs | `%(asctime)s [%(levelname)s] %(name)s: %(message)s` format configured in `main.py` |

**No heavy test framework setup visible** -- the project prioritizes integration testing via the Simulator page in the dashboard, which lets you trigger synthetic events and watch them flow through the system in real time.

---

## Environment Variables

All configuration is via environment variables (loaded from `.env` in development via `python-dotenv`):

### Backend

| Variable | Required | Purpose |
|----------|----------|---------|
| `RAZORPAY_KEY_ID` | Yes | Razorpay API authentication |
| `RAZORPAY_KEY_SECRET` | Yes | Razorpay API authentication |
| `RAZORPAY_WEBHOOK_SECRET` | Yes | HMAC-SHA256 webhook signature verification |
| `OPENROUTER_API_KEY` | Yes | AI gateway authentication |
| `OPENAI_API_KEY` | No | Direct OpenAI access (fallback, currently unused) |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |
| `GREEN_API_INSTANCE_ID` | Yes | Green API WhatsApp instance |
| `GREEN_API_TOKEN` | Yes | Green API authentication |
| `GREEN_API_URL` | No | Default: `https://7107.api.greenapi.com` |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio authentication |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio authentication |
| `TWILIO_PHONE_NUMBER` | Yes | Twilio sender number |
| `RESEND_API_KEY` | Yes | Resend email authentication |
| `RESEND_FROM_EMAIL` | No | Default: `noreply@mail.albertabishek.com` |
| `SENDGRID_API_KEY` | No | SendGrid (backup, not actively used) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key (bypasses RLS) |
| `SUPABASE_ANON_KEY` | Yes | Supabase anonymous key (frontend-facing) |
| `REDIS_URL` | Yes | Redis connection string. Default: `redis://localhost:6379/0` |
| `APP_PASSWORD` | Yes | Dashboard login password |
| `FRONTEND_URL` | No | Default: `http://localhost:5173` |
| `API_BASE_URL` | No | Default: `http://localhost:8000` |
| `APP_ENV` | No | Default: `development` |
| `TEST_CUSTOMER_EMAIL` | No | Default: `test@example.com` |
| `TEST_CUSTOMER_PHONE` | No | Default: `+919999999999` |

### Frontend (Vite -- prefixed with `VITE_`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_SUPABASE_URL` | Yes | Supabase project URL (client-side) |
| `VITE_SUPABASE_ANON_KEY` | Yes | Supabase anonymous key (client-side) |

---

## Why Each Choice -- Alternatives Considered

### FastAPI vs. Django vs. Flask

| Criterion | FastAPI | Django | Flask |
|-----------|---------|--------|-------|
| Async support | Native | Partial (ASGI in 4.x, but ORM is sync) | No (requires gevent/asyncio hacks) |
| Request validation | Built-in via Pydantic | Forms/serializers (verbose) | Manual or Flask-Marshmallow |
| API docs | Auto-generated Swagger + ReDoc | Django REST Framework (separate install) | Flask-RESTX (separate install) |
| ORM | None needed (Supabase SDK) | Django ORM (wasted) | SQLAlchemy (separate install) |
| Learning curve | Low for API-focused projects | High (full framework) | Low but less productive |

**Tradeoff accepted:** FastAPI has a smaller ecosystem for non-API tasks (admin panels, background jobs need separate libraries). This is fine because Recovery Router is purely an API service.

### Supabase vs. Raw PostgreSQL vs. Firebase

| Criterion | Supabase | Raw PostgreSQL | Firebase |
|-----------|----------|---------------|----------|
| Realtime (available) | Built-in WebSocket subscriptions (not used in current build) | Manual LISTEN/NOTIFY + custom WebSocket | Built-in |
| SQL support | Full PostgreSQL | Full PostgreSQL | NoSQL only |
| Row-level security | Built-in | Manual policies | Security rules (different model) |
| Hosting | Managed | Self-managed or managed | Managed |
| Python SDK | Official | psycopg2/asyncpg | firebase-admin |
| Cost at scale | Predictable | Depends on hosting | Can spike with reads |

**Tradeoff accepted:** Supabase adds a dependency on their platform. If Supabase goes down or changes pricing, migration to raw PostgreSQL is straightforward since it is PostgreSQL underneath.

### React vs. Vue vs. Svelte

**For a buildathon dashboard, the choice barely matters.** React was chosen because:
- Largest ecosystem = fastest to find solutions when stuck
- Supabase has the most React examples
- React 19's improvements (automatic batching, better Suspense) are production-ready

**Tradeoff accepted:** React's bundle is larger than Svelte's. For a dashboard used by the merchant (not public-facing), bundle size is irrelevant.

### Redis vs. RabbitMQ vs. SQS

| Criterion | Redis | RabbitMQ | Amazon SQS |
|-----------|-------|----------|------------|
| Celery broker | Excellent support | Best support | Supported |
| Also serves as cache | Yes | No | No |
| Rate limiting / dedup | Native data structures | Need separate service | Need separate service |
| Operational complexity | Single service | Separate service | AWS dependency |
| Durability | AOF/RDB (good enough) | Excellent | Excellent |

**Tradeoff accepted:** Redis as a Celery broker is slightly less durable than RabbitMQ (a crash could lose in-flight messages). For this use case, losing a recovery event is recoverable -- the escalation cycle will catch it on the next scan. The operational simplicity of one Redis instance serving seven roles outweighs the durability tradeoff.

### OpenRouter vs. Direct API Calls

| Criterion | OpenRouter | Direct APIs |
|-----------|-----------|-------------|
| API keys needed | 1 | 3 (Anthropic, Google, OpenAI) |
| Code complexity | Single client | Three separate integrations |
| Latency overhead | ~50-100ms | None |
| Model switching | Change a string | Change SDK + request format |
| Cost | Small markup | Base pricing |

**Tradeoff accepted:** OpenRouter adds a small latency and cost markup per request. For a classification call that takes 1-3 seconds, 50ms overhead is negligible. The code simplicity gain is substantial.

---

## Cost Implications

### Free Tier Services

| Service | Free Tier | What You Get |
|---------|-----------|-------------|
| Supabase | Yes | 500MB database, 2GB bandwidth, 50K monthly active users, Realtime included |
| Vercel | Yes (Hobby) | 100GB bandwidth, serverless functions, preview deployments |
| Resend | Yes | 100 emails/day, 1 custom domain |
| Green API | Trial | Limited messages for testing |
| Twilio | Trial | $15.50 credit, verified numbers only |
| Razorpay | Test mode | Full API access, no real payments processed |

### Paid Services

| Service | Cost Model | Current Tier |
|---------|-----------|-------------|
| Railway | Usage-based ($5/month minimum after trial) | Hosting backend + Redis + Celery workers |
| OpenRouter | Per-token | Varies by model; Haiku and Flash are sub-cent per call for classification |

### Where Costs Grow Fastest

1. **OpenRouter / AI calls.** Every recovery event makes at least one AI call for classification and one for message generation. At scale, if you process 10,000 failed payments/day, that is 20,000+ AI calls/day. Even at $0.001/call, that is $20/day or $600/month. Mitigation: the rule-based fallback handles events when AI is unavailable, and caching classification results for identical error patterns would reduce calls.

2. **Twilio SMS/WhatsApp.** SMS costs ~$0.0079/segment (US), higher internationally. WhatsApp business messages cost ~$0.005-0.08 depending on region. At 10,000 messages/day, this could be $50-800/day. Mitigation: Green API is cheaper for WhatsApp; email (nearly free) is the fallback.

3. **Railway compute.** Celery workers are always-on processes. At scale, you need more workers with higher concurrency. Railway charges per vCPU-hour. A 2-worker deployment might cost $10-20/month; scaling to 10 workers could be $50-100/month.

4. **Supabase.** The free tier covers development and small-scale production. At scale (>500MB database, >50K MAU), the Pro plan is $25/month.

5. **Redis memory.** All seven Redis roles share one instance. At scale, the dedup keys (1-hour TTL), rate limit sorted sets, and checkout tokens (24-hour TTL) accumulate. A dedicated Redis instance with more memory would be needed -- Railway's Redis add-on scales with memory usage.

---

## Architecture Decisions Summary

The tech stack was chosen for **speed of development** (buildathon constraint) and **operational simplicity** (single-developer deployment). Every choice prioritizes fewer moving parts:

- One database service (Supabase) instead of PostgreSQL + separate hosting
- One cache/broker (Redis) instead of Redis + RabbitMQ
- One AI gateway (OpenRouter) instead of three separate model SDKs
- One hosting platform per layer (Railway for backend, Vercel for frontend)
- No ORM, no router library, no state management library -- just the standard library features of each framework

The tradeoffs are appropriate for a buildathon project that needs to demonstrate a working end-to-end system. If this were a production system at scale, you would want RabbitMQ for the broker, a dedicated cache layer separate from the task queue, and direct model API integrations to avoid the OpenRouter markup.

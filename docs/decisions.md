# Decision Log -- Recovery Router

Every technical and non-technical decision made in the Recovery Router project, including things I intentionally didn't build.

Built by Albert Abishek I for the Razorpay AI Buildathon 2026 (Track 3: AI Revenue Recovery).

---

## Table of Contents

1. [Technical Decisions](#1-technical-decisions)
2. [Architecture Decisions](#2-architecture-decisions)
3. [Product Decisions](#3-product-decisions)
4. [Intentionally Avoided](#4-intentionally-avoided)
5. [Non-Technical Decisions](#5-non-technical-decisions)

---

## 1. Technical Decisions

### 1.1 FastAPI over Django/Flask

**Decision:** Use FastAPI as the web framework.

**Alternatives considered:** Django, Flask, Starlette (bare).

**Why this choice:** Recovery Router is a pure API service. It does not need Django's ORM (Supabase handles the database), Django's admin panel, or Django's template engine. All of that would be dead weight. Flask is lighter, but it lacks native async support and built-in request validation. Every endpoint in Recovery Router uses Pydantic models for input validation and response typing -- FastAPI gets that for free.

Three things sealed the decision:
- **Async webhooks.** Razorpay fires bursts of `payment.failed` events. FastAPI's async handler accepts and queues events without blocking on I/O, then hands off to Celery. The webhook returns 202 within milliseconds.
- **Auto-generated API docs.** The `/docs` endpoint (Swagger UI) was valuable during the buildathon for rapid API testing without needing Postman or curl.
- **Pydantic integration.** Every request/response model (`RecoveryEventInput`, `ClassificationResult`, `ActionPlan`) is a Pydantic class. FastAPI validates incoming data against these models automatically. Django REST Framework's serializers or Flask-Marshmallow would need extra boilerplate for the same thing.

**Tradeoffs accepted:** FastAPI has a smaller ecosystem for non-API tasks. No admin panel, no built-in background job framework. That is fine here -- Celery handles background work, and the React dashboard replaces an admin panel.

### 1.2 Celery + Redis over Alternatives

**Decision:** Use Celery with Redis as the task queue for async processing.

**Alternatives considered:** Python RQ, Dramatiq, FastAPI BackgroundTasks, asyncio task groups.

**Why this choice:** The recovery pipeline involves external API calls to Razorpay, OpenRouter, and messaging providers that can take 5-30 seconds. Running these in the webhook handler would time out Razorpay's webhook delivery. Celery gives four things the lighter alternatives do not:

1. **Celery Beat for periodic tasks.** Recovery Router runs two scheduled jobs: escalation sweeps every 5 minutes and invoice scans every 6 hours. RQ has rq-scheduler as an addon; Dramatiq has no built-in scheduler. Celery Beat is mature, battle-tested, and integrated.
2. **Delayed task execution.** Events classified with "send in 30 minutes" or "send in 4 hours" use `apply_async(countdown=N)`. This is a first-class Celery feature.
3. **Automatic retries with backoff.** Transient errors (connection timeouts, API rate limits) trigger exponential backoff retries (60s, 120s, 240s). Celery's `self.retry(exc=exc, countdown=backoff)` handles this natively.
4. **Worker isolation.** A crashed AI call or a hanging messaging provider does not affect the FastAPI API server. Workers are separate processes.

Python RQ is simpler but lacks delayed tasks and built-in periodic scheduling. Dramatiq is excellent but less widely adopted, and its periodic task story requires a third-party library. FastAPI BackgroundTasks run in the same process -- a hanging AI call would block the event loop.

**Tradeoffs accepted:** Celery is heavy for a buildathon project. The configuration surface is large (`celery_app.py` has 14 settings). The operational cost is three processes instead of one (web, worker, beat). Worth it for reliability.

### 1.3 Supabase over Raw PostgreSQL

**Decision:** Use Supabase as the database layer.

**Alternatives considered:** Self-hosted PostgreSQL with SQLAlchemy, Firebase, PlanetScale.

**Why this choice:** Supabase gave me three things for free that would have taken days to build:

1. **Realtime subscriptions.** The frontend dashboard subscribes to the `recovery_events` table via Supabase Realtime. New events and status changes appear on the dashboard instantly without polling. With raw PostgreSQL, I'd need to set up LISTEN/NOTIFY plus a WebSocket relay -- Supabase provides this out of the box.
2. **Managed infrastructure.** No provisioning, no backups, no patching. One fewer thing to maintain during a buildathon under time pressure.
3. **Dual-key access model.** The backend uses `SUPABASE_SERVICE_KEY` for full table access. The frontend uses `SUPABASE_ANON_KEY` for Realtime subscriptions only. Row-level security policies restrict what the anon key can read.

Firebase was considered but rejected: it is NoSQL-only, and Recovery Router's data model (events with foreign-key-linked attempts, partial unique indexes, PostgreSQL triggers) needs a relational database. PlanetScale would work but does not have a Realtime subscription feature.

**Tradeoffs accepted:** Supabase adds a platform dependency. If Supabase goes down or changes pricing, migration is straightforward because it is PostgreSQL underneath. The Python SDK (`supabase-py`) is less mature than `psycopg2` or SQLAlchemy, which means some queries are more verbose than they would be with a proper ORM.

### 1.4 OpenRouter over Direct Model APIs

**Decision:** Route all AI calls through OpenRouter instead of calling Anthropic, Google, and OpenAI APIs directly.

**Alternatives considered:** Direct Anthropic SDK, direct Google Gemini SDK, direct OpenAI SDK, LiteLLM.

**Why this choice:** Recovery Router uses three AI models from three different providers. Without OpenRouter, I'd need three API keys, three SDK integrations, three request/response formats, and three error handling paths. OpenRouter provides a single endpoint (`https://openrouter.ai/api/v1/chat/completions`) with a unified OpenAI-compatible format.

The entire AI client (`ai_client.py`) is 191 lines. With three separate SDKs, it would be 400+ lines with three times the error handling surface. Switching models is a string change, not a library swap.

LiteLLM was considered as an alternative gateway. OpenRouter was chosen because it is a hosted service (no self-hosted proxy needed) and its model catalog includes all three target models.

**Tradeoffs accepted:** OpenRouter adds ~50-100ms of latency per request and a small cost markup. For a classification call that takes 1-3 seconds, 50ms overhead is negligible. The code simplicity gain is substantial. If this were a production system processing 50,000 events/day, the cost markup (~$0.001/call extra) would justify switching to direct APIs.

### 1.5 Three Models in This Order: Claude Haiku 4.5 -> Gemini 3.7 Flash -> GPT-4o-mini

**Decision:** A specific 3-model fallback chain with Claude Haiku first.

**Alternatives considered:** Single model (cheaper, simpler), two models, different ordering.

**Why this choice:**

1. **Claude Haiku 4.5** (primary): Best quality-to-speed ratio for structured classification. Haiku models are optimized for fast inference on JSON outputs. In testing, Haiku consistently produced the most nuanced failure category assignments -- correctly distinguishing "UPI timeout" from "user cancelled" based on error description text that was ambiguous. 12-second timeout, 1 retry.

2. **Gemini 3.7 Flash** (first fallback): Google's speed-optimized model. Slightly faster (10-second timeout) and cheaper. It handles the classification task well enough when Haiku is rate-limited or down. Chosen as second because its JSON output was occasionally less consistent than Haiku's.

3. **GPT-4o-mini** (second fallback): The most widely available model. If both Anthropic and Google are having issues, OpenAI is likely still up. Serves as the reliability anchor. 12-second timeout.

4. **Rule-based fallback** (final): If all three models fail, deterministic rules take over. A `FALLBACK_RULES` dictionary maps error code keywords to (category, probability, channel, timing) tuples. Recovery never stops because AI is down.

The key insight is that these models are used for classification and message generation, not complex reasoning. All three are "small/fast" tier models. Using a frontier model (Claude Opus, GPT-4o) would add cost and latency without meaningfully improving classification accuracy for this use case.

**Tradeoffs accepted:** Three models means three potential failure points in each call. Each model gets only 1 retry (2 attempts total) to keep total worst-case latency under 30 seconds. A single model with 3 retries would be simpler but has a single point of failure.

### 1.6 Rule-Based Fallback Exists

**Decision:** Maintain a complete rule-based classifier and message template system alongside AI.

**Alternatives considered:** AI-only (fail if AI is unavailable), queue events until AI recovers.

**Why this choice:** Reliability beats sophistication. Payment recovery is time-sensitive -- a UPI timeout needs a retry link within minutes, not "whenever the AI comes back." The rule-based fallback handles all 12 failure categories with pre-written action descriptions, reasoning text, and recovery probabilities derived from the AI's typical outputs.

The fallback uses a two-pass keyword match: first against the error code, then against the error description. Each category has a `FALLBACK_ACTIONS` dictionary with action, reasoning, alternative, and skip_reason strings. Even without AI, recovery messages are contextually appropriate.

**Tradeoffs accepted:** The rule-based fallback is less nuanced. It cannot distinguish between "UPI timeout due to network congestion" (high recovery) and "UPI timeout due to expired VPA" (low recovery) based on subtle error description differences. It assigns the same probability to all UPI timeouts (0.80) while the AI might give 0.85 for one and 0.60 for the other. For most events, this difference does not change the recovery outcome.

### 1.7 Razorpay Orders API over Payment Links API

**Decision:** Use the Orders API to create checkout orders instead of the Payment Links API.

**Alternatives considered:** Payment Links API (the "obvious" choice for recovery links).

**Why this choice:** The Payment Links API has a 30-link lifetime limit in test mode. During development and demo, each test scenario creates a payment link. Hit the limit after 30 tests and the system stops working. The Orders API has no such limit.

By creating orders and hosting my own checkout page at `/pay/{order_id}`, I get unlimited test-mode payment generation. The hosted page loads Razorpay's Standard Checkout SDK, pre-fills customer details from a Redis-stored token, and auto-opens the checkout modal.

**Tradeoffs accepted:** Three things are worse with this approach:
- Checkout URLs are longer than Razorpay's `rzp.io` short links.
- The checkout page is served by my FastAPI app -- if the backend goes down, checkout links break.
- I had to build and maintain a server-rendered HTML checkout page instead of using Razorpay's hosted page.

In production, you would use the Payment Links API (no 30-link limit outside test mode). This was a necessary buildathon workaround.

### 1.8 Green API for WhatsApp over Twilio-Only

**Decision:** Use Green API as the primary WhatsApp provider, with Twilio WhatsApp as fallback.

**Alternatives considered:** Twilio WhatsApp only, WhatsApp Business API directly, no WhatsApp.

**Why this choice:** The entire value proposition of Recovery Router's AI is personalized messages. The AI writes context-aware recovery text ("Hey Arun, looks like your UPI payment of Rs 4,999 timed out..."). Green API lets me send that personalized text as a free-form WhatsApp message.

Twilio's WhatsApp integration requires pre-approved templates via `content_sid`. You cannot send dynamic, AI-personalized text -- every message uses the same template. That defeats the purpose of having AI-generated messages.

Green API allows sending any text, which means the customer receives the actual AI-crafted message. Twilio WhatsApp is the fallback: if Green API fails, the customer at least gets a template message (better than nothing).

**Tradeoffs accepted:** Green API requires a phone with WhatsApp Web connected to the API instance. If the phone disconnects, sends fail silently (API returns 200 but the message is never delivered). There are no delivery receipts. This is acceptable for a buildathon demo but not for production. In production, the WhatsApp Business API (direct from Meta) would replace both providers.

### 1.9 Self-Hosted Checkout Page

**Decision:** Build a server-rendered checkout page at `/pay/{order_id}` instead of relying on Razorpay-hosted pages.

**Alternatives considered:** Razorpay Payment Links (hosted by Razorpay), Razorpay Standard Checkout in a static page.

**Why this choice:** This was a consequence of the Orders API decision (see 1.7). Since I use Orders instead of Payment Links, there is no Razorpay-hosted checkout page. I needed to build one.

The page is server-rendered HTML from `backend/app/routers/checkout.py`. It loads Razorpay's Checkout.js SDK, reads customer details from a Redis token (`?t={token}`), and auto-opens the checkout modal 500ms after page load. The order ID is validated against a regex (`^order_[A-Za-z0-9]{8,30}$`). All user-supplied strings are escaped for both HTML and JavaScript contexts.

Customer PII (name, email, phone) is stored server-side in Redis with a random 24-byte token. The PII never appears in the URL path or query parameters beyond the opaque token. This means recovery links can be forwarded or shared without leaking customer information.

**Tradeoffs accepted:** The checkout page is a security surface I maintain. It runs on my backend -- if the backend goes down, checkout links break. There is no CSRF protection on the page. The checkout token has a 24-hour TTL, after which the page still works but without pre-filled customer details.

### 1.10 Redis for Six Different Purposes

**Decision:** Use a single Redis instance for six distinct roles.

**Alternatives considered:** Separate services for each role (RabbitMQ for broker, Memcached for cache, etc.), multiple Redis instances.

**Why this choice:** Operational simplicity. One service, one connection URL, one thing to monitor. The six roles:

| Role | Key pattern | TTL | Why Redis works |
|------|-------------|-----|-----------------|
| Celery broker | Celery internal | N/A | Standard Celery broker pattern |
| Celery result backend | Celery internal | N/A | Task result storage |
| Dedup cache | `dedup:{type}:{id}` | 1 hour | `SET NX` is a perfect dedup primitive |
| Rate limiting | `ratelimit:{key}` | Sliding window | Sorted sets enable sliding windows |
| Per-resource cooldowns | `cooldown:{type}:{id}` | 5 min | `SET NX EX` is a natural cooldown |
| Checkout token store | `checkout:{token}` | 24 hours | Key-value with TTL, exactly what Redis does |
| Analytics cache | `cache:analytics:{range}` | 120s | Simple cache with auto-expiry |
| Distributed locks | `lock:event:{id}`, `lock:escalation` | 240-300s | `SET NX EX` gives atomic locking |

Every role uses a different Redis data structure or operation in a way that plays to Redis's strengths. There is no role here that would be better served by a different technology at this scale.

**Tradeoffs accepted:** All roles share a single instance. If Redis goes down, everything breaks -- not just the task queue but also dedup, rate limiting, cooldowns, and locks. At higher scale, you would split into at least two instances: one for the Celery broker (tuned for queue throughput) and one for cache/locks/cooldowns (tuned for low latency). For a single-merchant buildathon demo, one instance is correct.

### 1.11 React 19 + Vite 8 for the Frontend

**Decision:** Use React 19 with Vite 8 as the frontend stack.

**Alternatives considered:** Vue, Svelte, Next.js, no frontend (API-only).

**Why this choice:** For a buildathon dashboard with five pages, the framework choice barely matters. React was chosen for three practical reasons:
- Largest ecosystem means fastest to find solutions when stuck under time pressure.
- Supabase has the most React examples and official hooks.
- React 19's automatic batching handles the real-time event feed without manual optimization.

Vite 8 was chosen because Create React App is deprecated and Webpack requires significant configuration. Vite provides instant dev server startup and the config is 15 lines. The dev proxy forwards `/api` and `/webhook` requests to the FastAPI backend, so the frontend uses the same relative paths in development and production.

No router library -- page state is managed via `useState('overview')` in `App.jsx`. Five tabs do not need react-router's complexity. No state management library -- React's built-in state and context are sufficient for a dashboard that polls every 30 seconds.

**Tradeoffs accepted:** React's bundle is larger than Svelte's. For a merchant dashboard (not public-facing), bundle size is irrelevant. No SSR means no SEO, which is fine because this is an authenticated dashboard with no public content.

### 1.12 Railway for Backend, Vercel for Frontend

**Decision:** Split hosting: Railway for the Python backend, Vercel for the React frontend.

**Alternatives considered:** Everything on Railway, everything on Vercel (serverless), Fly.io, Render, self-hosted.

**Why this choice:** Railway supports multi-process Procfile deployments. The backend needs three always-on processes: the FastAPI web server, the Celery worker, and Celery Beat. Railway runs each Procfile entry as a separate container. Vercel's serverless model cannot run persistent worker processes.

Vercel handles the static React frontend with CDN distribution, preview deployments for every branch, and API rewrites that proxy `/api` requests to the Railway backend. This keeps frontend deploys fast (static file upload) and decoupled from backend deploys.

Railway also provides a managed Redis addon that sets `REDIS_URL` automatically.

**Tradeoffs accepted:** Two hosting platforms means two dashboards, two billing accounts, and CORS configuration between them. The split also means the frontend's API calls cross a network boundary (Vercel CDN -> Railway backend), adding latency compared to co-located deployment.

### 1.13 PostgreSQL Trigger as Last Line of Defense

**Decision:** Add a `BEFORE UPDATE` trigger on `recovery_events` that blocks premature exhaustion.

**Alternatives considered:** Application-level checks only, database constraints only.

**Why this choice:** This trigger exists because of an actual bug. During development, an old prototype process was still running and writing directly to the database, marking events as "exhausted" before the recovery budget was spent. The application-level safety checks (two layers in the escalation engine) could not prevent writes that bypassed the application entirely.

The trigger fires whenever `status` is changing to `exhausted`. It blocks the transition if `attempt_count < max_attempts` AND `max_attempts > 0` AND `skip_reason IS NULL`. When blocked, it reverts the status to the old value and raises a PostgreSQL WARNING.

This catches any writer -- the application, manual SQL queries, n8n workflows, future integrations -- that tries to prematurely exhaust an event. It is a defense-in-depth measure: the application's two safety layers should prevent it, and the trigger catches what slips through.

**Tradeoffs accepted:** Database triggers are invisible to application code. A developer debugging an exhaustion issue might not realize a trigger is silently reverting their update. The trigger raises a WARNING, but you have to be looking at PostgreSQL logs to see it. This is documented in the migrations and architecture docs, but it is still a non-obvious behavior.

---

## 2. Architecture Decisions

### 2.1 Six Components, Not Monolith, Not Microservices

**Decision:** The system has six components: FastAPI API, Celery Worker, Celery Beat, React Frontend, Redis, and Supabase PostgreSQL.

**Alternatives considered:** Monolith (everything in one process), microservices (separate services for classification, messaging, tracking, etc.).

**Why this choice:** A monolith would mean the webhook handler, the AI classifier, the message sender, and the escalation engine all run in the same process. A hanging AI call would block webhook ingestion. A crashed message send would take down the API.

Microservices would mean separate deployable services for classification, messaging, escalation, and tracking -- each with its own API, deployment, and monitoring. For a single-developer buildathon project, this is architectural overkill. The inter-service communication overhead and deployment complexity would eat the entire development timeline.

Six components hits the sweet spot: the API and worker are separate processes (fault isolation), but they share the same codebase (development simplicity). Redis and Supabase are managed services (zero operational burden). The frontend is a static SPA (decoupled deploys).

**Tradeoffs accepted:** All backend logic lives in one codebase. There is no independent scalability for, say, the classifier versus the messenger. At scale, you would want dedicated Celery queues for `recovery`, `escalation`, and `invoice_scan` tasks, routed to specialized worker pools.

### 2.2 Async Pipeline with Celery, Not Synchronous Processing

**Decision:** Webhook ingestion is synchronous (validate and queue), but the entire recovery pipeline (classify, route, generate link, send message, log) runs as an async Celery task.

**Alternatives considered:** Synchronous processing in the webhook handler, async with FastAPI background tasks.

**Why this choice:** The recovery pipeline involves multiple external API calls:
- AI classification via OpenRouter (1-3 seconds)
- Payment link creation via Razorpay Orders API (1-2 seconds)
- AI message generation via OpenRouter (1-3 seconds)
- Message delivery via Green API/Twilio/Resend (1-5 seconds)

Total: 4-13 seconds of external I/O per event. Razorpay webhooks expect a response within a few seconds. Running this synchronously would cause timeouts, leading Razorpay to retry the webhook, leading to duplicate processing.

The webhook handler does five fast operations (rate limit, body size check, HMAC verification, Redis dedup, payload normalization), then calls `process_recovery_event.delay(event_data)` and returns 202 immediately. Total webhook response time: under 100ms.

FastAPI's `BackgroundTasks` were rejected because they run in the same process. A hung AI call would consume a thread from the async event loop. Celery workers are separate processes with their own resource pools.

**Tradeoffs accepted:** Celery adds operational complexity (separate worker and beat processes). There is a delay between webhook acceptance and actual processing -- typically 1-2 seconds for the Celery worker to pick up the task. For payment recovery (where the customer is already past the payment attempt), this delay is imperceptible.

### 2.3 `task_acks_late=True` and `task_reject_on_worker_lost=True`

**Decision:** Configure Celery for at-least-once delivery with late acknowledgment.

**Alternatives considered:** Default (ack on pickup), at-most-once delivery.

**Why this choice:** Each Celery task represents a revenue recovery opportunity. Losing a task means losing potential revenue. With `task_acks_late=True`, tasks are acknowledged only after the worker completes them successfully. If a worker dies mid-task (OOM kill, segfault, network partition), the task returns to the queue and is picked up by another worker.

`task_reject_on_worker_lost=True` complements this: if a worker process is lost (not just a task exception but a process-level failure), the task is explicitly rejected and re-queued rather than silently lost.

`worker_prefetch_multiplier=1` ensures each worker fetches only one task at a time, preventing a slow AI classification from blocking other tasks sitting in a worker's local buffer.

**Tradeoffs accepted:** At-least-once delivery means tasks can run more than once. The system handles this with two-level deduplication (Redis fast path + DB unique indexes). There is also a `visibility_timeout` of 3600 seconds: if a task has been picked up but not acknowledged within an hour, it becomes visible again. This is a safety net for zombie workers but means a very slow task could be processed twice.

### 2.4 Exponential Backoff: 60s -> 120s -> 240s

**Decision:** Transient errors trigger Celery retries with exponential backoff.

**Alternatives considered:** Fixed delay (always 60s), no backoff (immediate retry), jittered backoff.

**Why this choice:** The backoff formula is `60 * (2 ** self.request.retries)`:
- First retry: 60 seconds
- Second retry: 120 seconds
- Third retry: 240 seconds (4 minutes)

This gives transient issues (API rate limits, network blips, provider outages) progressively more time to resolve. A fixed delay might retry into the same rate limit window. Immediate retries waste capacity hammering an already-overloaded service.

The maximum of 3 retries caps the total retry window at about 7 minutes. After that, the task is logged as a permanent failure. This prevents infinite retry loops on unfixable errors.

**Tradeoffs accepted:** No jitter. Two workers retrying the same type of failure will hit the same backoff schedule and potentially retry simultaneously. At the current scale (2 workers), this is not a problem. At higher concurrency, adding random jitter (`backoff + random.uniform(0, 30)`) would reduce thundering herd effects.

### 2.5 Distributed Locks Instead of Database-Only Locking

**Decision:** Use Redis `SET NX EX` for distributed locks instead of database row locks.

**Alternatives considered:** PostgreSQL advisory locks, `SELECT ... FOR UPDATE`, no locking (rely on conditional updates only).

**Why this choice:** Three lock levels exist in the system:

| Lock | Key | TTL | Purpose |
|------|-----|-----|---------|
| Global escalation | `lock:escalation` | 240s | Prevent concurrent escalation cycles |
| Per-event | `lock:event:{id}` | 300s | Prevent concurrent processing of the same event |
| Delayed send | `lock:event:{id}` | 300s | Prevent delayed task racing with escalation |

Redis locks are faster than database locks (sub-millisecond vs. milliseconds). They do not hold database connections. They have automatic expiry -- if a process dies without releasing the lock, it expires on its own. PostgreSQL advisory locks would need explicit release and could leak if the connection drops ungracefully.

All locks use `SET NX EX` (atomic set-if-not-exists with expiry). No lock renewal -- if a process is slower than the TTL, the lock expires and another process can proceed. This is acceptable because:
- The escalation cycle processes 50 events in under 240 seconds.
- Per-event processing (classify + send) completes in under 300 seconds even with slow AI responses.

**Tradeoffs accepted:** Redis locks are not as durable as database locks. If Redis restarts, all locks disappear. This could cause a brief window of concurrent escalation. The system handles this gracefully: conditional updates (`eq("status", "pending")`) prevent double-processing even without locks. The locks are an optimization to prevent wasted work, not a correctness requirement.

### 2.6 Two-Level Deduplication: Redis + Database

**Decision:** Deduplicate events at both the Redis layer (fast) and the database layer (durable).

**Alternatives considered:** Redis only, database only, no dedup (rely on Razorpay's idempotency).

**Why this choice:** Razorpay retries failed webhook deliveries. Without dedup, the same `payment.failed` event could create multiple recovery events, each sending its own recovery message to the customer.

**Layer 1 -- Redis** (`dedup.py`): `SET dedup:{event_type}:{identifier} 1 NX EX 3600`. Sub-millisecond check. Catches webhook retries within the same hour (Razorpay typically retries within minutes). But Redis is volatile -- a restart loses all dedup keys.

**Layer 2 -- Database** (`recovery.py`, `_check_durable_dedup`): Queries `recovery_events` for existing rows with the same `payment_id`, `order_id`, or `invoice_id`. Catches anything Redis missed (after a Redis restart, or if the key TTL expired before the retry). Backed by partial unique indexes that exclude `TEST_` prefixed IDs (simulator events are intentionally non-unique).

The combination gives both speed (Redis answers 99% of dedup checks in microseconds) and correctness (the database catches the rest).

**Tradeoffs accepted:** The 1-hour Redis TTL means a very late Razorpay retry (>1 hour after the original) would pass the Redis check and rely on the database layer. The database query is slower (milliseconds vs. microseconds) but only fires for events that pass the Redis check. In practice, Razorpay retries happen within 5 minutes.

### 2.7 Sliding Window Rate Limiting, Not Fixed Window

**Decision:** Use a sliding window rate limiter based on Redis sorted sets.

**Alternatives considered:** Fixed window counters, token bucket, leaky bucket.

**Why this choice:** Fixed window rate limiting has a burst problem: if you allow 100 requests per minute, a client can send 100 requests at 0:59 and another 100 at 1:01, effectively getting 200 requests in 2 seconds. The sliding window avoids this by counting requests within a continuously moving time window.

The implementation uses a Redis sorted set where each member is a timestamp. On each request:
1. Remove all members older than `now - window_seconds` (trim the window)
2. Add the current timestamp
3. Count the members
4. If count exceeds the limit, remove the just-added member and reject

This gives accurate rate limiting regardless of when requests arrive within the window.

**Tradeoffs accepted:** Sorted sets use more memory than simple counters (one entry per request instead of one counter per window). At 100 requests/minute, each sorted set has at most 100 members -- trivial memory. At 10,000 requests/minute, you would want a more memory-efficient algorithm.

### 2.8 72-Hour Recovery Window with 24-Hour Extension

**Decision:** Each recovery event gets a 72-hour window. If no outreach was ever sent and the window expires, it extends by 24 hours.

**Alternatives considered:** No window (try forever), fixed window (hard 72-hour cutoff), category-specific windows.

**Why this choice:** 72 hours is long enough for the escalation engine to try multiple channels across multiple days (respecting quiet hours and cooldowns), but short enough that the recovery message is still contextually relevant. A week-old "your UPI payment timed out" message feels stale.

The 24-hour extension exists for a specific edge case: if all messaging providers were down or cooldowns blocked every send attempt during the entire 72-hour window, the event would expire with zero outreach. That is unfair -- the system never got a chance. The extension gives one more day to attempt delivery.

The extension only applies when `attempt_count == 0` and `max_attempts > 0`. If at least one message was sent but the customer did not respond, the window expires normally. The customer has been given their chance.

**Tradeoffs accepted:** 72 hours is arbitrary. A gateway error might be recoverable within 5 minutes; an overdue invoice might benefit from follow-up over 2 weeks. Category-specific windows would be more optimal but add complexity. The escalation engine's retry delays (1-48 hours per category) provide category-specific pacing within the fixed window.

### 2.9 Per-Resource Cooldowns (5 Minutes)

**Decision:** Each phone number and email address has a 5-minute cooldown after receiving a message on any channel.

**Alternatives considered:** No cooldowns (send freely), longer cooldowns (1 hour), global cooldowns (across all resources).

**Why this choice:** Cooldowns prevent customer annoyance. If a customer appears in three concurrent recovery events (e.g., a failed payment, an abandoned cart, and an overdue invoice all within minutes), the system should not send three WhatsApp messages in rapid succession.

The 5-minute window balances responsiveness with restraint. It is short enough that the escalation engine (running every 5 minutes) can send one message per cycle per customer. It is long enough that a customer who receives a WhatsApp message is not immediately bombarded with an SMS about a different event.

The implementation is Redis `SET NX EX`: atomic, self-expiring, no cleanup needed. The cooldown is per-channel per-resource (`cooldown:whatsapp:+919999999999`), so a WhatsApp cooldown does not block an email to the same customer.

**Tradeoffs accepted:** If a customer has multiple events, only one gets outreach per 5-minute window. Lower-priority events wait. The escalation engine handles this gracefully -- the blocked send is logged as "cooldown active" and retried in the next cycle.

---

## 3. Product Decisions

### 3.1 Three Leak Types in One Pipeline

**Decision:** Handle payment failures, cart abandonment, and overdue invoices through the same classify-route-act-measure pipeline.

**Alternatives considered:** Separate pipelines per leak type, payment failures only.

**Why this choice:** The recovery problem is the same regardless of leak type: something went wrong, the system needs to understand what, decide how to recover, reach the customer, and track the outcome. The operations differ (a UPI timeout needs an immediate WhatsApp, an overdue invoice needs a formal email), but the pipeline shape is identical.

Building three separate pipelines would mean three sets of escalation logic, three sets of messaging code, three sets of analytics. One pipeline with a 12-category classification system is simpler to build, test, and maintain.

From a product perspective, a merchant should see all three leak types in one dashboard. "How much revenue am I losing?" is not "how much from failed payments?" -- it is the total across all leaks.

**Tradeoffs accepted:** The unified pipeline means the classification prompt has to handle all three leak types. This makes the AI system prompt longer (70 lines) and the fallback rules more complex. Some decisions (like timing) work differently across types: a UPI timeout is time-critical, an overdue invoice is not. The AI handles this nuance, but the rule-based fallback uses simpler heuristics.

### 3.2 Dynamic Attempt Budgets, Not Fixed 5 for Everyone

**Decision:** The number of recovery attempts (0-5) is computed dynamically based on amount, recovery probability, and failure category.

**Alternatives considered:** Fixed 5 attempts for everyone, fixed by category, merchant-configurable.

**Why this choice:** A blanket "always try 5 times" wastes outreach on unrecoverable events and under-serves high-value recoverable ones. The budget formula considers three factors:

- **Category hard stops:** Unrecoverable declines and browse-only carts get 0 attempts. User cancellations get max 2 (respect the customer's choice).
- **Probability floor:** Below 10% probability, 1 attempt (one shot, then stop).
- **Amount x probability matrix:** High-value + high-probability events (e.g., a Rs 5,000 UPI timeout at 0.85 probability) get 5 attempts. Low-value + moderate-probability events get 2-3.

This means the system spends its outreach budget where it is most likely to recover revenue.

**Tradeoffs accepted:** The budget formula is hardcoded, not merchant-configurable. A merchant might want different thresholds (e.g., "always try at least 3 times for amounts over Rs 1,000"). Adding merchant configuration would require a settings UI, storage, and per-merchant override logic. For a buildathon, the formula captures the right intent.

### 3.3 Ghost Recovery Prevention (Honest Metrics)

**Decision:** When a payment is captured and matched to a recovery event, the system checks whether my outreach actually contributed to the recovery.

**Alternatives considered:** Count all matched payments as "recovered" (simpler, inflated numbers).

**Why this choice:** If a customer's UPI payment times out at 3:00 PM, the system sends a WhatsApp at 3:01 PM, and the customer retries on their own at 3:02 PM (before even seeing the message), did the system recover that payment? No. But if I count it as "recovered," my metrics look better than they are.

The system distinguishes two outcomes:
- **`recovered`**: At least one outreach message was successfully sent before the payment was captured.
- **`organic_recovery`**: `attempt_count == 0` AND no successful outreach exists. The customer paid on their own.

The check is deliberately conservative: even if `attempt_count` is 0 (maybe due to a timing bug), if any attempt record shows `outcome = "sent"`, the recovery is attributed to outreach.

**Tradeoffs accepted:** This undercounts my effectiveness. If the system sent a WhatsApp and the customer paid 30 seconds later (probably because of the message), but the message delivery was not confirmed (only "sent" to the provider), I still count it as my recovery. But if the provider never accepted the message and the customer paid anyway, it is correctly marked organic. The undercounting direction is intentional -- better to understate than overstate.

### 3.4 Razorpay UI Clone (Feel Like a Native Feature)

**Decision:** Build the dashboard to look like a Razorpay product, using Razorpay's design language.

**Alternatives considered:** Generic dashboard (Material UI, Ant Design), custom branding.

**Why this choice:** The buildathon brief is "build something that feels like it belongs in Razorpay's ecosystem." Recovery Router's dashboard uses:
- Dark navy navbar (`#1B1F36`) with the Razorpay logo SVG
- Razorpay blue primary accent (`#528FF0`)
- Card-based layout with 8px border radius and 1px borders
- Status badges matching Razorpay's color system (green for success, amber for pending, red for failure)
- Inter font family with consistent weight hierarchy

This is a handcrafted CSS approach, not Razorpay's official design system library. The goal is that a Razorpay PM looking at the dashboard should immediately feel "this could be one of their products."

**Tradeoffs accepted:** The design is a visual clone, not a component library integration. If Razorpay updates their design language, the dashboard does not update automatically. The styling is done via CSS custom properties and Tailwind utilities, not a reusable design system. For a buildathon, visual fidelity matters more than engineering rigor in the design layer.

### 3.5 Quiet Hours (9 PM - 9 AM IST)

**Decision:** No recovery messages are sent between 9 PM and 9 AM Indian Standard Time.

**Alternatives considered:** No quiet hours, merchant-configurable hours, timezone-aware per-customer.

**Why this choice:** Sending a payment recovery WhatsApp at 2 AM is a good way to make a customer block your number. Quiet hours are a basic respect-the-customer measure. Events arriving during quiet hours are rescheduled to 9 AM the next morning -- they stay in the pipeline, just delayed.

9 PM to 9 AM covers the overnight period when most Indian consumers would not appreciate transactional messages. IST is hardcoded because Recovery Router is built for Indian merchants on Razorpay.

**Tradeoffs accepted:** A customer in a different timezone (say, a US-based customer of an Indian merchant) might be awake at 3 AM IST. The system still holds the message until 9 AM IST. Per-customer timezone detection would require IP geolocation or customer profile data that I do not have. Fixed IST is a reasonable default for Razorpay's primary market.

### 3.6 "Sent" Not "Delivered"

**Decision:** Track message outcomes as "sent" (provider accepted) rather than "delivered" (customer received).

**Alternatives considered:** Full delivery tracking via webhooks from each provider.

**Why this choice:** Honesty. The system can confirm that Green API, Twilio, or Resend accepted the message for delivery. It cannot confirm the customer saw it. Calling it "delivered" when I only know it was "sent" would inflate my outreach metrics.

The audit log and analytics dashboard use "sent" consistently. The ghost recovery prevention (3.3) uses this distinction too -- a message marked "sent" might not have reached the customer, so if the customer pays without any "sent" messages, it is classified as organic.

**Tradeoffs accepted:** I overstate my uncertainty. Many "sent" messages are probably delivered. Without delivery receipts, I cannot refine this. Building delivery webhook integrations for Green API, Twilio, and Resend would add three more webhook handlers, three more status tracking paths, and three more provider-specific behaviors. That is a v2 feature, not a buildathon feature.

---

## 4. Intentionally Avoided

### 4.1 No Promise-to-Pay (PTP) Feature

**Decision:** The system does not offer a "promise to pay later" option in recovery messages.

**Alternatives considered:** Adding a "I'll pay by [date]" response option with a reminder workflow.

**Why not:** PTP adds significant complexity: customer response handling (WhatsApp reply parsing or a web form), a promise tracking table, promise expiry logic, reminder workflows for broken promises, and a merchant interface to view/manage promises. This is a feature that sounds simple ("just let them say they'll pay later") but requires its own pipeline.

More importantly, PTP introduces a new trust problem. If a customer promises to pay and does not, the merchant needs to decide whether to pursue further. That decision tree is outside the scope of automated recovery. Recovery Router's job is "send the right message at the right time to get payment now," not "negotiate payment timelines."

### 4.2 No Complex ML Models for Classification

**Decision:** Use LLM-based classification, not trained ML models (gradient boosting, neural networks, etc.).

**Alternatives considered:** Training a custom classifier on Razorpay's historical failure data.

**Why not:** Training an ML model requires labeled training data: thousands of payment failures with correct failure categories and recovery outcomes. I do not have access to Razorpay's historical data. I am building on test-mode transactions with synthetic scenarios.

LLMs (Claude, Gemini, GPT) are effective zero-shot classifiers for this task. The error descriptions from Razorpay are natural language text ("Payment processing failed because the bank server is temporarily unavailable"). An LLM reads this and assigns the right category without any training data.

The rule-based fallback (keyword matching against error codes) provides a simpler version of what a trained classifier would do. If this system processed millions of real events, you would train a lightweight classifier on the observed patterns. For a buildathon, LLM classification + rule fallback is the pragmatic choice.

### 4.3 No Vanity Metrics / Inflated Numbers

**Decision:** Every metric in the dashboard reflects actual system behavior, with no inflation or misleading aggregation.

**Alternatives considered:** Standard industry practice of counting "all payments after recovery message" as recovered.

**Why not:** The recovery industry has a metrics credibility problem. If you send a recovery email and the customer pays three days later by navigating directly to the merchant's website, did the email cause the payment? Most recovery tools would count it as recovered. Recovery Router does not.

Three specific anti-inflation measures:
1. **Organic vs. recovered split.** Payments captured with zero successful outreach are marked `organic_recovery`, not `recovered`.
2. **"Sent" not "delivered."** Outreach metrics say "sent" because that is what I can verify.
3. **AI lift comparison.** The analytics page compares against a 15% industry baseline (cited from Razorpay's 2026 blog) so the improvement is contextualized, not presented as an absolute.

This hurts my demo numbers. A system that counts all matched payments as "recovered" would show a higher recovery rate. But honest numbers build trust, and trust is what a payment recovery system needs.

### 4.4 No Feature-Rich Dashboard (Fewer, High-Impact Features)

**Decision:** Five pages with focused functionality, not a sprawling dashboard with dozens of features.

**Alternatives considered:** Adding a merchant settings page, customer profiles, A/B testing, campaign management, export/download, custom notification templates.

**Why not:** More features does not mean a better product. A dashboard with 20 pages and half-working features is worse than one with 5 pages where everything works. The five pages cover the complete workflow:
- Overview: "What is happening right now?"
- Events: "What happened to each event?"
- Analytics: "Is the system working?"
- Simulator: "Let me test it."
- Audit Logs: "Show me every message attempt."

Each page was built to completion before starting the next. The simulator has live payment testing. The events page has a trace panel showing the full lifecycle. The audit logs show complete degradation paths. These are deep features, not surface features.

### 4.5 No Delivery Receipt Tracking (Yet)

**Decision:** Do not build delivery/read receipt integration for any messaging provider.

**Alternatives considered:** Twilio status callbacks, Green API delivery webhooks, Resend open tracking.

**Why not:** Each provider has a different delivery status model:
- Twilio fires status callback webhooks with states like `queued`, `sent`, `delivered`, `undelivered`, `failed`, `read`.
- Green API has a webhook for incoming messages and delivery receipts.
- Resend supports email open/click tracking via a tracking pixel.

Building three webhook handlers, a status reconciliation pipeline, and UI to show delivery status is a significant feature. It would need its own Celery task, its own database table, and its own UI components.

For the buildathon, the honest "sent" metric is sufficient. Delivery tracking is a clear v2 feature.

### 4.6 No Direct Database Access from Frontend

**Decision:** The frontend calls the backend API for all data operations. The only direct Supabase connection from the frontend is for Realtime subscriptions.

**Alternatives considered:** Using the Supabase client in the frontend for both reads and Realtime.

**Why not:** Direct database access from the frontend would bypass the backend's business logic, rate limiting, authentication, and logging. The backend's event listing endpoint (`GET /api/events`) adds pagination, filtering, status mapping, and access control. The analytics endpoint computes aggregate metrics and caches them.

The Supabase anon key in the frontend is restricted by RLS policies to read-only access. But even so, having the frontend query the database directly would create two data access paths that could diverge.

The single exception (Realtime subscriptions) is acceptable because Supabase Realtime is a push model -- the frontend subscribes and receives updates. It does not query or filter data; it just gets notified when rows change.

### 4.7 Specific Features That Were Rejected

During development, several features were considered and deliberately rejected:

- **Email open tracking pixels**: Would inflate "delivered" metrics and raise privacy concerns.
- **Discount/incentive codes in recovery messages**: Adds a discount management layer, margin impact tracking, and abuse prevention. Outside scope.
- **Multi-merchant support**: Would require `merchant_id` on all tables, tenant isolation, per-merchant settings, and a merchant onboarding flow. The system is single-tenant by design.
- **Promise-to-pay workflow**: See section 4.1.
- **Custom notification templates**: The AI generates messages. Merchant-editable templates would create a conflict between AI personalization and merchant control.
- **Scheduled report emails**: Would need an email scheduling service, report generation pipeline, and unsubscribe management. The dashboard serves this purpose.
- **Webhook replay/retry from the UI**: Would need an event store, replay queue, and idempotent processing guarantees. The simulator covers testing needs.

---

## 5. Non-Technical Decisions

### 5.1 "Think Like You Already Work There"

**Decision:** Build Recovery Router as if it were a real Razorpay product, not a buildathon demo.

**Alternatives considered:** Building a proof-of-concept with lorem ipsum data and stub endpoints.

**Why this choice:** The buildathon evaluates whether participants can build things that belong in Razorpay's ecosystem. A POC with placeholder data demonstrates coding ability but not product thinking. Recovery Router has:
- Real Razorpay API integration (test mode, but real API calls)
- Real messaging delivery (WhatsApp, SMS, email to actual phones/inboxes)
- Real-time dashboard with live data
- Production-grade error handling (retries, fallbacks, dedup, rate limiting)
- Honest metrics that a PM would trust

The goal was that a Razorpay engineer reviewing the code should think "this person could ship this internally" rather than "this is a hackathon project."

**Tradeoffs accepted:** Building production-grade infrastructure takes time away from features. Time spent on dedup, rate limiting, distributed locks, and the database trigger could have been spent on additional features like delivery tracking or A/B testing. The bet is that depth of execution matters more than breadth of features.

### 5.2 Razorpay's Design Tokens/Icons/Colors

**Decision:** Use Razorpay's visual identity in the dashboard: logo, colors, typography, layout patterns.

**Alternatives considered:** Generic design system, custom branding.

**Why this choice:** Visual consistency signals product thinking. When the dashboard opens with the Razorpay logo, navy navbar, and blue accent color, it immediately communicates "this is designed to be part of Razorpay." The evaluators see it as a product, not a project.

The specific elements:
- Razorpay logo SVG (inline path data, not an image file)
- Dark navy navbar (`#1B1F36`)
- Primary blue (`#528FF0`)
- Surface grey (`#F7F8FA`)
- Inter font family
- Card-based layout with subtle borders and shadows

These are extracted from Razorpay's public-facing dashboard by visual inspection, not from their internal design system.

**Tradeoffs accepted:** Using another company's visual identity in a demo could be seen as presumptuous. The buildathon context makes it appropriate -- the brief says "build for Razorpay." In a real product context, you would use the official design system with proper licensing.

### 5.3 Honest Limitations in the Demo

**Decision:** Acknowledge what is not done in the demo video and documentation, rather than glossing over it.

**Alternatives considered:** Only showing the best-case scenarios, avoiding mention of limitations.

**Why this choice:** The video script explicitly says "This runs on Razorpay test-mode data. There are open items: migrations need finishing, security policies need tightening, some matching edge cases need work." The known issues document (`docs/known_issues.md`) is a detailed inventory of everything incomplete, fragile, or limited.

Honesty about limitations demonstrates engineering maturity. A developer who says "here is what I did not build and why" shows better judgment than one who implies everything is perfect. Razorpay's own Vulcan page says "8-10% improvement" -- not "eliminates all failures."

**Tradeoffs accepted:** Listing limitations might make the project seem less impressive. The bet is that evaluators respect honesty over polish, especially in a revenue recovery product where metric integrity is the core differentiator.

### 5.4 Two-Part Demo Structure: Live Payment + Simulation

**Decision:** The demo video has two distinct segments: a real Razorpay payment that fails, and a simulated cart abandonment.

**Alternatives considered:** All simulated (faster, more controllable), all live (riskier, more impressive).

**Why this choice:** The live payment proves the system works end-to-end with Razorpay's actual infrastructure. A real checkout opens, a real payment fails, a real webhook fires, and the recovery pipeline processes it. This is not a mock -- the Razorpay checkout modal, the test failure card, the webhook delivery are all real.

The simulation shows that the same pipeline handles different leak types with different behaviors. A cart abandonment gets lower recovery odds, fewer attempts, and a gentler message tone. Comparing the two events side by side demonstrates the AI's contextual decision-making.

**Tradeoffs accepted:** The live payment segment carries demo risk. If the Razorpay API is slow, if the webhook is delayed, if the backend is cold-starting, the demo stalls on camera. Mitigation: pre-test both flows before recording, keep the dashboard pre-loaded, and accept that a few seconds of loading is authentic behavior.

### 5.5 114 Tests: Production Mindset, Not Demo Mindset

**Decision:** Write 114 tests across 5 test files covering API, pipeline, security, errors, and load behavior.

**Alternatives considered:** No tests (buildathon projects often skip them), minimal smoke tests.

**Why this choice:** Tests serve two purposes in a buildathon submission:
1. They prove the system actually works (not just the happy path that the demo shows).
2. They demonstrate engineering rigor.

The 114 tests cover:
- API endpoint validation (request/response contracts)
- Pipeline logic (classification, routing, budget computation, escalation)
- Security (HMAC verification, rate limiting, input sanitization)
- Error handling (provider failures, AI fallback, concurrent access)
- Load behavior (webhook bursts, concurrent escalation)

A Razorpay engineer reviewing the submission can run the tests and see that the system handles edge cases, not just the demo scenarios.

**Tradeoffs accepted:** Writing tests takes time away from features. 114 tests could have been 50 features. The bet is the same as 5.1: depth over breadth. A well-tested system with honest metrics and fewer features is more trustworthy than a feature-rich system with no tests and inflated numbers.

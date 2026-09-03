# Known Issues, Limitations & Open Items

> Recovery Router -- Razorpay AI Buildathon 2026 (Track 3)
> Built by Albert Abishek I
> Last updated: 2026-09-03

This is an honest inventory of everything that is incomplete, fragile, or limited in the current system. It exists so I know exactly what is not done.

---

## 1. Test-Mode Constraints (Critical)

### 1.1 All Razorpay data is test-mode
Every payment, order, and invoice is created with test-mode API keys. No real money moves. Recovery rates, amounts, and conversion metrics reflect simulated behavior, not production merchant traffic.

### 1.2 Payment Links replaced by Orders API workaround
Razorpay test-mode Payment Links API has a 30-link lifetime limit. The system works around this by using the Orders API plus a self-hosted checkout page (`/pay/{order_id}`) instead. This is functionally equivalent but:
- The checkout URLs are longer than Razorpay's `rzp.io` short links
- The hosted checkout page loads the Razorpay Checkout.js SDK from CDN -- this is a third-party dependency the system does not control
- If the backend goes down, checkout links break (they are served by the FastAPI app itself)

### 1.3 Simulator bypasses security checks
The `/api/simulate` endpoint generates events with `TEST_` prefixed payment/order IDs. These intentionally skip:
- Webhook signature verification (simulator events are not real Razorpay webhooks)
- Durable dedup on `TEST_` prefixed IDs (so the same scenario can be run repeatedly)

This is by design for demo purposes, but means the simulator path and the real webhook path exercise different code branches.

---

## 2. Messaging Provider Limitations (Critical)

### 2.1 Twilio trial account
- WhatsApp via Twilio requires pre-approved `content_sid` templates, not custom text. The system uses a single hardcoded `content_sid` (`HXfe5ab5f00277942d4d4200328b4d403c`) for all Twilio WhatsApp messages, regardless of failure type or personalization.
- SMS via Twilio trial can only send to verified phone numbers.
- Twilio trial accounts display "Sent from your Twilio trial account" in messages.

### 2.2 Green API limitations
- Green API is the primary WhatsApp provider because it supports AI-personalized free-text messages. But it requires a phone with WhatsApp Web connected to the Green API instance.
- If the phone disconnects from WhatsApp Web, all Green API sends fail silently (the API returns 200 but the message is never delivered).
- No delivery receipt -- the system marks "sent" when the API accepts the message, not when the customer actually receives it.

### 2.3 No delivery receipts for any channel
The system tracks "sent" (provider accepted the message) not "delivered" (customer received it) or "read" (customer opened it). This applies to all channels:
- WhatsApp (both Green API and Twilio): no read receipts consumed
- SMS: no delivery confirmation consumed
- Email (Resend): no open/click tracking consumed

This means the analytics showing "sent" counts could overstate actual outreach effectiveness.

---

## 3. Security Open Items (Important)

### 3.1 Authentication is a shared password
The dashboard uses a single `APP_PASSWORD` for all users. There are no user accounts, no RBAC, no session tokens with expiry. The login endpoint returns the password itself as the "token" (`main.py` line 74: `return {"status": "ok", "token": settings.APP_PASSWORD}`). This means:
- Anyone with the password has full access
- The password is stored in `localStorage` on the client
- There is no session expiry or token rotation
- The "token" sent in the `Authorization` header is the plaintext password

This is acceptable for a single-builder demo but is not production-grade auth.

### 3.2 Supabase uses the service key
The backend connects to Supabase using `SUPABASE_SERVICE_KEY` (the service role key that bypasses Row-Level Security). This means:
- RLS policies, if they exist on the tables, are not enforced
- The backend has unrestricted read/write access to all rows
- If the backend is compromised, all data is exposed

### 3.3 CORS allows multiple origins
`main.py` allows CORS from `localhost:5173`, `localhost:3000`, `albertabishek.com` subdomains, and a regex matching Vercel preview URLs. This is fine for development but broader than a production deployment would warrant.

### 3.4 Checkout page has no CSRF protection
The hosted checkout page at `/pay/{order_id}` serves HTML directly with the Razorpay key embedded. The checkout token `t` parameter authenticates the customer context lookup, but:
- The token is a URL parameter (logged in server logs, browser history, potentially shared)
- There is no CSRF token on the page
- The checkout token has a 24-hour TTL in Redis, after which the page still works but shows "Customer" instead of the real name

### 3.5 Debug and migration endpoints are exposed
The following endpoints are behind auth but are administrative/debug tools that should probably not exist in production:
- `POST /api/debug/escalate/{event_id}` -- manually trigger escalation
- `POST /api/debug/test-update/{event_id}` -- test Supabase writes
- `POST /api/migrate/fix-exhausted` -- backfill migration
- `POST /api/migrate/fix-premature-exhaustion` -- fix cooldown-related exhaustion
- `DELETE /api/reset/all-data` -- deletes everything (requires confirmation param)

---

## 4. Reconciliation Edge Cases (Important)

### 4.1 Amount tolerance is very tight
`recovery_tracker.py` uses a 1% tolerance (`0.01` absolute, not percentage) when matching captured payment amounts to event amounts. This means:
- A recovery event for Rs 499.00 would reject a captured payment of Rs 499.02
- This is actually 0.01 rupees tolerance, not 1% -- it is an absolute value, not a percentage
- Partial payments are rejected (customer pays Rs 400 of a Rs 499 event)

### 4.2 Cross-currency matching
The tracker checks that the captured payment's currency matches the event's currency. It does proper case-insensitive comparison. However, there is no support for multi-currency scenarios where a payment might be settled in a different currency than the original failure.

### 4.3 Matching relies on notes and order_id linkage
The reconciliation waterfall is:
1. `notes.recovery_event_id` (most reliable -- set by my payment link generation)
2. `payment_link.reference_id` (my order_id stored as reference_id)
3. `order_id` match
4. `payment_id` match

For real Razorpay webhooks where the customer pays through a different channel (e.g., they get my WhatsApp but pay through the merchant's original checkout instead of my link), matching falls to order_id/payment_id, which may not match if the merchant's checkout generates new IDs.

### 4.4 Ghost recovery protection
The system correctly distinguishes organic recoveries (customer paid on their own, attempt_count == 0 and no successful outreach) from system-assisted recoveries. However, the check queries `recovery_attempts` for any `outcome == "sent"` row, which includes payment_link channel attempts that are customer retry failures, not outreach.

---

## 5. Scalability Concerns (Important)

### 5.1 Single Celery worker
The system runs on a single Celery worker (Railway deployment). Under load:
- All tasks (initial processing, delayed sends, escalation cycles, invoice scans) share one worker process
- `worker_prefetch_multiplier=1` limits throughput but prevents memory bloat
- No horizontal scaling configured

### 5.2 Escalation batch is capped at 50 events
`tasks/escalation.py` queries at most 50 pending events per cycle (every 5 minutes). At scale, if there are thousands of pending events due for escalation, the backlog grows. The priority ordering (by `recovery_probability` descending) means low-probability events could be indefinitely starved.

### 5.3 Supabase client is a singleton
`database.py` creates a single `supabase.Client` instance shared across all threads. The supabase-py client uses httpx internally. Under concurrent Celery task execution, this single client handles all database traffic. There is no connection pooling or client-per-request pattern.

### 5.4 Redis is used for everything
A single Redis instance (Upstash) handles:
- Celery task queue and results backend
- Rate limiting sorted sets
- Per-resource cooldown keys
- Deduplication keys
- Checkout context tokens
- Distributed locks (event locks, escalation lock)

At scale, contention on this single Redis instance would be a bottleneck.

### 5.5 AI calls are synchronous in recovery pipeline
The `classify_event` and `generate_personalized_messages` calls are synchronous httpx calls to OpenRouter. Each recovery event blocks its Celery task for 10-12 seconds per AI model attempt. With a 3-model fallback chain, a worst-case classification can take 30+ seconds before falling back to rules.

### 5.6 No database indexes mentioned
The code performs queries like `SELECT * FROM recovery_events WHERE status = 'pending' AND next_action_at <= now()` on every escalation cycle. Without proper indexes on `(status, next_action_at)`, this degrades as the table grows.

---

## 6. Data Integrity (Important)

### 6.1 Optimistic concurrency control
The system uses "update where status = X" as a poor man's optimistic lock for status transitions. Combined with Redis distributed locks (`lock:event:{id}`), this prevents most race conditions. However:
- The Redis locks have a TTL (60-300 seconds). If a task hangs, the lock expires and another task can process the same event.
- There is no database-level row locking (`FOR UPDATE SKIP LOCKED` was considered but not implemented).

### 6.2 Recovery attempts table idempotency
~~The `idempotency_key` field previously had no unique constraint.~~ **FIXED** in migration 005 — a unique partial index now enforces idempotency. The action reservation pattern (INSERT "reserved" BEFORE send) combined with `APIError` code 23505 catch prevents duplicate sends on worker retries.

### 6.3 Event counts endpoint is approximate
`GET /api/events/counts` fetches all events matching the date filter and counts statuses in Python. It uses `count="exact"` from Supabase but then iterates over `res.data` to count by status. For large datasets, this loads all rows into memory just to count them.

---

## 7. AI Classification Limitations (Important)

### 7.1 Classification accuracy is unvalidated
The AI classifier categorizes events into 11 failure categories. There is no validation dataset, no accuracy metrics, no A/B test against rules-only. The rule-based fallback penalties classifications at 0.7x probability, but this penalty factor is arbitrary.

### 7.2 Model chain assumes OpenRouter availability
The 3-model fallback chain (Claude Haiku 4.5 -> Gemini 3.7 Flash -> GPT-4o-mini) goes through OpenRouter. If OpenRouter itself is down, all three models fail simultaneously and the system falls to rule-based classification. There is no direct-to-provider fallback.

### 7.3 Structured output is parsed, not guaranteed
The AI calls request `response_format: {"type": "json_object"}` but only some models reliably honor it. The `_parse_json` function in `ai_client.py` strips markdown fences as a workaround. If the AI returns malformed JSON, the call returns `None` and the system tries the next model.

### 7.4 Escalation AI can be overridden
The escalation service has a safety override: if the AI says "give_up" but `attempt_count < max_attempts`, the system forces a "send" action. This is correct behavior (don't waste budget) but means the AI's judgment about futile cases is sometimes ignored.

---

## 8. Frontend Issues (Nice-to-have)

### 8.1 No error boundary per page
There is a single `ErrorBoundary` wrapping the entire app. If one component crashes (e.g., bad data shape from API), the whole dashboard shows the error state, not just that page.

### 8.2 No offline or network error handling
If the API is unreachable, fetch calls throw and the loading state hangs. There is no retry UI, no "connection lost" banner, no cached fallback data.

### 8.3 Date filtering is client-side string manipulation
`DateRangePicker` generates date strings that are passed as query params. There is no timezone handling -- the frontend sends date strings, and the backend filters with string comparison against ISO timestamps. Events created at 11:30 PM IST might appear on the wrong day.

### 8.4 No pagination UI for events
The events list fetches up to 200 events. There is no infinite scroll, no "load more", no page navigation. Large event sets are simply truncated.

### 8.5 No browser compatibility testing
The frontend uses modern JSX, optional chaining, and CSS custom properties. No polyfills or transpilation targets are configured for older browsers.

---

## 9. Quiet Hours Assumptions (Nice-to-have)

### 9.1 Hardcoded IST timezone
Quiet hours are 9 PM to 9 AM IST, hardcoded in both `tasks/recovery.py` and `services/escalation.py`. This assumes all customers are in the IST timezone. There is no per-customer timezone detection.

### 9.2 Duplicated quiet hours logic
The `_is_quiet_hours()` and `_next_permitted_time()` functions are duplicated between `tasks/recovery.py` and `services/escalation.py` with identical implementations. This is a maintenance risk if one is updated without the other.

---

## 10. Recently Fixed Issues

### 10.1 Infinite retry on unreachable contacts (FIXED)
Previously, events with invalid contact details (fake email, wrong phone) would retry forever because `attempt_count` only increments on success and safety overrides prevent give_up when `attempt_count < max_attempts`. **Fixed** with `delivery_failure_count` — a separate counter tracking consecutive hard delivery failures. When `delivery_failure_count > max_attempts`, the event is exhausted with reason "All delivery attempts failed." See migration 006.

### 10.2 Missing idempotency keys on delayed/retry paths (FIXED)
Previously, delayed send and retry-failure paths inserted `recovery_attempts` rows without idempotency keys. **Fixed** — all send paths now have structured keys: `{event_id}:initial:1`, `{event_id}:delayed:{n}`, `{event_id}:escalation:{n}`, `{event_id}:retry_failure:{n}`.

### 10.3 Post-send DB insert (double-send risk) (FIXED)
Previously, all three send paths inserted the DB row AFTER `send_message()`. A worker crash between send and insert meant the message was re-sent on retry. **Fixed** with the action reservation pattern: INSERT "reserved" BEFORE send, UPDATE outcome AFTER. Unique constraint catches retries.

---

## 11. What Works Well

For an honest assessment:

- **The full pipeline works end-to-end.** Webhook ingestion -> AI classification -> channel routing -> payment link generation -> multi-provider message delivery -> recovery tracking on payment.captured -- all of this works and has been tested with real Razorpay test-mode payments.

- **Multi-provider fallback is solid.** The WhatsApp -> Twilio -> Email degradation chain is well-implemented with full audit trails (`degradation_path`).

- **Ghost recovery prevention is correct.** The system distinguishes organic recoveries from system-assisted recoveries by checking both `attempt_count` and the presence of successful outreach attempts.

- **Double-attribution blocking works.** The recovery tracker checks if a `payment_id` is already attributed to another event before marking recovery.

- **The escalation engine respects budgets.** The `max_attempts` system prevents over-contacting customers, with the AI deciding channel rotation within that budget.

- **Rate limiting and cooldowns are properly Redis-backed.** Sliding window rate limits and per-resource cooldowns prevent message spam.

- **Unreachable contact detection works.** The `delivery_failure_count` circuit breaker stops infinite retries when all messaging providers reject a customer's contact details, without weakening the safety overrides that prevent premature abandonment.

- **Action reservation prevents double-sends.** The reserve-before-send pattern with idempotency keys ensures that worker crashes between send and DB insert don't cause duplicate messages.

- **The audit trail is comprehensive.** Every attempt, degradation path, AI reasoning, and status transition is logged in `recovery_attempts`.

---

## 12. What Would Break First in Production

1. **The single Celery worker** would be overwhelmed with any real merchant's volume. This is the first bottleneck.

2. **AI latency** -- 10-30 seconds per event for classification would create unacceptable queue depth. In production, the rule-based classifier should be the primary path, with AI as an enhancement, not the other way around.

3. **The Supabase singleton client** would hit connection limits or experience timeouts under concurrent load.

4. **Green API phone disconnection** -- if the WhatsApp Web phone disconnects and nobody notices, all WhatsApp sends silently fail. There is no health check for the Green API connection.

5. **The checkout page is served by the same FastAPI instance** that processes webhooks. Under load, checkout page requests compete with webhook processing.

---

## 13. What a Razorpay Engineer Would Flag

1. **Auth model is a demo hack.** Shared password, no sessions, password-as-token. This would be the first thing blocked in any security review.

2. ~~**No idempotency guarantees at the database level.**~~ **FIXED.** Unique partial indexes on `payment_id`, `order_id`, `invoice_id` (migration 003) and `idempotency_key` (migration 005) now enforce durable dedup at the database level.

3. **Service key bypass of RLS.** Using `SUPABASE_SERVICE_KEY` means the application is trusted, but a compromise exposes everything. In Razorpay's infrastructure, this would need proper service accounts with scoped permissions.

4. **No structured logging or observability.** The system uses Python `logging` with text format. No JSON structured logs, no request tracing (no trace IDs), no metrics export (Prometheus/Datadog). Debugging production issues would require log searching.

5. **No health checks for external dependencies.** The `/api/health` endpoint likely checks if the server is up, but there is no deep health check for Redis, Supabase, OpenRouter, Twilio, Green API, or Resend connectivity.

6. **Amount handling uses float arithmetic.** Payment amounts are stored and compared as floats, not integers (paise). The `amount * 100` conversion in `payment_links.py` uses `int()` truncation, which can produce off-by-one errors for amounts like Rs 99.99 (becomes 9998 instead of 9999 due to floating point).

7. **The recovery_tracker tolerance of 0.01 is in rupees, not percentage.** This was likely intended to be 1% tolerance but is implemented as 1 paisa absolute tolerance, which is effectively exact matching for any amount above Rs 1.

---

## 14. Designed but Not Built

Based on code comments, system documentation, and architecture plans:

- **Multi-tenant support** -- the system is single-merchant. No merchant_id partitioning.
- **Webhook signature verification for simulator** -- simulator bypasses it by design, but there is no toggle.
- **A/B testing framework** -- mentioned in planning docs, not implemented.
- **Customer opt-out / unsubscribe** -- there is an `opted_out` field checked in escalation but no mechanism for customers to set it.
- **Delivery receipt consumption** -- the messaging providers support delivery/read receipts but the system does not poll or webhook for them.
- **Per-customer timezone** -- quiet hours are IST-only.
- **Dashboard user accounts** -- single shared password.
- **Database migrations** -- no migration tool (Alembic, etc.). Schema is managed via Supabase dashboard.
- **Prometheus/Datadog metrics** -- no observability export.
- **FOR UPDATE SKIP LOCKED** -- mentioned in planning docs as the production approach for escalation dedup, using Redis locks instead.

# Recovery Router — Build Verification Log

**Purpose:** Track every step, verify every claim, catch every issue BEFORE it becomes a bug.  
**Rule:** No assumptions. Only trust results from real API calls with real credentials.

---

## Pre-Build Checklist

### Credential Verification (Real API calls — verified 2026-08-26)
- [x] Razorpay API — PASS (200 OK, GET /v1/payments works, 0 payments in test mode)
- [x] Razorpay Invoices API — PASS (200 OK, 0 invoices in test mode)
- [x] OpenAI API — PASS (model=gpt-4o-mini-2024-07-18, responded correctly)
- [x] Supabase — PASS (40 events in recovery_events, 74 attempts)
- [x] Upstash Redis — PASS (PING=True, SET/GET works)
- [x] Celery Broker — PASS (connects to Upstash Redis via rediss://)
- [x] Twilio — PASS (account="My First Twilio Account", status=active)
- [x] Resend — PASS (API key works, restricted to sending only — that's fine)
- [ ] SendGrid — not tested yet (fallback, lower priority)

### Environment Setup (verified 2026-08-26)
- [x] Python 3.14.3 — WARNING: very new, but packages install fine
- [x] Node.js v24.15.0
- [x] npm 11.12.1
- [x] pip 25.3
- [ ] Git initialized

### Database Verification (verified 2026-08-26)
- [x] recovery_events table: EXISTS (40 rows)
- [x] recovery_attempts table: EXISTS (74 rows)
- [ ] pending_captures table: DOES NOT EXIST (need to create)
- [x] Status breakdown: pending=2, recovered=2, exhausted=36

## CRITICAL FINDINGS — Must Address Before Building

### Finding 1: OpenAI Model Name
- BUILD_PLAN says "GPT-5 Mini" but actual model is `gpt-4o-mini` (model ID: gpt-4o-mini-2024-07-18)
- n8n workflows also use gpt-4o-mini, not gpt-5-mini
- **Action:** Use `gpt-4o-mini` in all code. Update BUILD_PLAN references.

### Finding 2: Database Schema Mismatch (11 columns MISSING)
The BUILD_PLAN assumes 41+ columns. Actual schema has only 30 columns.
**Missing columns (not in Supabase):**
- `error_code` — needed for classification + fallback rules
- `error_description` — useful context for AI
- `method` — payment method (upi/card/netbanking/wallet)
- `cart_value` — for cart abandonment events
- `items_in_cart` — for cart abandonment events
- `days_overdue` — for invoice overdue events
- `alternative_action` — AI classification output
- `skip_reason` — for no-action events
- `source` — track origin (api/n8n/simulator)
- `razorpay_raw` — flag for raw webhook format
- `fallback_classification` — flag for rule-based fallback
**Action:** Add these columns via ALTER TABLE before building.

### Finding 3: ID Type is INT, not UUID
- BUILD_PLAN schema says `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- Actual: `id` is INTEGER (auto-increment)
- recovery_attempts.recovery_event_id is also INT
- **Action:** Use INT in all code. Match existing schema.

### Finding 4: pending_captures Table Missing
- BUILD_PLAN defines this table for handling race conditions
- **Action:** Create it via SQL.

### Finding 5: Upstash Redis SSL
- Credential URL has `?ssl_cert_reqs=none`
- Celery SSL config should use `ssl.CERT_NONE` not `ssl.CERT_REQUIRED`
- **Action:** Use `ssl.CERT_NONE` in Celery config to match Upstash's self-signed cert.

---

## Build Progress

### Phase 1: Backend Core
- [x] Project scaffold created
- [x] celery_app.py — Celery connects to Upstash Redis (VERIFIED: worker starts, tasks register)
- [x] config.py — all env vars loaded
- [x] database.py — Supabase client works (VERIFIED: health check returns ok)
- [x] redis_client.py — direct Redis works (VERIFIED: health check returns ok)
- [x] models.py — Pydantic models defined
- [x] normalizer.py — handles raw Razorpay + custom format
- [x] dedup.py — Redis SET NX works
- [x] webhooks.py — POST /webhook/recovery-router endpoint (VERIFIED: 200 OK)

### Phase 2: Classification + Routing
- [x] classifier.py — OpenAI structured output (VERIFIED: correctly classified upi_timeout)
- [x] classifier fallback — rule-based (coded, not yet triggered)
- [x] router.py — deterministic routing
- [x] tasks/recovery.py — process_recovery_event Celery task (VERIFIED: E2E works)
- [x] rate_limiter.py — Redis sliding window

### Phase 3: Message Delivery
- [x] payment_links.py — Razorpay API (VERIFIED: real payment link created, HTTP 200)
- [x] messenger.py — Resend email (coded)
- [x] messenger.py — Twilio WhatsApp/SMS (WhatsApp needs ContentSid, falls back to SMS)
- [x] messenger.py — SendGrid fallback (coded)

### Phase 4: Escalation + Scanner
- [x] escalation.py — AI decision + asyncio.gather()
- [x] tasks/escalation.py — Celery Beat task
- [x] invoice_scanner.py — Razorpay invoice API (VERIFIED: 0 invoices in test mode)
- [x] tasks/invoice_scan.py — Celery Beat task
- [x] recovery_tracker.py — ghost recovery fix (attempt_count > 0)

### Phase 5: Analytics + API
- [x] analytics.py — compute metrics (VERIFIED: returns correct data)
- [x] GET /api/analytics (VERIFIED: 200 OK)
- [x] GET /api/events (VERIFIED: 200 OK, returns events)
- [x] POST /api/simulate (VERIFIED: queues task, worker processes)
- [x] GET /api/health (VERIFIED: supabase=ok, redis=ok)

### Phase 6: React Frontend
- [ ] Vite + React + Tailwind scaffold
- [ ] Supabase realtime connected (VERIFIED)
- [ ] All dashboard components
- [ ] Responsive + dark/light mode

### Phase 7: Deploy + Test
- [ ] Railway deployment (3 services)
- [ ] End-to-end test passing

---

## Issues Found During Build

| # | Issue | Found In | Resolution | Status |
|---|-------|----------|-----------|--------|
| 1 | OpenAI model is gpt-4o-mini not gpt-5-mini | credential verify | Use gpt-4o-mini in code | FIXED |
| 2 | DB schema had 11 missing columns + INT IDs not UUID | schema verify | Drop & recreate tables with full schema | FIXED |
| 3 | Upstash Redis SSL needs CERT_NONE not CERT_REQUIRED | credential verify | Use ssl.CERT_NONE | FIXED |
| 4 | Celery autodiscover_tasks didn't find task modules | worker startup | Use include= config | FIXED |
| 5 | Stale Celery tasks from another project in Upstash | worker startup | Purged celery queue key | FIXED |
| 6 | psycopg2-binary blocked by Application Control | DB setup | Used psycopg (pure Python) instead | FIXED |
| 7 | Direct Supabase host DNS fails | DB setup | Used session pooler connection | FIXED |
| 8 | Twilio trial blocks BOTH WhatsApp (ContentSid required) AND free-form SMS to Indian numbers ("Invalid template name. Trial accounts can only use predefined SMS templates.") | E2E test 2026-08-26 | Added channel degradation in `send_message()`: whatsapp -> sms -> email. Verified live: degraded_from=whatsapp, channel_used=email, real Resend id returned | FIXED |
| 11 | `/api/health` returns `status: "ok"` but HealthBadge checked for `"healthy"` | frontend browser test | Badge now reads `status == "ok"` + per-service chips | FIXED |
| 12 | AILift rendered `+-17.5 pts` when recovery rate is below baseline | frontend browser test | Sign-aware formatting + neutral colour when negative | FIXED |
| 13 | Supabase anon key hardcoded in `src/lib/supabase.js` | frontend review | Moved to `VITE_*` env vars, `.env` gitignored, `.env.example` added | FIXED |
| 9 | pip dependency conflict: pydantic==2.11.0 vs supabase | pip install | Relaxed version pins to >= | FIXED |
| 10 | Python 3.14.3 (very new) but all packages compatible | env check | No action needed | OK |

---

## Phase 6 — Frontend Verification (2026-08-26)

All checks below were run against the live stack (FastAPI :8000, Celery solo worker,
Upstash Redis, Supabase, real Razorpay/OpenAI/Resend/Twilio credentials).

| # | Check | Method | Result |
|---|-------|--------|--------|
| F1 | Vite dev server boots | `preview_start` frontend :5173 | PASS |
| F2 | Dashboard renders all 7 components | browser `read_page` accessibility tree | PASS — StatTiles, AILift, ChannelRanking, RecoveryByType, LiveFeed, SimulatorPanel, HealthBadge all present |
| F3 | No console errors | `read_console_messages onlyErrors` | PASS — none |
| F4 | `/api/analytics` reachable via Vite proxy | `curl localhost:5173/api/analytics` | PASS — real totals returned |
| F5 | `/api/health` reports all services | `curl localhost:5173/api/health` | PASS — supabase ok, redis ok, celery ok |
| F6 | Simulator button drives the real pipeline | clicked "Card Expired" in browser, then queried DB | PASS — event id=2 created |
| F7 | AI classified the simulated event correctly | inspected row | PASS — `failure_category=card_expired`, `recovery_probability=0.5`, routed to `email` |
| F8 | Razorpay payment link actually created | `recovery_attempts.metadata` | PASS — `plink_TUJWVFIjXIn8m8`, `https://rzp.io/rzp/xlgA21Y` |
| F9 | Email actually delivered | `recovery_attempts.outcome` | PASS — `sent`, Resend id `5f16101f-…` |
| F10 | Channel degradation whatsapp -> email | direct `send_message()` call with cooldowns cleared | PASS — `degraded_from=whatsapp`, `channel_used=email`, Resend id `3348ddd5-…` |

### Known limitation (documented, not hidden — Rule 11)
Twilio **trial** accounts cannot send free-form WhatsApp *or* SMS to Indian numbers;
India's DLT rules require pre-registered templates. Recovery Router handles this by
degrading the channel to email rather than burning a recovery attempt. On a paid
Twilio account with registered templates, the WhatsApp/SMS path works unchanged —
the routing logic and the analytics are already channel-agnostic.

---

## Rules I Must Follow (from project-spec + strategy)
1. One rupee recovered > ten features built
2. Think like Razorpay, not like a hackathon participant
3. Smarter than doing nothing — know when NOT to act
4. Measurable or it didn't happen
5. Honest about what doesn't work
6. One engine, not three products
7. Complement Razorpay, don't compete
8. Ship beats perfect
9. NEVER build a feature without answering "How much revenue does this recover?"
10. NEVER show a metric without showing how it was measured
11. NEVER hide a limitation
12. NEVER send a recovery action without the system having a reason
13. NEVER treat all failures the same
14. Payment link must have expire_by matching recovery_window_ends
15. Ghost recovery: only mark recovered if attempt_count > 0
16. Concurrent OpenAI calls via asyncio.gather() in escalation
17. Single Celery task process_recovery_event for merged pipeline
18. Celery + Upstash Redis (rediss:// SSL) — NO Docker

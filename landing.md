# Recovery Router - Submission Landing Page Content

> **Razorpay AI Buildathon 2026 - Track 3: AI Revenue Recovery**
> Built by Albert Abishek I

---

## Section 1: HERO

### Headline
**What happens after a payment fails?**

### Running Text Ticker
`UPI timed out... Card declined... Cart abandoned... Invoice overdue... Insufficient funds... Gateway error... Bank downtime... Subscription lapsed...`

### Tagline
**Vulcan routes payments. Recovery Router routes failures.**

### One-liner
An AI-powered engine that classifies every revenue leak, routes it to the optimal recovery action, and executes through the right channel at the right time - with honest metrics that never inflate results.

### CTA Buttons
- **Live Demo** → razorpay.albertabishek.com
- **API Docs** → api.albertabishek.com/docs
- **GitHub** → github.com/albertabishek/Recovery-Router-

---

## Section 2: THE PROBLEM - Why This Track Exists

### The Scale of Revenue Leakage in India

| Metric | Number | Source |
|--------|--------|--------|
| D2C payment success rate | 68–74% average | Razorpay "Payment Success Rate Optimization India" guide, May 2026 |
| Cart abandonment cause | 70% caused by payment failures | Same Razorpay article, May 2026 |
| Customers who won't return after card decline | 40% | Same Razorpay article, May 2026 |
| Automated retry recovery rate | 15–20% of failed transactions | Same Razorpay article, May 2026 |
| Vulcan improvement | 8–10% better success rates | razorpay.com/foundation-model |

### What Exists Today - And Why It's Not Enough

**Razorpay's current arsenal:**
- **Vulcan** (Aug 2026): India's first transformer-based AI model for payments. Trained on 4B transactions, 3T data points, ~3,000 signals per transaction. Improves payment *success* rates by 8–10%. Hyper-precision routing, fraud detection, RTO risk intelligence.
- **Agent Studio** (Mar 2026): World's first AI Agent Studio for payments, built on Anthropic's Claude Agent SDK. 8 pre-built agents including Dispute Responder, Subscription Recovery, Abandoned Cart Conversion, Cashflow Forecaster.
- **Failed Payment Recovery**: Existing product for subscription payment recovery via WhatsApp reminders and incentive-led nudges.

**The gap:** Vulcan optimizes the *before* - making payments succeed. But when they don't? There's no unified, intelligent system that understands *why* a payment failed and routes the failure to the right recovery action through the right channel at the right time. Agent Studio provides building blocks, but not a complete classify-route-act-measure pipeline across all three revenue leak types.

### The Global Landscape - How Others Handle It

**Stripe (Global leader in recovery):**
- **Combined Billing tools** (Smart Retries + automatic card updates + recovery automations): Stripe reports **55% of failed payments recovered on average** using the combined suite
- Smart Retries uses ML models trained on billions of data points to choose optimal retry timing
- Pre-dunning card updater proactively refreshes expired cards before they fail
- **Limitation**: Template-based dunning emails only, no SMS/WhatsApp/in-app, retry logic and dunning operate independently rather than as a coordinated sequence

**PayPal:**
- Rigid retry: every 5 days, up to twice per billing cycle, fixed schedule
- No native dunning email automation - merchants build their own
- Partners with FlexFactor for ML-based recoverability scoring (not native)
- **Limitation**: No merchant control, no multi-channel outreach

**Adyen:**
- **Auto Rescue**: ML-powered retry for recurring payments, uses reinforcement learning to optimize retry timing
- Uses **contextual multi-armed bandits** - one of the most technically sophisticated retry approaches globally
- **Limitation**: Retry-only focus, dunning communication left entirely to merchants

**Lemon Squeezy:**
- Auto-retries 4 times over 2 weeks, sends dunning emails at each failure
- Simple, opinionated, free - good for indie devs
- **Limitation**: No ML, email-only, no analytics on recovery performance

**Square:**
- Fixed retry: every 3 days for 9 days, no configuration, no ML, no dunning emails
- Most basic recovery among major processors

**Cashfree (India):**
- "Relay" AI agent for retrying failed payments, abandoned cart follow-up, failed subscription management
- Intelligent routing through best-performing acquirer
- Real-time bank outage monitoring
- Direct competitor in the Indian payment recovery space

**Juspay (India):**
- Payment orchestration router across 150+ countries
- Smart retry logic: only retries soft declines (insufficient funds, issuer timeouts)
- Focuses on *which* declines to retry vs. not
- Orchestration layer, not a recovery engine

**Chargebee / Recurly / Zuora (Global SaaS billing):**
- **Chargebee**: 30–40% native recovery, pre-dunning workflows recover an additional 15–22%
- **Recurly**: Claims **70–80% recovery rate** with Intelligent Dunning ML
- **Zuora**: Reports SaaS companies lose **9–12% of MRR annually** without dunning automation
- All subscription-only - no one-time payment recovery, no cart abandonment

### Global Industry Benchmarks

| Metric | Number |
|--------|--------|
| Global cost of failed payments annually | **$440 billion** |
| Involuntary churn share of all subscriber losses | **Over 50%** |
| Industry median recovery rate | **47.6%** |
| Best-in-class layered recovery programs | **70–85%** |
| AI/ML uplift over native billing retry | **2–4x improvement** |
| Failure breakdown: insufficient funds (soft decline) | ~50% |
| Failure breakdown: risk management (hard flag) | 25–33% |
| Failure breakdown: card issues (expired, lost) | 10–15% |

### What's Missing Globally - The Gaps

1. **Retry-dunning coordination**: Most platforms treat retries and customer emails as independent systems that sometimes compete with each other
2. **Multi-channel outreach**: Almost everyone is email-only. SMS, WhatsApp, in-app are absent or require third-party integrations
3. **Decline-code intelligence**: Different decline codes need different responses, but most platforms apply the same dunning sequence regardless
4. **Cross-leak-type coverage**: Everyone specializes - subscriptions OR carts OR invoices. Nobody does all three in one pipeline
5. **Personalized messaging**: Template-based dunning emails are the norm. AI-personalized, channel-specific messages are largely unsolved

**The pattern:** Everyone focuses on *retry mechanics* - when to retry the same payment method. Nobody combines diagnostic intelligence (understanding *why* it failed) with personalized multi-channel recovery (right channel, right message, right timing, right number of attempts) across all three revenue leak types in a single engine. Recovery Router fills this gap.

---

## Section 3: MY JOURNEY - From Hackathon Post to Production System

### Discovering the Buildathon
I saw the Razorpay AI Buildathon announcement and immediately went to study the problem statements. Track 3 - AI Revenue Recovery - wasn't just a coding challenge. It was Razorpay admitting they had a gap in their own product ecosystem.

### The Research Phase - Thinking Like a Razorpay Engineer
Before writing a single line of code, I spent time understanding:

1. **Razorpay's product ecosystem** - Vulcan, Agent Studio, Smart Collect, Payment Links, Magic Checkout. What does each solve? Where do they intersect? Where are the gaps?

2. **Why they posed this problem** - Vulcan had just launched (Aug 2026), Agent Studio in March. They had optimized the *success* path. But the *failure* path - what happens after a payment fails - was still fragmented. Separate tools for separate leak types, no unified intelligence.

3. **The competitive landscape** - Studied Stripe's Smart Retries, Cashfree's Relay, Juspay's orchestration. Everyone focuses on retry mechanics. Nobody does diagnostic intelligence + personalized recovery.

4. **Industry data** - 68–74% D2C success rates, 70% of cart abandonment caused by payment failures, 40% of customers won't return after a decline (all from Razorpay's 2026 guide). The numbers made the ROI case obvious.

5. **Other Track 3 submissions** - Researched 25 entries and 12 public repositories. Most were building simple retry bots or basic WhatsApp notification systems. None were thinking about the unified pipeline problem.

### The Core Insight
> "Vulcan routes payments. Recovery Router routes failures."

This became the north star. Not a standalone tool, but something that *completes* Razorpay's ecosystem - the missing piece that handles everything after a payment fails.

### Prototyping with n8n
Started with 5 n8n workflows as a rapid prototype:
- Recovery Router (15-node webhook-to-send pipeline)
- Invoice Overdue Scanner (6h cron)
- Recovery Tracker (payment.captured matching)
- Escalation Agent (5-min AI decision loop)
- Recovery Analytics API

These proved the logic worked. But n8n was too limited for production reliability - no distributed locking, no race condition handling, no proper deduplication. The n8n workflows would later come back to haunt us (Section 7).

### The Full Rebuild
Rebuilt everything as a proper six-component architecture: FastAPI + Celery Worker + Celery Beat + React Frontend + Redis + Supabase. Every operation runs through the real async pipeline - no shortcuts, no mocks, no tricks.

---

## Section 4: MY THINKING PRINCIPLES

### 1. "Without ROI, there will be no features"
Every feature had to justify its existence through measurable impact. I rejected a Promise-to-Pay (PTP) feature suggestion because it added complexity without clear recovery rate improvement. I rejected a "feature-rich" dashboard approach in favor of fewer, high-impact capabilities.

**What I intentionally avoided:**
- Complex ML models that couldn't be explained to a merchant
- Features that look impressive in demos but add no recovery value
- Over-engineering the AI - rule-based fallback exists because reliability > sophistication
- Vanity metrics - organic recoveries are tracked separately, never inflated
- Claiming "delivered" when we only know "sent" - the system tracks provider acceptance, not delivery receipts

### 2. Think Like You Already Work There
I cloned Razorpay's actual UI - not because it's pretty, but because it makes judges see Recovery Router as a native feature, not a hackathon toy. I used their design tokens, their SVG icons, their color system, their layout patterns. When you look at the dashboard, it feels like it already belongs in Razorpay's product suite.

### 3. Honest Metrics Over Impressive Numbers
Ghost recovery prevention: if a customer pays organically (no outreach was sent), it's logged as `organic_recovery`, not `recovered`. The system separates organic from outreach-driven recovery - only events where messages were actually sent count toward recovery metrics. This is the metric a product manager at Razorpay would trust.

### 4. Safety First - It's Financial Software
Every security decision was made with the awareness that this handles real money:
- HMAC-SHA256 webhook verification with timing-safe comparison
- XSS prevention on checkout pages (regex-validated order IDs)
- AI input sanitization to prevent prompt injection
- Rate limiting on every endpoint
- Per-event distributed locks to prevent race conditions
- Three-layer defense against premature give-up
- Server-side PII - customer data never appears in URLs
- Database trigger as last line of defense against external writers

### 5. Real Architecture, Not Demo Architecture
"Everything will be async. Use Celery, workers, everything - no tricks."
- `task_acks_late=True` - tasks aren't acknowledged until complete
- `task_reject_on_worker_lost=True` - tasks requeue on worker crash
- Exponential backoff on transient failures (60s → 120s → 240s)
- Distributed Redis locks serialize concurrent event processing
- Conditional database updates prevent TOCTOU race conditions

---

## Section 5: WHAT I BUILT - The Solution

### One Engine, Three Leak Types

| Revenue Leak | How It Enters | What Happens |
|-------------|---------------|-------------|
| Payment Failures | Razorpay `payment.failed` webhook | Auto-classified into 12 categories, AI picks the optimal recovery path |
| Cart Abandonment | Merchant POST to `/webhook/recovery-router` | Classified by intent (high intent vs browse-only), only high-value carts get outreach |
| Overdue Invoices | Invoice scanner polls Razorpay API every 6h | Classified by days overdue, escalation tone matches urgency |

**Two entry paths:**
- **Real webhooks** (`/webhook/recovery-router`): HMAC-SHA256 signature verification + Redis deduplication (1h TTL) + normalization → full pipeline
- **Simulator** (`/api/simulate`): Creates synthetic events and queues Celery tasks directly - no signature verification, no dedup (designed for testing, not production ingestion)

### The Pipeline: Classify → Route → Act → Measure

**Step 1: Classify (AI)**
3-model fallback chain via OpenRouter: Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini. Rule-based fallback if all AI fails (the system never blocks on AI). Each event is classified into one of 12 categories with a recovery probability estimate.

**Step 2: Route (Dynamic Budgets)**
`max_attempts` is computed per event - not a fixed 5 for everyone:
- High-value UPI timeout → 5 attempts (high probability, high value)
- Browse-only cart abandonment → 0 attempts (no ROI in chasing)
- User-cancelled → 2 attempts (respect the customer's signal)
- Insufficient funds, small amount → 1–2 attempts

**Step 3: Act (Multi-Channel)**
AI generates personalized messages for each channel:
```
WhatsApp: Green API (personalized text) → Twilio WhatsApp (template) → Email fallback
SMS: Twilio SMS → WhatsApp fallback → Email fallback
Email: Resend with AI-personalized HTML, branded template
```
Every provider attempt is logged in the `degradation_path` for full audit trail.

**Step 4: Measure (Honest Metrics)**
- Recovery reconciliation: 4-strategy matching (notes → reference_id → order_id → payment_id)
- Ghost recovery prevention: organic payments (no outreach sent) tracked separately, never counted as recovered
- Double-attribution prevention: unique `recovered_payment_id` index
- Currency match, amount tolerance (1%), entity status validation
- Tracks provider acceptance ("sent"), not delivery receipts - delivery tracking not yet integrated

### Escalation Engine (AI-Driven, Every 5 Minutes)
The AI analyzes full attempt history - which channels were tried, what succeeded/failed, what's left - and decides:
- Next channel and tone (friendly → firm → urgent → final)
- Whether to continue or give up
- Three-layer safety: schema default → AI override → hard guard
- Quiet hours: no messages 9 PM – 9 AM IST
- 72-hour recovery window with 24-hour extension for active events
- Per-resource cooldowns (5 min per phone/email) prevent customer fatigue

### Self-Hosted Checkout & Live Payment
Razorpay Payment Links API has a 30-link test-mode limit. We bypassed this with:
- Razorpay Orders API (unlimited) + self-hosted checkout page at `/pay/{order_id}`
- Server-side PII: customer details stored in Redis with 24h-TTL token
- XSS-safe: regex-validated order IDs, `json.dumps` JS escaping
- **Try Live Payment**: real Razorpay test-mode checkout in the Simulator - creates actual orders via Orders API, payment failure triggers webhook through the full recovery pipeline

### Dashboard (5 Pages)

| Page | What It Shows |
|------|--------------|
| **Overview** | Revenue metrics, recovery rate, channel performance, recent events feed |
| **Recovery Events** | Event list with status tabs, 420px slide-in detail panel with full pipeline visualization, attempt history, AI classification fields |
| **Analytics** | 5-card KPI strip, channel effectiveness ranking, failure category distribution, recovery by type breakdown |
| **Simulator** | 10 built-in scenarios across 3 event types, custom recipient fields, Try Live Payment with real Razorpay checkout |
| **Audit Logs** | Full recovery attempt trail with AI reasoning, provider degradation paths, delivery status, auto-refresh every 15 seconds |

### Features You Might Miss
- **Event pause/resume/cancel** - manual control over any recovery event from the detail panel
- **Health monitoring** - `/api/health` endpoint with component-level status (database, Redis, Celery, Razorpay API)
- **Full event trace** - every AI decision, provider attempt, and state transition logged and viewable
- **Recovery retry failure tracking** - failed delivery attempts recorded with error details and degradation path
- **Mobile responsive** - dashboard works on phone and tablet
- **Bulk data generator** - populate the system with test data across all event types for demo or testing

### Testing Infrastructure
- **114 automated tests** across 6 test files
- Covers: classifier accuracy, recovery pipeline, escalation logic, analytics, deduplication, webhook handling
- Tests verify AI fallback chain, dynamic budget calculation, ghost recovery prevention, and race condition handling

---

## Section 6: TECHNICAL ARCHITECTURE

### System Architecture Diagram
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
              │  Dedup (Redis + DB)     │
              │  Rate limit (sliding)   │
              │  Normalize webhook      │
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │   Celery +   │
                    │    Redis     │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                  ▼
  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐
  │  Recovery     │  │  Escalation  │  │ Invoice Scan   │
  │  Pipeline     │  │  Engine      │  │  (every 6h)    │
  │  (Celery)     │  │  (every 5m)  │  │  Razorpay API  │
  ├──────────────┤  │  AI-driven   │  │  polling       │
  │ 1. Classify  │  │  channel     │  └────────────────┘
  │ 2. Route     │  │  rotation    │
  │ 3. Pay link  │  └──────────────┘
  │ 4. AI msg    │
  │ 5. Send      │
  │ 6. Log       │
  └──────┬───────┘
         │
    ┌────┼────────────────┐
    ▼    ▼                ▼
 WhatsApp  SMS         Email
(Green→   (Twilio→    (Resend
 Twilio→   WA→         AI HTML)
 Email)    Email)
```

### Tech Stack - And Why Each Choice

| Component | Choice | Why |
|-----------|--------|-----|
| API Framework | FastAPI | Async, auto-docs (Swagger), Pydantic validation, perfect for webhook ingestion |
| Task Queue | Celery + Redis | Production-grade async, late ACK, crash recovery, periodic scheduling (Beat) |
| Database | Supabase (PostgreSQL) | Realtime subscriptions for live dashboard, row-level security, built-in REST |
| AI Gateway | OpenRouter | Single API for multiple models, automatic fallback chain, no vendor lock-in |
| AI Models | Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini | Speed + cost optimized: fastest first, cheapest last, rule-based if all fail |
| Payments | Razorpay Orders API | Unlimited orders (vs 30-link Payment Links limit), full checkout control |
| WhatsApp | Green API + Twilio | Green API for personalized text, Twilio as template fallback |
| SMS | Twilio | Industry standard, but trial limits restrict testing |
| Email | Resend | Developer-first, clean API, custom domain support |
| Frontend | React 19 + Vite 8 | Fast HMR, modern tooling, Razorpay UI clone |
| Realtime | Supabase Realtime | WebSocket-powered live event updates on dashboard |
| Cache/Locks | Redis | Dedup, rate limiting, distributed locks, PII token store |

### Security Architecture

| Layer | Protection | Implementation |
|-------|-----------|----------------|
| Webhook Ingestion | HMAC-SHA256 signature verification | Timing-safe `hmac.compare_digest()` |
| Request Validation | Body size limit (256 KB) | FastAPI middleware |
| Deduplication | Two-level: Redis + DB | Redis SET NX (1h TTL) + PostgreSQL unique partial indexes |
| Rate Limiting | Sliding window per-endpoint | Redis sorted sets: webhooks 100/min, analytics 30/min |
| AI Safety | Input sanitization | Truncation (200 chars) + control character stripping |
| Checkout Security | XSS prevention | Regex-validated order_id `^order_[A-Za-z0-9]{8,30}$` + `json.dumps` |
| PII Protection | Server-side storage | Redis with 24h-TTL token, never in URLs |
| Race Conditions | Distributed locks + optimistic concurrency | Redis NX locks (300s TTL) + conditional `.eq("status", "pending")` |
| State Integrity | Three-layer give-up prevention | Schema default → AI override → hard guard |
| External Writers | Database trigger | PostgreSQL trigger blocks premature exhaustion from ANY source |
| CORS | Explicit allowlist | Specific origins + Vercel preview regex |

---

## Section 7: WHAT BROKE & HOW I FIXED IT

*They asked for this. Here's the truth.*

### Bug #1: The Premature Give-Up
**What happened:** Events were being marked "exhausted" after just 1 attempt when they had a budget of 5.
**Root cause:** The AI escalation schema defaulted `action` to "give_up" instead of "send". The AI would sometimes return partial JSON, inheriting the destructive default.
**Fix:** Changed schema default to "send", added AI override that checks for untried channels before allowing give-up, and added a hard guard that blocks give-up when `attempt_count < max_attempts`. Three layers of defense.
**Lesson:** In financial software, a single safety check is never enough. Defense in depth.

### Bug #2: The TOCTOU Race Condition
**What happened:** After fixing Bug #1, events #16 and #17 were *still* prematurely exhausted. The code was correct - but two Celery tasks were processing the same event concurrently.
**Root cause:** `_send_delayed` (a countdown task) and the Beat escalation cycle could both pick up the same event. Task A reads status="pending", Task B reads status="pending", both proceed, one sets exhausted before the other finishes.
**Fix:** Three-pronged:
1. Conditional database updates using `.eq("status", "pending")` - optimistic concurrency control
2. Per-event Redis distributed locks (`lock:event:{id}`, 300s TTL)
3. Atomic exhaustion check in `_update_event_state` - single write for state transition
**Lesson:** Async systems need explicit serialization. "It works locally" means nothing.

### Bug #3: The Ghost Writer Mystery (⭐ The Star Story)
**What happened:** Event #18 was marked exhausted with `skip_reason=null` and `next_action_at` still set. This was an *impossible* state - our code always sets `skip_reason` when exhausting and clears `next_action_at`.
**Investigation:**
- Checked every code path. None could produce this state.
- Checked git history of every file version. The current code was correct.
- Checked Celery task results in Redis. All tasks completed correctly.
- Checked worker file timestamps vs .pyc timestamps. Code was fresh.
- Reviewed database triggers. None were modifying state.

**The breakthrough:** Checked the n8n workflows directory. Found the "Mark Exhausted" node in `Escalation Agent.json`:
```json
{"fieldsUi": {"fieldValues": [
  {"fieldId": "status", "fieldValue": "exhausted"},
  {"fieldId": "current_strategy", "fieldValue": "exhausted"}
]}}
```
No `skip_reason`. No `next_action_at = null`. No status guard. And all 5 n8n workflows were still active - writing directly to Supabase with their own credentials, completely bypassing the FastAPI backend.

**Two independent systems were racing against each other with no mutual awareness.**

**Fix:**
1. Unpublished all n8n workflows
2. Added PostgreSQL trigger (migration 004) as database-level defense:
```sql
CREATE TRIGGER trg_prevent_premature_exhaustion
  BEFORE UPDATE ON recovery_events
  FOR EACH ROW
  EXECUTE FUNCTION prevent_premature_exhaustion();
```
This blocks ANY writer (n8n, manual queries, future integrations) from marking an event exhausted when attempts remain and no skip_reason is provided.

**Lesson:** When you can't find the bug in your code, look for systems you forgot were still running. And always have a database-level safety net in financial systems.

### Bug #4: Railway Build Failures
**What happened:** Railway wouldn't build the Python backend. Three attempts:
1. Nixpacks `python311` package → `pip: command not found`
2. Added `python311Packages.pip` → `No module named pip`
3. Removed all manual Nix config, let Nixpacks auto-detect → ✅ Works

**Lesson:** Don't fight the platform. Nixpacks is designed to auto-detect Python projects from `requirements.txt`. Manual Nix package configuration was the problem, not the solution.

### Bug #5: WhatsApp Personalization
**What happened:** WhatsApp messages were sending generic Twilio templates instead of AI-personalized text.
**Root cause:** Twilio WhatsApp requires pre-approved `content_sid` templates - you can't send custom text.
**Fix:** Prioritized Green API (which supports free-form text) over Twilio WhatsApp. Twilio becomes the template-based fallback.
**Lesson:** Not all APIs are equal. Provider limitations shape architecture.

### Bug #6: The Dynamic Budget Discovery
**What happened:** The user noticed "why is everyone showing 1/5, no event is more than one attempt."
**Root cause:** Fixed `max_attempts = 5` for every event. A $50 browse-only cart abandonment got the same budget as a $30,000 failed invoice payment.
**Fix:** Dynamic `max_attempts` computed from amount, recovery probability, and failure category. Range: 0 (unrecoverable) to 5 (high-value, high-probability).
**Lesson:** One-size-fits-all is the enemy of ROI. Every attempt has a cost - balance it against recovery probability.

---

## Section 8: IMPACT & ROI

### Recovery Potential

| Metric | Before Recovery Router | With Recovery Router |
|--------|----------------------|---------------------|
| Failed payments recovered | ~0% (manual follow-up) | AI-classified into 12 categories, multi-channel recovery with dynamic budgets |
| Cart recovery rate | Industry: 5–10% | High-intent only - browse-only carts get 0 attempts, respects customer signal |
| Invoice collection improvement | Manual: weeks | Automated: starts within hours, escalation tone matches urgency |
| Customer re-engagement | 40% won't return after decline | Multi-channel outreach within optimal timing window (72h recovery window) |
| Time to first recovery action | Hours to days (manual) | Seconds to minutes (automated) |

**Note:** All metrics are from test-mode data with simulated scenarios. Production recovery rates depend on merchant volume, payment mix, and customer demographics. The system tracks provider acceptance ("sent"), not delivery receipts - delivery tracking is not yet integrated.

### What the System Tracks

| Metric | How It Works |
|--------|-------------|
| 12 failure categories | AI classifies every event with recovery probability estimate |
| 3+1 AI models | Claude Haiku 4.5 → Gemini 3.7 Flash → GPT-4o-mini + rule-based fallback |
| 114 automated tests | Across 6 test files covering the full pipeline |
| 0 ghost recoveries | Organic vs outreach-driven separation prevents inflated numbers |

### Cost Efficiency
- Dynamic budgets mean no wasted outreach on unrecoverable events
- Zero-attempt events (unrecoverable, browse-only) → zero messaging cost
- AI classification prevents spray-and-pray recovery attempts
- Per-resource cooldowns (5 min per phone/email) prevent customer fatigue and spam

### What a Razorpay Product Manager Would See
- **Honest metrics:** Organic vs outreach-driven recovery clearly separated - if no message was sent, it's marked organic, never counted as recovered
- **Channel effectiveness ranking:** Which channel recovers best, backed by data
- **Failure category distribution:** What's failing and why, across the merchant base
- **ROI per attempt:** Cost of outreach vs recovery value, per category
- **Full audit trail:** Every AI decision, provider attempt, and state change logged

---

## Section 9: DEMO

### Video
5-minute demo video - two-part demo structure with live Razorpay payment + simulated cart abandonment

### Timeline
| Timestamp | What's Shown |
|-----------|-------------|
| 0:00–0:15 | Problem statement - Razorpay's published D2C success rates, the recovery gap |
| 0:15–0:30 | The thesis - one pipeline for three leak types |
| 0:30–2:30 | **Live Payment Demo** - real Razorpay test-mode checkout, payment fails through actual gateway, webhook triggers full recovery pipeline |
| 2:30–3:10 | **Simulated Cart Abandonment** - different leak type, different AI classification, different budget and tone |
| 3:10–3:40 | Honest tracking - organic vs outreach-driven separation, provider acceptance tracking |
| 3:40–4:05 | Safety proofs - dedup rejection, escalation engine, three-layer give-up prevention |
| 4:05–4:25 | The Ghost Writer bug - best war story, database-level safety net |
| 4:25–5:00 | Limitations, open items, and close |

---

## Section 10: SCREENSHOTS GALLERY

### Dashboard Overview
[Hero revenue card, stat tiles, organic vs outreach-driven recovery comparison, channel performance, recent events feed]

### Recovery Events
[Event list with status tabs, 420px slide-in detail panel with pipeline visualization, attempt history, pause/resume/cancel controls, AI classification fields]

### Analytics / Reports
[5-card KPI strip, channel effectiveness ranking, failure category distribution, recovery by type breakdown]

### Simulator
[10 scenario cards across 3 event types, custom recipient fields, Try Live Payment with real Razorpay checkout]

### Audit Logs
[Full recovery attempt trail with AI reasoning, provider degradation paths, delivery status, auto-refresh every 15 seconds]

### Self-Hosted Checkout
[Razorpay payment modal, auto-open after 500ms, recovery_router provenance in payment notes]

### Health Monitoring
[Component-level health check: database, Redis, Celery worker, Razorpay API status]

---

## Section 11: LINKS

| Resource | URL |
|----------|-----|
| Live Dashboard | [razorpay.albertabishek.com](https://razorpay.albertabishek.com) |
| API Documentation | [api.albertabishek.com/docs](https://api.albertabishek.com/docs) |
| GitHub Repository | [github.com/albertabishek/Recovery-Router-](https://github.com/albertabishek/Recovery-Router-) |
| API Health Check | [api.albertabishek.com/api/health](https://api.albertabishek.com/api/health) |

---

## Section 12: ABOUT ME

### Albert Abishek I
**Razorpay AI Buildathon 2026 - Track 3 (Revenue Recovery)**

[Your experience, background, education - to be filled]

### Why Razorpay?
[Your personal connection to the problem, why this company, why this track - to be filled]

### Why I Built It This Way
I didn't build a hackathon project. I built what I would build if I were a Razorpay engineer assigned to solve this problem on Day 1.

- I used Razorpay's UI because it should feel like it belongs
- I focused on ROI because that's what shipping products is about
- I handled security because this is financial software
- I built async architecture because production systems need it
- I tracked honest metrics because trust is everything in fintech
- I built 114 automated tests because production systems need verification, not just demos
- I documented open items because honesty about what's unfinished matters more than pretending everything is done

### Anticipated Judge Questions

**Q: How is this different from Razorpay's existing Failed Payment Recovery product?**
A: Razorpay's existing product focuses on subscription payment recovery via WhatsApp reminders. Recovery Router handles all three revenue leaks (payment failures, cart abandonment, overdue invoices) through a unified AI pipeline with dynamic attempt budgets, multi-channel fallback, and honest metrics that distinguish organic from AI-driven recovery.

**Q: Why not use Razorpay Agent Studio to build this?**
A: Agent Studio provides building blocks. Recovery Router is the complete pipeline - classify, route, act, measure - with production-grade reliability (distributed locks, race condition handling, crash recovery, database-level safety triggers). Agent Studio agents could potentially be integrated as the messaging layer.

**Q: What's the actual recovery rate?**
A: This runs on Razorpay test-mode data with simulated scenarios. The system demonstrates the full classify-route-act-measure pipeline, but production recovery rates depend on merchant volume, payment mix, and customer demographics. The honest metrics system ensures we only count events where outreach was actually sent - organic recoveries are tracked separately and never inflated into recovery numbers. Recovery attempts track provider acceptance ("sent"), not delivery receipts, because delivery tracking is not yet integrated.

**Q: How do you handle scale?**
A: Celery workers with Redis broker support horizontal scaling. Each event is processed as an independent task. Distributed locks prevent concurrent processing of the same event. Rate limiting prevents provider and API overload. The architecture supports multiple workers with no code changes.

**Q: What about customer consent and spam?**
A: Per-resource cooldowns (5 min per phone/email) prevent over-messaging. Quiet hours (9 PM – 9 AM IST) respect customer time. Dynamic budgets limit total outreach. Browse-only cart abandonment gets zero attempts. User-cancelled events get max 2 gentle attempts. The system is designed to recover revenue, not annoy customers.

**Q: Why three AI models instead of one?**
A: Reliability. If Claude Haiku is down, Gemini takes over. If both are down, GPT-4o-mini. If all AI fails, rule-based classification keeps the system running. In financial software, the system must never block waiting for an AI provider.

**Q: What would you build next?**
A: Delivery receipt integration (track whether messages were actually opened, not just sent), Hinglish voice recovery (regional language support), merchant-specific model fine-tuning based on their payment mix, A/B testing framework for recovery strategies, and integration with Razorpay's Magic Checkout for pre-emptive failure prevention. Open items: some database migrations need finishing, RLS policies need tightening, and a few reconciliation edge cases need work.

---

## Section 13: RAZORPAY PRODUCT ANALYSIS - Where Recovery Router Fits

### The Razorpay Ecosystem (2026)

```
Before Payment         During Payment        After Payment
──────────────         ──────────────        ─────────────
Magic Checkout    →    Vulcan (AI routing)    →  ???
(Pre-fill, UX)         Smart Collect              |
                       Payment Links               |
                       Subscriptions                ▼
                                              Recovery Router
                                              (Classify → Route →
                                               Act → Measure)
```

### Product Synergies

| Razorpay Product | Recovery Router Integration Point |
|-----------------|----------------------------------|
| **Vulcan** | Vulcan optimizes routing to *prevent* failures. When failures still happen, Recovery Router takes over. Vulcan's decline signals could feed Recovery Router's classifier. |
| **Agent Studio** | Recovery Router's messaging layer could use Agent Studio agents. The escalation engine's AI decisions could power custom Agent Studio templates. |
| **Smart Collect** | Invoice recovery events from Recovery Router could trigger Smart Collect virtual accounts for B2B receivables. |
| **Payment Links** | Recovery Router already generates payment links via Orders API. Native Payment Links integration would simplify the flow. |
| **Magic Checkout** | Pre-payment data from Magic Checkout (saved cards, UPI IDs) could improve Recovery Router's channel selection for returning customers. |

### The Positioning
Recovery Router isn't a competitor to any Razorpay product. It's the missing piece - the system that handles everything after a payment fails, across all three revenue leak types, with the intelligence and safety that financial software demands.

**"Vulcan makes payments succeed. Recovery Router makes failures recoverable."**

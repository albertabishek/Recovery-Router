# The Journey - How Recovery Router Was Built

> From a buildathon announcement to a production-grade recovery engine in four days.
> By Albert Abishek I

---

## Discovering the Buildathon

I saw the Razorpay AI Buildathon 2026 announcement and went straight to the problem statements. Three tracks, each with a different challenge. Track 3 - AI Revenue Recovery - stopped me cold.

This was not a typical hackathon prompt. Razorpay was not asking participants to build something novel on top of their platform. They were admitting, publicly, that there was a gap in their own product ecosystem. Vulcan had launched in August 2026 - India's first transformer-based AI model for payments, trained on 4 billion transactions and 3 trillion data points. It improved payment success rates by 8-10%. Agent Studio had launched in March, the world's first AI Agent Studio for payments, built on Anthropic's Claude Agent SDK.

They had spent years optimizing the success path. Making payments go through. But the failure path - what happens after a payment fails - was still fragmented. Separate tools for separate leak types. No unified intelligence. No single pipeline that understood why a payment failed and could route the failure to the right recovery action.

Track 3 was Razorpay saying: we solved the "before." Someone solve the "after."

I picked Track 3.

---

## The Research Phase - Thinking Like a Razorpay Engineer

Before writing a single line of code, I went deep into research. If I was going to build something that belonged in Razorpay's ecosystem, I needed to understand the ecosystem first.

### Understanding Razorpay's Product Suite

I studied every relevant product: Vulcan, Agent Studio, Smart Collect, Payment Links, Magic Checkout, the existing Failed Payment Recovery product. The question was not "what can I build?" but "what is missing?"

The answer became clear. Vulcan optimized payment routing to prevent failures. Agent Studio provided building blocks - pre-built agents for disputes, subscriptions, abandoned carts. The existing Failed Payment Recovery product handled subscription payment recovery via WhatsApp reminders. But there was no unified, intelligent system that could take any type of payment failure, understand why it happened, decide what to do about it, and execute through the right channel at the right time.

The failure path was a collection of point solutions. Nobody had built the pipeline.

### Understanding Why Razorpay Posed This Problem

The timing was revealing. Vulcan launched in August 2026 with hyper-precision routing and fraud detection. It pushed success rates up by 8-10%. But that also meant Razorpay had better data than ever on what was still failing and why. They could see the gap more clearly than anyone, and they were inviting the community to fill it.

### Studying the Competition

I researched how every major payment processor handles recovery:

- **Stripe** reports 55% of failed payments recovered using their combined billing tools (Smart Retries + automatic card updates + recovery automations). But their dunning is template-based email only - no SMS, no WhatsApp, no in-app. Retry logic and dunning operate independently.
- **Adyen** uses contextual multi-armed bandits for retry timing - one of the most technically sophisticated approaches globally. But it is retry-only. Dunning communication is left entirely to merchants.
- **Cashfree** launched "Relay," an AI agent for retrying failed payments and handling abandoned carts. Direct competitor in the Indian market.
- **Juspay** does payment orchestration across 150+ countries with smart retry logic, but it is an orchestration layer, not a recovery engine.
- **Chargebee** and **Recurly** handle subscription dunning well (Recurly claims 70-80% recovery with Intelligent Dunning ML), but they only do subscriptions - no one-time payment recovery, no cart abandonment.

The pattern was clear: everyone focuses on retry mechanics - when to retry the same payment method. Nobody combines diagnostic intelligence (understanding why it failed) with personalized multi-channel recovery (right channel, right message, right timing) across all three revenue leak types in a single engine.

That's when it clicked. What if I treated payment failures the way Vulcan treats payment routing? Classify every failure, compute a dynamic recovery budget based on its characteristics, and route it through a multi-channel pipeline with honest metrics. That was the insight that shaped everything.

---

## The Core Insight

> "Vulcan routes payments. Recovery Router routes failures."

This became the north star. Not a standalone tool. Not another retry bot. Something that completes Razorpay's ecosystem - the missing piece that handles everything after a payment fails.

The positioning was deliberate. Recovery Router is not a competitor to any Razorpay product. It is the system that sits at the end of the payment lifecycle, where Vulcan's routing ends and recovery begins. Vulcan makes payments succeed. Recovery Router makes failures recoverable.

Three leak types, one pipeline:
- **Payment failures** enter via Razorpay webhooks, classified into 12 categories
- **Cart abandonment** enters via merchant API, classified by intent
- **Overdue invoices** are discovered by polling the Razorpay API every 6 hours

All three flow through the same classify-route-act-measure pipeline. That was the architecture from day one.

---

## The n8n Prototype Phase

I started with n8n - a visual workflow automation tool - to prove the logic before committing to a full build.

Five workflows, built rapidly:

1. **Recovery Router** - a 15-node webhook-to-send pipeline. Webhook receives a payment failure, classifies it, generates a payment link, writes an AI-personalized message, sends it via the best available channel.
2. **Invoice Overdue Scanner** - a cron job running every 6 hours, polling Razorpay's API for overdue invoices and feeding them into the recovery pipeline.
3. **Recovery Tracker** - listens for `payment.captured` events and matches them back to recovery events to track what actually got recovered.
4. **Escalation Agent** - a 5-minute loop where AI analyzes the full attempt history for each active event and decides the next action: which channel, what tone, whether to continue or give up.
5. **Recovery Analytics API** - an HTTP endpoint that aggregates recovery metrics for the dashboard.

These workflows proved something important: the logic worked. The classify-route-act-measure pipeline was sound. An event could enter the system, get classified, receive a dynamic recovery budget, and be routed through escalating channels with AI-generated messages.

But n8n was not enough for production. No distributed locking - two workflow executions could process the same event simultaneously. No race condition handling. No proper deduplication. No crash recovery. For a demo, n8n was fine. For financial software, it was dangerous.

And the n8n workflows would come back to haunt me later, in a way I never expected. More on that in a moment.

---

## The Full Rebuild

### August 28, 2026 - Day 1

The initial commit landed at 4:06 PM IST on August 28. The decision had already been made: rebuild everything as a proper six-component architecture.

- **FastAPI** for the API layer - async, auto-documented, with Pydantic validation for webhook ingestion
- **Celery Worker** for async task processing - the recovery pipeline runs as background tasks
- **Celery Beat** for periodic scheduling - the invoice scanner (every 6h) and escalation engine (every 5 min)
- **React Frontend** for the dashboard - cloned from Razorpay's actual UI design
- **Redis** for caching, deduplication, distributed locks, rate limiting, and PII token storage
- **Supabase (PostgreSQL)** for persistent storage with realtime subscriptions

The guiding principle was simple: "Everything will be async. Use Celery, workers, everything - no tricks." No mocking the queue. No faking async with setTimeout. No demo shortcuts. If a Razorpay engineer reviewed this code, they should see production patterns, not hackathon patterns.

The first commit was massive - the full working pipeline from webhook ingestion through AI classification to multi-channel message delivery. The dashboard. The simulator. The test suite. The foundation was laid in one push.

### August 30, 2026 - The Marathon Day

August 30 was the day everything came together and nearly fell apart, multiple times.

**8:37 AM** - Security hardening, authentication, AI classification improvements, and UI updates. The system started looking and behaving like real financial software.

**8:47 AM** - Ten minutes later, the first major bug fix. The Premature Give-Up bug. Events were being marked "exhausted" after just 1 attempt when they had a budget of 5. The AI escalation schema had defaulted `action` to "give_up" instead of "send." When the AI returned partial JSON, it inherited the destructive default. Fix: changed the schema default, added an AI override that checks for untried channels, and added a hard guard that blocks give-up when attempts remain. Three layers of defense - because in financial software, a single safety check is never enough.

**10:59 AM** - Reconciliation fixes, quiet hours enforcement, payment link safety, and the honest metrics system. This is where ghost recovery prevention was born. If a customer pays organically - no outreach was sent - the system logs it as `organic_recovery`, not `recovered`. The system separates organic from outreach-driven recovery because that is the metric a product manager would trust.

**12:57 PM** - The TOCTOU race condition fix. After fixing the Premature Give-Up bug, events #16 and #17 were still getting prematurely exhausted. The code was correct. But two Celery tasks were processing the same event concurrently - `_send_delayed` (a countdown task) and the Beat escalation cycle could both pick up the same event. Task A reads status="pending", Task B reads status="pending", both proceed, one sets exhausted before the other finishes. Classic time-of-check-to-time-of-use. Fix: conditional database updates with `.eq("status", "pending")` for optimistic concurrency, per-event Redis distributed locks with 300-second TTL, and atomic state transitions.

**5:42 PM** - Railway and Vercel deployment configs, plus the database safety trigger. This is when the Ghost Writer bug was discovered and fixed. Event #18 had been marked exhausted with `skip_reason=null` and `next_action_at` still set - an impossible state. My code always sets `skip_reason` when exhausting and clears `next_action_at`. I checked every code path. Checked git history. Checked Celery task results in Redis. Checked worker file timestamps against .pyc timestamps. Everything was correct.

Then I checked the n8n workflows directory. The "Mark Exhausted" node in `Escalation Agent.json` was setting status to "exhausted" - but with no `skip_reason`, no `next_action_at = null`, and no status guard. All five n8n workflows were still active, writing directly to Supabase with their own credentials, completely bypassing the FastAPI backend. Two independent systems were racing against each other with no mutual awareness.

Fix: unpublished all n8n workflows, then added a PostgreSQL trigger as the last line of defense - a database-level guard that blocks ANY writer from marking an event exhausted when attempts remain and no skip_reason is provided. No matter what writes to the database - the app, n8n, a manual query, a future integration - the trigger prevents premature exhaustion.

**5:45 PM to 5:50 PM** - Railway build failures. Three attempts in eight minutes. First: Nixpacks `python311` package resulted in "pip: command not found." Second: added `python311Packages.pip`, got "No module named pip." Third: removed all manual Nix configuration and let Nixpacks auto-detect Python from `requirements.txt`. That worked. The lesson: do not fight the platform.

**9:03 PM to 10:16 PM** - Three commits over 73 minutes to get the favicon right. Razorpay-style logo, then the exact logo mark from the navbar, then fixing the colors to match precisely. A small detail, but the dashboard needed to feel native.

### August 31, 2026 - Final Polish

**7:34 AM** - The final commit before submission. A security audit had identified P0 and P1 issues - these were fixed first thing in the morning. The system was ready.

---

## The Dashboard - Cloning Razorpay's UI

I did not build a hackathon dashboard. I cloned Razorpay's actual UI - their design tokens, their SVG icons, their color system, their layout patterns. Not because it is pretty (though it is), but because Recovery Router should feel like it already belongs in Razorpay's product suite. Not a hackathon demo — a native feature.

When you open the dashboard, it feels like it already belongs in Razorpay's product suite. Five pages:

- **Overview** - revenue metrics, recovery rate, channel performance, recent events feed
- **Recovery Events** - event list with status tabs, a 420px slide-in detail panel with full pipeline visualization, attempt history, AI classification fields, pause/resume/cancel controls
- **Analytics** - 5-card KPI strip, channel effectiveness ranking, failure category distribution, recovery by type breakdown
- **Simulator** - 10 built-in scenarios across 3 event types, custom recipient fields, and a "Try Live Payment" button that creates a real Razorpay test-mode checkout
- **Audit Logs** - full recovery attempt trail with AI reasoning, provider degradation paths, delivery status, auto-refresh every 15 seconds

---

## The Testing Philosophy

114 tests across 6 test files. API tests, pipeline tests, security tests, error handling tests, load tests, and end-to-end tests.

Why so many tests for a hackathon project? Because this is not a hackathon project. This is what I would build if I were a Razorpay engineer assigned to solve this problem on Day 1. Production systems need verification, not just demos.

The tests cover the things that matter in financial software: classifier accuracy across all 12 failure categories, the full recovery pipeline from webhook to message delivery, escalation logic and the three-layer give-up prevention, analytics accuracy, deduplication under concurrent load, webhook signature verification, rate limiting, and the dynamic budget calculation.

If a test fails, something real is broken. No flaky tests, no tests that pass because they test nothing.

---

## Timeline Summary

| Date | Phase | Key Events |
|------|-------|-----------|
| Before Aug 28 | Research | Studied Razorpay's ecosystem, competitive landscape, industry data, other Track 3 submissions. Built 5 n8n prototype workflows. |
| Aug 28 (4:06 PM) | Initial Build | First commit - full working pipeline, dashboard, simulator, test suite. Six-component architecture from day one. |
| Aug 30 (8:37 AM) | Hardening | Security hardening, auth, AI classification, UI improvements. |
| Aug 30 (8:47 AM) | Bug Fix | Premature Give-Up bug - three-layer defense added. |
| Aug 30 (10:59 AM) | Honest Metrics | Ghost recovery prevention, reconciliation fixes, quiet hours. |
| Aug 30 (12:57 PM) | Race Conditions | TOCTOU fix - distributed locks, conditional updates, atomic state transitions. |
| Aug 30 (5:42 PM) | Deployment + Ghost Writer | Railway/Vercel configs. Ghost Writer bug discovered - n8n workflows still active, racing against the backend. Database trigger added. |
| Aug 30 (5:45-5:50 PM) | Build Fixes | Three Railway build attempts in 8 minutes. |
| Aug 30 (9:03-10:16 PM) | Polish | Favicon iterations to match Razorpay's exact brand. |
| Aug 31 (7:34 AM) | Security Audit | P0/P1 security and accuracy fixes from final audit. |

Four days from first commit to submission-ready. But the research that shaped the architecture - the competitive analysis, the product ecosystem study, the insight about the unified pipeline - that happened before the first line of code was written.

---

## What I Learned

**1. Research before code.** The time spent studying Razorpay's products, the competitive landscape, and other submissions shaped every architectural decision. Without that research, I would have built another retry bot.

**2. Defense in depth is not optional in financial software.** A single safety check failed (the schema default). Two safety checks might have failed (the AI override). Three layers - schema default, AI override, hard guard - plus a database trigger as the ultimate backstop. That is what it takes.

**3. Async systems need explicit serialization.** "It works locally" means nothing when two Celery tasks can process the same event concurrently. Distributed locks and conditional updates are not premature optimization - they are correctness requirements.

**4. Prototype systems come back to haunt you.** The n8n workflows were supposed to be throwaway prototypes. They were still running, still writing to the database, still causing impossible states. When you cannot find the bug in your code, look for systems you forgot were still running.

**5. Honest metrics build trust.** It would have been easy to count organic recoveries as AI-driven recoveries and show impressive numbers. But a Razorpay product manager would see through that in seconds. Separating organic from outreach-driven recovery is not a feature - it is integrity.

**6. Build what belongs.** I cloned Razorpay's UI, used their design tokens, matched their favicon. Not for aesthetics — so that when you open Recovery Router, it feels like it already belongs in the Razorpay suite. The goal was never novelty. The goal was to build the missing piece.

---

*Recovery Router - Razorpay AI Buildathon 2026, Track 3: AI Revenue Recovery*
*Built by Albert Abishek I*

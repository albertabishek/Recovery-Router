# Recovery Router — Video Demo Script

**Target Duration:** ~8-9 minutes (flexible for impact)
**Speaker:** Albert Abishek I
**Format:** Screen recording with voice-over, overlays where noted

---

## Screen 1: Opening — Personal Introduction (~50 seconds)

**[SCREEN: Profile photo on left, Track 3 problem statement on right, clean dark background]**

> Hi, I'm Albert Abishek.
>
> When I saw the Razorpay AI Buildathon announcement, I went straight to the problem statements. Three tracks. Track 3 stopped me cold.
>
> "AI Revenue Recovery." Razorpay was essentially saying — we've spent years optimizing the success path. Vulcan makes payments go through. Agent Studio gives you building blocks. But what happens *after* a payment fails? That's still fragmented. Separate tools for separate leak types. No unified intelligence.
>
> That's what I built. Recovery Router — a single pipeline that takes any payment failure, understands *why* it failed, decides what to do about it, and executes through the right channel at the right time.
>
> Vulcan routes payments. Recovery Router routes failures.
>
> Let me show you how it works.

---

## Screen 2: Architecture & Tech Decisions (~70 seconds)

**[SCREEN: Architecture diagram showing the 6 components — FastAPI, Celery Worker, Celery Beat, React Frontend, Redis, Supabase]**

> Recovery Router has six components. Let me walk you through each and *why* I chose it.
>
> **FastAPI** for the API layer. Not Django — no ORM needed since Supabase handles the database. Not Flask — no native async. FastAPI gives me async webhook handlers that accept and queue events in under 100 milliseconds, plus Pydantic validation on every request for free.
>
> **Celery with Redis** for background processing. The recovery pipeline involves calling AI models, generating payment links, and sending messages — that's 5 to 13 seconds of external I/O per event. I couldn't run that inside the webhook handler. Celery gives me delayed task execution, periodic scheduling, and automatic retries with exponential backoff. Every recovery attempt is a separate Celery task that survives worker crashes.
>
> **Supabase** — managed PostgreSQL with Row Level Security. I needed relational data — events with foreign-keyed attempts, partial unique indexes, database triggers. Firebase was out.
>
> **Redis** serves six different roles — task broker, dedup cache, rate limiter, distributed locks, checkout token store, and analytics cache. One service, one connection URL.
>
> **[OVERLAY: 3-model AI chain diagram]**
>
> For AI, I use **OpenRouter** with a 3-model fallback chain. If the primary model fails, we fall through to the next. If all three fail, deterministic rules take over. Recovery never stops because AI is down.
>
> And the frontend — **React** with Vite, styled to look exactly like a Razorpay product. Not a hackathon dashboard. A native feature.

---

## Screen 3: Live Demo — Simulator & Dynamic Budgets (~90 seconds)

**[SCREEN: Simulator page open in the dashboard]**

> Let me show you the system processing real events. The Simulator has 10 built-in scenarios covering all three revenue leak types — payment failures, cart abandonment, and overdue invoices.
>
> Watch what happens when I fire a **UPI Timeout** — a Rs 4,999 payment that timed out.
>
> **[Click UPI Timeout scenario]**
>
> The event enters the pipeline. The AI classifies it as "upi_timeout" with a 0.85 recovery probability. The router sees high value plus high probability and assigns **5 recovery attempts**. That's the dynamic budget — this event is worth chasing hard.
>
> Now watch this. I'll fire a **Low-Value Cart Abandonment** — a Rs 149 browsing session.
>
> **[Click Low-Value Cart scenario]**
>
> Same pipeline. But the AI classifies it as "browse_only_abandonment" and assigns **zero attempts**. No messages sent. Because spending money to recover a Rs 149 browse-only session would cost more than the recovery is worth.
>
> The budget ranges from 0 to 5 based on three signals — amount, recovery probability, and failure category. A Rs 30,000 failed invoice gets 5 attempts across multiple channels. A user cancellation gets max 2 — because they cancelled for a reason, and we respect that.
>
> **[SCREEN: Switch to Live Payment section]**
>
> Now the real thing. This "Try Live Payment" button creates a real Razorpay test-mode checkout.
>
> **[Click Open Razorpay Checkout, show the checkout modal]**
>
> This is Razorpay's actual Standard Checkout SDK. I'll enter the test card and let it fail.
>
> **[Complete the failed payment flow]**
>
> A real `payment.failed` webhook just fired from Razorpay's servers. The recovery pipeline is processing it right now. Let's go see it in the dashboard.

---

## Screen 4: Dashboard Walkthrough — Events & Classifications (~70 seconds)

**[SCREEN: Events page showing the list of events with different statuses]**

> Here's the Events page. Every event in the system — filtered by status tabs. In Progress, On Hold, Paid, Gave Up.
>
> **[Click on the UPI timeout event]**
>
> When I click an event, this detail panel slides in. Let me walk you through what the AI decided.
>
> Category: "upi_timeout." Recovery probability: 0.85. Recommended channel: WhatsApp. Budget: 5 attempts. And here's the AI's reasoning — it explains *why* it classified this event this way and what the backup plan is.
>
> **[Scroll to show the Recovery Pipeline visualization]**
>
> This pipeline visualization shows every step — Classified, Routed, Message Sent, Result. Each step with a green checkmark when completed.
>
> **[Scroll to Attempt History]**
>
> And the attempt history. You can see the channel used, the outcome, the degradation path — if WhatsApp failed, did it fall to SMS or email? Every provider attempt is logged.
>
> **[Click on a different event — a card expired one]**
>
> Now look at this card expired event. Different classification, different budget — 3 attempts instead of 5. The retry delay is 6 hours because a card expired customer needs time to update their card details. The AI knows this.
>
> **[Click on an unrecoverable decline]**
>
> And this fraud decline — zero attempts, zero messages. The system correctly identified this as unrecoverable and spent nothing on it. That's what intelligent routing looks like.

---

## Screen 5: Safety Mechanisms & Ghost Writer Story (~90 seconds)

**[SCREEN: Code showing the three-layer give-up prevention]**

> Now, the part that makes this production-grade — safety mechanisms. In financial software, a single safety check is never enough.
>
> Recovery Router has **three layers of give-up prevention**. If the AI says "give up" but the budget isn't spent, Layer 1 overrides it and picks a different channel. Layer 2 is a hard guard — even after the AI decision, it forces a send if attempts remain. And Layer 3 — if zero outreach was sent when the recovery window expires, the window extends by 24 hours. Every event gets at least one real attempt.
>
> Then there's **quiet hours** — no messages between 9 PM and 9 AM. **Per-resource cooldowns** — 5-minute cooldown per phone number to prevent message flooding. **Action reservation** — we insert a "reserved" row in the database *before* sending, so if a worker crashes mid-send, the retry sees the reservation and skips instead of double-sending.
>
> And there's the **delivery failure detector** — a separate counter tracking consecutive hard provider rejections. If a customer's contact details are fake, the system stops after max_attempts + 1 failures instead of retrying forever.
>
> **[SCREEN: Show the Ghost Writer JSON overlay image]**
>
> But here's my favourite bug story. **The Ghost Writer.**
>
> I found Event 18 in this impossible state. Status "exhausted" after only 1 attempt. Skip reason null — but every code path sets it. Next action still scheduled — but it should be cleared when exhausted. Strategy says "exhausted" — not "max_attempts_reached."
>
> I checked every code path. Checked git history. Checked Celery task results. Checked worker bytecode timestamps. Everything was correct. My code *could not* produce this state.
>
> Then I remembered — this project started with n8n workflows. Five visual workflows I built as a prototype. When I rebuilt in Python, I forgot to unpublish them. They were still running, writing directly to Supabase, with none of my safety guards. Two independent systems racing against each other with no mutual awareness.
>
> The ghost writer was me, from two weeks ago.
>
> The fix? A **PostgreSQL trigger** — a database-level guard that catches *any* writer trying to prematurely exhaust an event. Not just my app. Any query. Any integration. The defense is at the data layer now.

---

## Screen 6: Analytics & Honest Metrics (~70 seconds)

**[SCREEN: Analytics page showing KPI cards, channel performance, failure category breakdown]**

> The Analytics page. Five KPI cards at the top — total events, recovery rate, average attempts to recover, average recovery time, and the AI lift multiplier.
>
> This lift multiplier compares our recovery rate against a 15% industry baseline — that's from Razorpay's own published data. Not a number I made up. We show the improvement in percentage points and additional revenue recovered.
>
> **[Scroll to Channel Performance]**
>
> Channel performance — ranked by recovery rate. You can see which channels are working best. WhatsApp with personalized AI messages typically outperforms template-based SMS.
>
> **[Scroll to Failure Category Breakdown]**
>
> And failure category breakdown. Each of the 12 categories with its recovery rate. UPI timeouts recover at 80%+. Unrecoverable declines at 0%. The system treats them completely differently.
>
> **[OVERLAY: Code block showing ghost recovery prevention logic]**
>
> But here's what I'm most proud of — **honest metrics**. When a payment is captured, the system checks: did we actually send a recovery message before the customer paid? If `attempt_count` is zero and no outreach was sent, we mark it as **organic recovery** — the customer paid on their own. We don't inflate our numbers by claiming credit for payments that would have happened anyway.
>
> And importantly — in the current landscape, we cannot send recovery notifications via WhatsApp, SMS, or email to AI payment agents. Agents don't check inboxes. They don't read WhatsApp. This is a fundamental gap that traditional recovery channels cannot fill — and it's why the future of recovery looks very different. More on that in a moment.

---

## Screen 7: Test Suite & Engineering Rigour (~80 seconds)

**[SCREEN: Terminal showing pytest output — unit tests running]**

> 397 tests across the entire codebase. 247 backend unit tests, 92 live integration tests, 31 end-to-end tests, and 27 frontend component tests.
>
> **[Show unit tests running — fast, all green]**
>
> The unit tests run anywhere, instantly, with zero external dependencies. They cover classifier logic — all 12 fallback categories. Router budget computation — every tier from 0 to 5 attempts. Quiet hours boundaries. Escalation channel rotation. Idempotency key formats. Reconciliation checks. Message generation safety. All 10 Pydantic models.
>
> **[OVERLAY: GitHub Actions CI workflow screenshot]**
>
> CI runs 274 of these tests automatically on every push — the unit tests plus frontend tests. The live integration tests run separately because they need real API credentials and a running server.
>
> **[Return to terminal or code view]**
>
> Let me tell you about the bugs I found. Not just the Ghost Writer — there were eight significant bugs total. Three were concurrency issues.
>
> **Bug 1 — The Premature Give-Up.** The AI schema defaulted `action` to "give_up." Any time the AI returned partial JSON, the system stopped trying to recover money. Fixed with three layers of defense.
>
> **Bug 2 — The TOCTOU Race Condition.** Two Celery tasks processing the same event simultaneously. Both read "pending," both proceed, chaos. Fixed with Redis distributed locks, conditional updates, and fresh state re-reads.
>
> **Bug 8 — The Infinite Retry Loop.** A customer with fake contact details. Every send failed. `attempt_count` never incremented because it's success-only. Safety overrides kept forcing retries. Fixed with a separate `delivery_failure_count` circuit breaker.
>
> Five out of eight bugs could have caused financial impact. Every one of them is now caught by independent safety mechanisms. 13 safety mechanisms across 18 defense layers total.

---

## Screen 8: Where It Fits & The Journey (~60 seconds)

**[SCREEN: Diagram showing Razorpay ecosystem — Vulcan, Agent Studio, Smart Collect, and Recovery Router completing the lifecycle]**

> Recovery Router isn't a standalone tool. It completes a lifecycle.
>
> Vulcan optimizes payment routing to prevent failures. Agent Studio provides pre-built agents for disputes and subscriptions. Smart Collect handles incoming payments. But what happens when a payment still fails? What happens when a cart is abandoned? What happens when an invoice goes overdue?
>
> That's the gap Recovery Router fills. Three leak types, one pipeline. Classify, route, act, measure. It sits at the end of the payment lifecycle, where Vulcan's routing ends and recovery begins.
>
> **[SCREEN: Timeline visualization — research phase → n8n prototype → full rebuild]**
>
> This was built in four days. But the research that shaped it happened before the first line of code. I studied every Razorpay product. I read how Stripe, Adyen, Chargebee, and Cashfree handle recovery. I understood *why* Razorpay posed this problem — they had the data from Vulcan to see what was failing, and they were inviting the community to fill the gap.
>
> The n8n prototype proved the logic. The full rebuild made it production-grade. Every architectural decision — from FastAPI to Celery to the database trigger — was informed by that research.
>
> I didn't build a hackathon project. I built what I would build if I were a Razorpay engineer assigned to solve this on Day 1.

---

## Screen 9: Future Vision — AI Payment Agents (~60 seconds)

**[SCREEN: Clean slide or diagram showing traditional recovery vs agent-initiated payments]**

> One last thing. Where does payment recovery go from here?
>
> Right now, recovery works through human channels — WhatsApp messages, SMS, emails. We send a link, the customer clicks it, they complete the payment. That works because *humans* check their messages.
>
> But the payments landscape is changing. Razorpay's own Agent Studio launched AI agents that initiate payments on behalf of businesses. What happens when the *payer* is also an agent? An AI agent handling procurement, subscriptions, automated purchasing — when that agent's payment fails, who do you send the WhatsApp to?
>
> You can't. Agents don't have inboxes. They don't read SMS. Traditional recovery channels are fundamentally incompatible with agent-initiated payments.
>
> The future of recovery isn't sending better messages — it's **agent-to-agent communication**. A recovery system that detects a failed agent-initiated payment and communicates directly with the paying agent's API. No human in the loop. No WhatsApp. Just machines talking to machines, resolving payment failures in seconds instead of hours.
>
> Recovery Router's architecture — the classify-route-act pipeline — is designed to be channel-agnostic. Today the channels are WhatsApp, SMS, and email. Tomorrow, the channel could be an API callback to the paying agent. The pipeline doesn't change. Only the last mile does.
>
> That's the thinking behind Recovery Router. Not just solving today's recovery problem — but building the architecture that adapts when the payer isn't human anymore.
>
> Thank you for watching.

---

## Production Notes

**Total estimated duration:** ~8.5 minutes

**Overlays needed:**
1. Profile photo (Screen 1)
2. Architecture diagram (Screen 2)
3. 3-model AI chain diagram (Screen 2)
4. Ghost Writer JSON data — the Event 18 impossible state (Screen 5)
5. Code block: ghost recovery prevention logic (Screen 6)
6. GitHub Actions CI screenshot (Screen 7)
7. Razorpay ecosystem diagram (Screen 8)
8. Timeline visualization (Screen 8)
9. Agent-to-agent recovery diagram (Screen 9)

**Dashboard pages to show:**
- Simulator page (Screen 3)
- Live Payment section (Screen 3)
- Events page with detail panel (Screen 4)
- Analytics page (Screen 6)
- Audit Logs page (optional, time permitting)

**Pre-recording checklist:**
- [ ] Clean the database (reset all test data)
- [ ] Run all test scenarios fresh so events are recent
- [ ] Verify the dashboard is loading properly
- [ ] Pre-test the live payment flow once
- [ ] Have the Ghost Writer JSON screenshot ready as overlay
- [ ] Prepare all code block overlays
- [ ] Test screen recording software

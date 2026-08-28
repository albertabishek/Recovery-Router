Recovery Router Spec

::: page
::: doc-header
::: doc-eyebrow
Razorpay AI Buildathon · Track 3
:::

# Recovery Router: Complete Project Specification {#recovery-router-complete-project-specification .doc-title}

One intelligent engine that classifies revenue leaks across payment
failures, cart abandonment, and overdue invoices --- and routes each to
the optimal recovery action.

::: doc-meta
Author: Albert Abishek I Deadline: Sep 5, 2026 v1.0
:::
:::

::: section
::: section-label
Section 1
:::

## The Problem We\'re Solving

Indian merchants on Razorpay lose revenue from three separate holes, and
each is plugged with a separate, unintelligent band-aid.

::: stat-row
::: stat-card
::: stat-value
20-25%
:::

::: stat-label
of all payments fail on Indian gateways
:::
:::

::: stat-card
::: stat-value
70%
:::

::: stat-label
of customers never return after a payment failure
:::
:::

::: stat-card
::: stat-value
\~20%
:::

::: stat-label
recovered by Razorpay\'s current broadcast approach
:::
:::

::: stat-card
::: stat-value
80%
:::

::: stat-label
of recoverable revenue is left on the table
:::
:::
:::

### The Three Revenue Leaks

**Leak 1: Payment Failures.** A customer tries to pay and the
transaction fails --- UPI timeout, card declined, insufficient funds,
bank downtime. Razorpay currently sends the same payment link to
everyone via WhatsApp/Email/SMS regardless of why it failed. No
classification. No channel optimization. No timing intelligence. A UPI
timeout at 9pm (network congestion, try again in 10 minutes) gets the
same treatment as a card declined for insufficient funds (needs a
completely different approach).

**Leak 2: Checkout Abandonment.** A customer adds items to cart, reaches
checkout, but leaves without paying. Razorpay\'s Agent Studio has an
abandoned cart agent, but it launched in March 2026, is still in early
access with no published adoption data, is powered by third parties
(SuperU & Nugget by Zomato), and has faced dark pattern concerns from
journalists.

**Leak 3: Overdue Invoices.** A payment link or invoice is sent but the
customer hasn\'t paid. Razorpay offers exactly 3 timer-based reminders
via SMS/email at fixed intervals. No AI. No prioritization. No
intelligence about which overdue invoices to chase harder or through
which channel. No receivables agent actually exists in Agent Studio
despite being mentioned at Sprint 2026.

::: {.callout .callout-red}
The core problem: Razorpay treats these as three separate problems with
three separate dumb tools. No unified view. No intelligence. No system
that asks \"what is the smartest thing to do for THIS specific revenue
leak?\"
:::
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 2
:::

## Why This Gap Exists

**Razorpay invested in prevention, not recovery.** Vulcan (their
foundation model, launched August 2026) prevents failures by routing
payments optimally. This is the rational priority --- preventing a
failure beats recovering from one. But even Vulcan only improves success
by 8-10%. Failures will always exist.

**Stripe is the only platform with intelligent recovery --- and even
they have gaps.** Stripe\'s Smart Retries uses 500+ signals and ML to
decide WHEN to retry. But it only decides timing. It doesn\'t decide
what ELSE to try --- different channel, different payment method,
different message, a payment plan offer. And it only recovers 25-35% for
B2C (not the 55% they market, which blends B2B numbers).

**Every third-party recovery tool is built for Stripe, for Western
SaaS.** FlyCode, Churnkey, Churn Buster, Butter Payments, Baremetrics
Recover --- all Stripe-only, all designed for subscription businesses in
the US/EU. Zero understanding of UPI, Indian banking, Razorpay\'s API,
or Indian e-commerce.

**Recovery needs merchant context that gateways don\'t have.** What
product did the customer want? What\'s the margin? Is a discount worth
it? What channel does this customer prefer? Gateways process payments;
they don\'t understand the merchant\'s business. That\'s why their
recovery is generic.

::: callout
Nobody --- not Stripe, not PayPal, not Razorpay, not any third-party
tool --- does intelligent recovery ROUTING across multiple action types
for a single failed event.
:::
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 3
:::

## What We\'re Building

### One sentence

**Recovery Router is an intelligent engine that ingests revenue leak
events from three sources --- payment failures, cart abandonment, and
overdue invoices --- classifies each one, and routes it to the single
highest-ROI recovery action.**

### The insight

::: {.callout .callout-green}
\"Razorpay built Vulcan to route payments to the optimal path. Recovery
Router routes failures to the optimal recovery path. One engine. Three
input types. Every action chosen for maximum recovery probability.\"
:::

### What it is NOT

-   Not a dashboard with charts and analytics
-   Not a chatbot or RAG advisor
-   Not a retry-at-checkout tool (Razorpay already does this)
-   Not a reconciliation or settlement system
-   Not three separate products bolted together
-   Not a feature showcase --- every component directly recovers revenue

### The differentiator

Every existing tool either (a) retries the same payment on a timer, or
(b) sends the same notification to everyone. Recovery Router does
neither. It looks at the specific failure, with its specific context,
and makes a routing decision: should I send a WhatsApp with a UPI link,
or an email with alternative payment methods, or wait 3 days and try
again, or offer a payment plan, or do nothing because this is
unrecoverable? **The routing decision is the product.**
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 4
:::

## How It Works (Non-Technical)

Think of it like a hospital triage system. When patients arrive at an
emergency room, a triage nurse doesn\'t give everyone the same
treatment. They assess, classify, and route each patient to the right
care. A broken arm goes to orthopedics. A chest pain goes to cardiology.
A minor cut gets basic first aid. And a patient who\'s already dead
doesn\'t get CPR --- resources are saved for the living.

Recovery Router does the same thing for revenue. Every failed payment,
abandoned cart, and overdue invoice is a \"patient.\" The system:

::: flow-container
::: flow-step
::: flow-num
1
:::

::: flow-content
#### Receives the event

A payment fails, a cart is abandoned, or an invoice goes overdue. The
event arrives via webhook or scheduled check.
:::
:::

::: flow-step
::: flow-num
2
:::

::: flow-content
#### Classifies it

AI analyzes the event: Why did it fail? What was the amount? What
payment method? What time of day? What region? It assigns a recovery
category and estimates recovery probability.
:::
:::

::: flow-step
::: flow-num
3
:::

::: flow-content
#### Routes to the best action

Based on classification, picks the single action with the highest
expected recovery value. Not \"send everything everywhere\" --- one
targeted action per event.
:::
:::

::: flow-step
::: flow-num
4
:::

::: flow-content
#### Executes

Sends the WhatsApp message, or the email, or the SMS, or schedules a
delayed retry, or logs \"no action\" for unrecoverable cases.
:::
:::

::: flow-step
::: flow-num
5
:::

::: flow-content
#### Measures the outcome

Tracks whether the customer eventually paid. Logs recovery time, channel
used, and amount recovered. Feeds this data back to improve future
routing decisions.
:::
:::
:::

### Example scenarios

**Scenario A --- UPI timeout at 9:30pm in Tier-3 city:** Classification:
network congestion, high recovery probability. Action: WhatsApp message
with UPI retry deeplink sent immediately (\"Your payment didn\'t go
through due to network issues. Tap to retry\"). Expected outcome:
customer retries within 15 minutes, payment succeeds.

**Scenario B --- Card declined, insufficient funds, ₹48,000 order:**
Classification: insufficient funds on high-value order, medium recovery
probability. Action: email sent after 24 hours with two options --- pay
via UPI (which may have different balance) or split into 2 payments. No
immediate push --- customer needs time to arrange funds.

**Scenario C --- Cart abandoned after reaching payment page, ₹1,200
order:** Classification: high-intent abandonment (reached payment step),
high recovery probability. Action: WhatsApp nudge after 30 minutes with
the cart summary and a one-tap payment link.

**Scenario D --- Invoice 15 days overdue, ₹3,500, no prior reminders
opened:** Classification: cold invoice, medium probability. Action: SMS
with a short direct payment link (customer likely didn\'t see email
reminders).

**Scenario E --- Card declined, card reported stolen:** Classification:
hard decline, zero recovery probability. Action: NO ACTION. Log as
unrecoverable. Save the merchant\'s messaging quota. Don\'t send a
\"retry your payment\" message to someone whose card was stolen ---
it\'s useless and looks bad.
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 5
:::

## How It Works (Technical)

### Architecture overview

The entire system runs as n8n workflows backed by Supabase for data
persistence, with a React frontend for the recovery view. n8n is not a
prototype layer --- it\'s the production orchestration engine. The
intelligence lives in the classification prompts and routing logic,
which port to any backend (FastAPI + Celery) when volume demands it.

::: tags
[n8n]{.tag} [Supabase / PostgreSQL]{.tag} [OpenAI API]{.tag} [Razorpay
API]{.tag} [Twilio (WhatsApp/SMS)]{.tag} [SendGrid (Email)]{.tag}
[React]{.tag} [Railway]{.tag}
:::

### Component 1: Ingest Layer (3 webhook endpoints)

**Payment Failure Webhook** --- Razorpay sends a `payment.failed` event
to our n8n webhook URL. The payload includes: payment ID, amount,
currency, method (card/UPI/netbanking/wallet), error code, error
description, contact info, and merchant metadata. We use Razorpay\'s
test mode to generate real webhook payloads.

**Cart Abandonment Trigger** --- A lightweight script on the checkout
page detects when a user session ends without payment completion. Fires
a webhook to n8n with: session ID, cart items, cart value, time spent on
checkout, whether payment was attempted, last payment method selected.

**Invoice Overdue Trigger** --- A scheduled n8n workflow (runs every 6
hours) polls Razorpay\'s Payment Links API, identifies links past their
due date that remain unpaid, and feeds them into the classification
pipeline with: link ID, amount, creation date, due date, days overdue,
reminder history.

### Component 2: Classification Engine (the brain)

A single n8n node that calls the LLM with the event data and a
structured prompt. The prompt includes Razorpay-specific context about
Indian payment patterns, regional banking behavior, and time-based
failure patterns. Returns structured JSON:

::: code-block
{ [\"leak_type\"]{.key}: [\"payment_failure\"]{.str},
[\"failure_category\"]{.key}: [\"upi_timeout\"]{.str},
[\"recovery_probability\"]{.key}: [0.78]{.num},
[\"recommended_action\"]{.key}: [\"whatsapp_retry_link\"]{.str},
[\"recommended_channel\"]{.key}: [\"whatsapp\"]{.str},
[\"recommended_timing\"]{.key}: [\"immediate\"]{.str},
[\"reasoning\"]{.key}: [\"UPI timeout during peak hours in Tier-3
region. High probability of success on immediate retry via same method.
WhatsApp has highest open rate for this demographic.\"]{.str},
[\"alternative_action\"]{.key}: [\"sms_upi_deeplink\"]{.str},
[\"skip_reason\"]{.key}: [null]{.str} }
:::

**Classification categories we handle (scoped to highest-impact):**

::: table-wrap
  Category                          Leak Type          Recovery Probability   Typical Action
  --------------------------------- ------------------ ---------------------- ------------------------------------------------------
  **UPI timeout / network error**   Payment failure    High (70-85%)          Immediate WhatsApp with UPI retry link
  **Insufficient funds**            Payment failure    Medium (30-50%)        Delayed email (24h) with alternative methods
  **Card expired**                  Payment failure    Medium (40-60%)        Email with card update prompt + UPI alternative
  **Bank downtime**                 Payment failure    High (60-80%)          Delayed retry (2-4h) via same method
  **Fraud/stolen card**             Payment failure    Zero                   No action (log as unrecoverable)
  **High-intent abandonment**       Cart abandonment   High (50-70%)          WhatsApp nudge after 30 min with cart + payment link
  **Browse-only abandonment**       Cart abandonment   Low (10-20%)           Email after 24h (low urgency, save messaging quota)
  **Invoice recently overdue**      Overdue invoice    High (50-70%)          SMS with direct payment link
  **Invoice long overdue**          Overdue invoice    Low (15-30%)           Escalated email with payment plan option
:::

### Component 3: Action Router (conditional logic)

An n8n Switch node routes to the correct action based on
`recommended_action`. This is deterministic --- the intelligence is in
the classification, the execution is mechanical. Each action path:

-   **WhatsApp via Twilio API** --- Sends a personalized message using
    pre-approved WhatsApp Business templates with a Razorpay payment
    link embedded. Message varies by failure category.
-   **Email via SendGrid** --- Sends a contextual email. For
    insufficient funds: includes alternative payment methods. For cart
    abandonment: includes cart summary. For expired card: includes
    update prompt.
-   **SMS via Twilio** --- Short message with direct payment link or UPI
    deeplink. Used when WhatsApp delivery is uncertain (feature phone
    users, tier-3 areas).
-   **Delayed re-trigger** --- Schedules the event to re-enter the
    pipeline after a wait period (2h, 24h, 72h). Used for bank downtime
    and insufficient funds scenarios.
-   **No-action logger** --- Records the event as \"intentionally
    skipped\" with the reason. Saves the merchant\'s messaging quota.
    This is as important as any action --- it proves the system is
    smarter than a broadcast.

### Component 4: Measurement & Feedback Loop

Every event and action is logged to Supabase with this schema:

::: code-block
[\-- Core events table]{.comment} [id]{.key} UUID PRIMARY KEY
[leak_type]{.key} ENUM (payment_failure, cart_abandonment,
invoice_overdue) [source_id]{.key} TEXT [\-- Razorpay payment/link
ID]{.comment} [amount]{.key} DECIMAL [failure_category]{.key} TEXT
[recovery_probability]{.key} FLOAT [action_taken]{.key} TEXT
[channel_used]{.key} TEXT [timing]{.key} TEXT [reasoning]{.key} TEXT
[action_at]{.key} TIMESTAMP [recovered]{.key} BOOLEAN DEFAULT NULL [\--
NULL = pending]{.comment} [recovered_at]{.key} TIMESTAMP
[recovery_time_mins]{.key} INT [created_at]{.key} TIMESTAMP
:::

A separate n8n workflow listens for Razorpay `payment.captured`
webhooks. When a payment comes in, it matches against pending events by
customer contact info and amount, and marks the event as recovered. This
closes the feedback loop and generates real recovery metrics.

### Component 5: Recovery View (React frontend)

One page. Three numbers at the top. A live event feed below. That\'s it.

-   **Revenue at Risk** --- sum of all event amounts in the pipeline
-   **Revenue Recovered** --- sum of all events where `recovered = true`
-   **Recovery Rate** --- recovered / at risk, as a percentage
-   **Live feed** --- scrolling list of events showing: amount, leak
    type, classification, action taken, outcome. The judges watch this
    during the demo to see the engine making different decisions for
    different inputs.
-   **Recovery by type** --- three small numbers showing recovery rate
    per leak type (payment failures, cart abandonment, invoices). Proves
    each sub-problem is measured independently.
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 6
:::

## What We Chose and Why

### Why all three leak types, not just one

Razorpay\'s Track 3 explicitly asks for \"payment failures, checkout
abandonment, and receivables management.\" Building one would answer
one-third of the problem statement. Building all three as one engine
shows we understand the full revenue lifecycle and built a unified
solution. The key: it\'s one pipeline with three input types, not three
products. The classification engine is the same. The routing logic is
the same. The measurement is the same. Only the webhook format differs.

### Why n8n as the full product

n8n is not a prototype tool --- it\'s a production workflow engine used
by companies at scale. We build the complete working system in n8n
because: (a) it lets us iterate on classification prompts and routing
logic in hours, not days; (b) it provides visual workflow documentation
for free --- the judges can see the entire system architecture by
looking at the n8n canvas; (c) the intelligence is in the classification
and routing, not the infrastructure. When volume demands code, the
proven n8n logic ports to FastAPI + Celery in 2-3 days because the hard
decisions are already made and tested.

### Why classification + routing instead of just retrying

Stripe\'s Smart Retries already proved that intelligent TIMING matters
--- 500+ signals, ML models, recovering 25-35%. But timing is only one
dimension. The channel (WhatsApp vs. email vs. SMS), the message (retry
link vs. alternative method vs. payment plan), and whether to act at all
--- those decisions are unmade by every platform. Recovery Router makes
all four decisions (what, when, where, whether) for each event.

### Why \"no action\" is a feature

Razorpay\'s current system sends notifications to every failed payment.
This includes: stolen cards (unrecoverable), fraud blocks
(unrecoverable), duplicate payments (customer already paid via different
method). Messaging these customers wastes the merchant\'s quota, annoys
the customer, and can damage the brand. Recovery Router identifying and
skipping unrecoverable events is as valuable as recovering the
recoverable ones.

### Why Supabase

PostgreSQL-backed, instant REST API, real-time subscriptions for the
live feed, free tier handles our scale. No overhead of managing a
database. The React frontend connects directly via Supabase client.
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 7
:::

## How We Compare

::: table-wrap
  Capability                    Razorpay Today                          Stripe                                        Third-Party Tools               Recovery Router
  ----------------------------- --------------------------------------- --------------------------------------------- ------------------------------- -----------------------------------------------------------------------
  **Failure classification**    None --- same treatment for all         Decline codes used for retry timing only      FlyCode does per-merchant ML    LLM classifies with contextual signals (time, region, amount, method)
  **Recovery channels**         WhatsApp + Email + SMS (all at once)    Email only                                    Email + SMS (some)              Picks ONE optimal channel per event
  **Timing intelligence**       Immediate broadcast                     ML-optimized retry timing                     Fixed schedules                 Immediate, 2h, 24h, or 72h based on failure type
  **\"No action\" decision**    No --- messages everyone                Skips hard declines for retry, still emails   No                              Yes --- skips unrecoverable, logs reason
  **Cart abandonment**          Agent Studio (early access, unproven)   Not built-in                                  Separate tools (Klaviyo etc.)   Same engine, same pipeline
  **Overdue invoices**          3 timer-based reminders                 Custom dunning flows                          Stripe-only tools               Same engine, same pipeline
  **Unified view**              No --- 3 separate tools                 No --- checklist of features                  No --- separate products        One dashboard, one recovery rate
  **India / Razorpay native**   Yes                                     No                                            No                              Yes --- built on Razorpay webhooks + API
:::
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 8
:::

## The ROI Math

For a merchant processing **₹1 crore/month**:

::: stat-row
::: stat-card
::: stat-value
₹20-25L
:::

::: stat-label
revenue lost to payment failures (20-25%)
:::
:::

::: stat-card
::: stat-value
₹10-15L
:::

::: stat-label
revenue lost to cart abandonment
:::
:::

::: stat-card
::: stat-value
₹5-10L
:::

::: stat-label
revenue stuck in overdue invoices
:::
:::
:::

**Total revenue at risk: ₹35-50 lakhs/month per merchant.**

Razorpay\'s current tools recover \~20% of payment failures (₹4-5L) and
near-zero from the other two categories with any intelligence. Recovery
Router targets the full ₹35-50L pool across all three leak types.

::: {.callout .callout-green}
Even a 5 percentage point improvement in overall recovery rate =
₹1.75-2.5 lakhs additional monthly revenue per merchant. Across
Razorpay\'s merchant base, this scales to crores.
:::

The pitch number: \"In testing with simulated Razorpay webhook data,
Recovery Router achieved X% recovery rate on payment failures compared
to the \~20% baseline --- and additionally recovered revenue from
abandoned carts and overdue invoices that had zero intelligent recovery
before.\"
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 9
:::

## Design Principles

-   **One rupee recovered \> ten features built.** Every component must
    directly recover revenue or measure recovery. Nothing else gets in.
-   **Think like Razorpay, not like a hackathon participant.** Every
    decision must pass: \"Would a Razorpay PM approve this for
    production?\"
-   **Smarter than doing nothing.** The system must know when NOT to
    act. Skipping unrecoverable events is as valuable as recovering the
    recoverable ones.
-   **Measurable or it didn\'t happen.** Recovery rate by failure type.
    False positive rate. Actions taken vs. skipped. Every claim backed
    by a number.
-   **Honest about what doesn\'t work.** Surface limitations. Quantify
    them. The judges reward exception reporting.
-   **One engine, not three products.** Three input types, one
    classification → routing → action → measurement pipeline.
-   **Complement Razorpay, don\'t compete.** \"Vulcan prevents failures.
    Recovery Router handles the ones that still happen.\"
-   **Ship beats perfect.** Working system with honest metrics over
    polished system that\'s half-built.
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 10
:::

## Submission Deliverables

### Public GitHub Repository

-   n8n workflow JSON exports (importable, documented)
-   React frontend source code
-   Supabase schema and setup scripts
-   Classification prompt files (versioned, explainable)
-   README with architecture diagram, setup instructions, and honest
    metrics
-   Test data generator script (produces realistic Razorpay webhook
    payloads)

### 5-Minute Pitch Video

-   0:00-0:30 --- The problem (Razorpay\'s own numbers: 25% failure, 70%
    never return, 80% unrecovered)
-   0:30-1:00 --- The insight (\"Vulcan routes payments. I route
    failures.\")
-   1:00-2:30 --- Live demo (3 different events, 3 different intelligent
    routing decisions)
-   2:30-3:30 --- Architecture (system diagram, classification example,
    routing logic)
-   3:30-4:15 --- Results (recovery rates by type, total recovered,
    actions skipped)
-   4:15-5:00 --- Limitations and scale path

### Architecture Documentation

-   System diagram showing full pipeline
-   Classification taxonomy with all failure categories
-   Routing decision matrix (input → action mapping with reasoning)
-   Measurement methodology (how recovery attribution works)
-   Scale path (n8n → FastAPI migration strategy)
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 11
:::

## Build Timeline

**13 days to deadline (Aug 23 → Sep 5).**

::: flow-container
::: flow-step
::: flow-num
D1
:::

::: flow-content
#### Day 1-2: Ingest layer

Set up Razorpay test-mode account. Configure payment.failed webhooks.
Build n8n webhook endpoints for all 3 event types. Test with real
Razorpay test payloads. Set up Supabase schema.
:::
:::

::: flow-step
::: flow-num
D3
:::

::: flow-content
#### Day 3-4: Classification engine

Write and iterate on the classification prompt. Test against every
failure category. Validate structured JSON output. Tune recovery
probability estimates. Build the n8n LLM node with error handling.
:::
:::

::: flow-step
::: flow-num
D5
:::

::: flow-content
#### Day 5-6: Action routing + execution

Build n8n Switch node for routing. Integrate Twilio (WhatsApp + SMS).
Integrate SendGrid (email). Build the delayed re-trigger loop. Build the
no-action logger. Test each action path end-to-end.
:::
:::

::: flow-step
::: flow-num
D7
:::

::: flow-content
#### Day 7: Measurement + feedback loop

Build the payment.captured webhook listener. Implement recovery
attribution matching. Test the full cycle: event in → action → payment
captured → marked recovered.
:::
:::

::: flow-step
::: flow-num
D8
:::

::: flow-content
#### Day 8-9: React frontend

Build the recovery view: three stat tiles, live event feed,
recovery-by-type breakdown. Connect to Supabase real-time. Deploy on
Vercel/Railway.
:::
:::

::: flow-step
::: flow-num
D10
:::

::: flow-content
#### Day 10-11: Demo data + metrics

Generate 100+ realistic test events across all three leak types. Run
through the full pipeline. Build up real metrics. Identify and document
failure cases and limitations.
:::
:::

::: flow-step
::: flow-num
D12
:::

::: flow-content
#### Day 12: Pitch video + docs

Record the 5-minute pitch. Write architecture documentation. Create
system diagram. Finalize README.
:::
:::

::: flow-step
::: flow-num
D13
:::

::: flow-content
#### Day 13: Polish + submit

Final GitHub cleanup. Verify all links work. Double-check metrics.
Submit via the Google Form before Sep 5.
:::
:::
:::
:::

------------------------------------------------------------------------

::: section
::: section-label
Section 12
:::

## Known Limitations (We Surface These, Not Hide Them)

-   **Classification accuracy depends on LLM quality.** The system is as
    good as the classification prompt. We report classification accuracy
    alongside recovery rates.
-   **Recovery attribution is imperfect.** If a customer pays 3 days
    after our WhatsApp message, did our message cause it or would they
    have paid anyway? We acknowledge this correlation-vs-causation gap
    in our metrics.
-   **n8n has throughput limits.** For a single merchant or small scale,
    n8n handles it. For Razorpay-scale (millions of events), the logic
    needs to move to async workers. We state this as a known migration
    path, not a flaw.
-   **Simulated data, not live merchant data.** Our metrics come from
    synthetic Razorpay test-mode events. Real-world recovery rates will
    differ. We state our test methodology transparently.
-   **Some failure types are genuinely unrecoverable.** We quantify what
    percentage of events fall into the \"no action\" bucket and explain
    why recovery isn\'t possible for those categories.
-   **WhatsApp Business templates require pre-approval.** In production,
    the message templates need Meta approval. For the buildathon demo,
    we use Twilio sandbox mode.
:::

------------------------------------------------------------------------

::: {.section style="text-align: center; padding: 2rem 0;"}
Recovery Router --- Razorpay AI Buildathon Track 3 Submission

Albert Abishek I · abishekialbert@gmail.com
:::
:::

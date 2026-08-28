Recovery Router Documentation

::: container
::: hero
::: hero-eyebrow
Razorpay AI Buildathon 2026 --- Track 3
:::

# Recovery Router

One intelligent engine that classifies revenue leaks across payment
failures, cart abandonment, and overdue invoices, then routes each to
the optimal recovery action --- autonomously.
:::

::: section
::: highlight-box
**Core Insight:** Razorpay built Vulcan to route payments to the optimal
processing path. Recovery Router routes *failures* to the optimal
recovery path.

Same classify → route → act → measure pipeline. Three input types, one
engine.
:::
:::

::: section
## Live System Status {#live-system-status .section-title}

::: stats
::: stat
::: stat-value
29
:::

::: stat-label
Total Events
:::
:::

::: stat
::: stat-value
5
:::

::: stat-label
Active Workflows
:::
:::

::: stat
::: stat-value
₹2.72L
:::

::: stat-label
Amount at Risk
:::
:::

::: stat
::: stat-value
12
:::

::: stat-label
Categories
:::
:::

::: stat
::: stat-value
3
:::

::: stat-label
Channels
:::
:::

::: stat
::: stat-value
2h
:::

::: stat-label
Agent Cycle
:::
:::
:::
:::

------------------------------------------------------------------------

::: section
## Razorpay API Usage {#razorpay-api-usage .section-title}

Razorpay\'s API is used in exactly **two places** across the system ---
one for reading data, one for receiving real-time events. Here\'s the
complete picture:

::: card
::: card-header
[1. Invoice Overdue Scanner --- GET /v1/invoices]{.card-title} [READ
ONLY]{.tag}
:::

**Where:** Workflow 2 → \"Fetch Razorpay Invoices\" node (HTTP Request)

**Endpoint:**
`https://api.razorpay.com/v1/invoices?type=invoice&status=issued&count=100`

**Auth:** HTTP Basic Auth using your Razorpay Key ID + Key Secret
(credential: \"Razor router\", ID: `frkgneFwFDPU9g7U`)

**Purpose:** Every 6 hours, polls Razorpay for all invoices with status
\"issued\" (meaning sent but not yet paid). For each invoice, it
calculates `days_overdue` based on the `due_date` field, then forwards
the data to the Recovery Router webhook for AI classification.

::: {.highlight-box style="margin-top:1rem;"}
**Why you see nothing on the Razorpay dashboard:** Your Razorpay account
currently has **zero real invoices**. The latest scheduled run
(execution 3400 at 04:00 UTC) successfully called the API and got
`{"count": 0, "items": []}`. The API is working --- there\'s just no
invoice data to fetch. To see it in action, create a test invoice in
Razorpay Dashboard → Invoices → Create Invoice with a past due date.
:::

::: node-detail
::: node-detail-title
Data Transformation
:::

Razorpay amounts are in **paise** (1/100th of a rupee). The node
converts: `amount / 100`

Days overdue: `Math.floor((now - due_date * 1000) / 86400000)`

Customer data extracted from: `customer_details.name`, `.email`,
`.contact`
:::
:::

::: card
::: card-header
[2. Recovery Tracker --- Webhook Receiver]{.card-title} [WEBHOOK]{.tag
.tag--green}
:::

**Where:** Workflow 3 → \"Payment Captured Webhook\" node

**Endpoint:**
`POST https://n8n.betiwonthearback.com/webhook/recovery-tracker`

**Purpose:** Receives Razorpay `payment.captured` webhook events. When a
customer successfully pays, this workflow looks up the payment in
Supabase and marks the recovery event as \"recovered\" --- closing the
measurement loop.

**Setup required:** In Razorpay Dashboard → Settings → Webhooks → Add
this URL and select the `payment.captured` event. This hasn\'t been
configured yet, which is why the tracker hasn\'t fired from live events.

::: node-detail
::: node-detail-title
Webhook Payload Parsing
:::

Extracts from Razorpay\'s nested structure: `payload.payment.entity.id`,
`.amount`, `.order_id`, `.method`
:::
:::

::: card
::: card-header
[What Razorpay API is NOT used for]{.card-title} [IMPORTANT]{.tag
.tag--amber}
:::

The Recovery Router webhook, Escalation Agent, and Analytics API do
**not** call Razorpay directly. Payment failure events and cart
abandonment events are sent to the Recovery Router via its webhook
endpoint --- in production, these would come from your app\'s backend
when Razorpay returns an error, or from your frontend when a cart is
abandoned. The system is designed to be **event-driven**, not
polling-based (except for invoices, which have no webhook event for
\"overdue\").
:::
:::

------------------------------------------------------------------------

::: section
## Features {#features .section-title}

::: feature-grid
::: feature-item
::: feature-bullet
:::

**AI-powered leak classification** --- GPT-5 Mini classifies every
revenue leak into one of 12 failure categories with calibrated recovery
probability scores
:::

::: feature-item
::: feature-bullet
:::

**Three input types, one pipeline** --- payment failures, cart
abandonment, and overdue invoices all flow through the same classify →
route → act → measure pipeline
:::

::: feature-item
::: feature-bullet
:::

**Intelligent channel routing** --- AI selects the optimal recovery
channel (WhatsApp, Email, SMS, or No Action) based on failure type,
amount, and recovery probability
:::

::: feature-item
::: feature-bullet
:::

**Autonomous escalation agent** --- every 2 hours, AI reviews pending
cases, decides the next action (channel switch, tone escalation, or give
up), sends messages, logs attempts, and updates state --- a true
observe-reason-act loop
:::

::: feature-item
::: feature-bullet
:::

**Multi-channel message delivery** --- WhatsApp (via Twilio), Email (via
SendGrid), SMS (via Twilio) with personalized, context-aware messages
including retry links
:::

::: feature-item
::: feature-bullet
:::

**Escalation strategy engine** --- 5-level escalation from friendly
reminder → firm follow-up → urgent → final notice → give up, with
channel switching between attempts
:::

::: feature-item
::: feature-bullet
:::

**Fraud detection and blocking** --- fraud/stolen card events are
classified with probability 0, automatically marked as exhausted with no
contact attempted
:::

::: feature-item
::: feature-bullet
:::

**Recovery tracking (feedback loop)** --- listens for Razorpay
payment.captured webhooks, matches against pending events, marks
recoveries to measure ROI
:::

::: feature-item
::: feature-bullet
:::

**Invoice overdue scanner** --- polls Razorpay API every 6 hours for
overdue invoices, calculates days overdue, auto-feeds into recovery
pipeline
:::

::: feature-item
::: feature-bullet
:::

**Real-time analytics API** --- GET endpoint returning aggregate
metrics: recovery rate, amount recovered, breakdowns by event type,
channel, and failure category
:::

::: feature-item
::: feature-bullet
:::

**72-hour recovery window** --- each event gets a timed recovery window;
the agent respects it and stops attempting after expiry
:::

::: feature-item
::: feature-bullet
:::

**Attempt logging and memory** --- every recovery attempt is logged to
`recovery_attempts` table with channel, strategy, message ID, and
outcome
:::

::: feature-item
::: feature-bullet
:::

**Smart timing** --- AI schedules next actions based on failure type:
immediate for UPI timeouts, 30 min for bank downtime, 1 hour for cart
abandonment, 4 hours for insufficient funds
:::

::: feature-item
::: feature-bullet
:::

**Opt-out and max-attempts guardrails** --- respects opted_out flag and
max_attempts (default 5) to prevent over-contacting customers
:::
:::
:::

------------------------------------------------------------------------

::: section
## Tech Stack {#tech-stack .section-title}

::: table-wrap
  Stack                          Purpose
  ------------------------------ -------------------------------------------------------------------------
  n8n (self-hosted on Railway)   Workflow orchestration engine --- all 5 production workflows
  Supabase / PostgreSQL          Persistence layer --- `recovery_events` and `recovery_attempts` tables
  OpenAI GPT-5 Mini              AI classification (Recovery Router) and escalation reasoning (Agent)
  Structured Output Parser       Forces AI responses into validated JSON schemas --- no parsing failures
  Razorpay API                   Invoice fetching (GET /v1/invoices) and payment webhook receiver
  Twilio                         WhatsApp and SMS message delivery
  SendGrid                       Email delivery with HTML templates
  React (planned)                Frontend dashboard --- connecting to Analytics API
  FastAPI (planned)              Production backend --- porting n8n logic to code
:::
:::

::: section
## Credentials Map {#credentials-map .section-title}

::: table-wrap
  Credential         Type            ID                   Used By
  ------------------ --------------- -------------------- --------------------------------------------------
  Supabase routing   supabaseApi     `gm8ZsBdGRtG7Ohlk`   All Supabase nodes (7 nodes across 4 workflows)
  OpenAI account     openAiApi       `ucY4ufVmzS2UNai3`   GPT-5 Mini in Recovery Router + Escalation Agent
  Razor router       httpBasicAuth   `frkgneFwFDPU9g7U`   Invoice Overdue Scanner (Razorpay API auth)
  Twilio account     twilioApi       `zy0whALRfEa1czn3`   Send WhatsApp/SMS nodes (5 nodes)
  SendGrid account   sendGridApi     `j5d8Aem1m1f0EamE`   Send Email nodes (2 nodes)
:::
:::

------------------------------------------------------------------------

::: section
## Workflow 1: Recovery Router {#workflow-1-recovery-router .section-title}

::: card
::: card-header
[The Classification Engine]{.card-title} [ACTIVE]{.tag .tag--green}
[WEBHOOK]{.tag} [14 NODES]{.tag}
:::

**ID:** `qWboQxSvPDSiyg4d`

**Webhook:**
`POST https://n8n.betiwonthearback.com/webhook/recovery-router`

**Purpose:** Receives any revenue leak event, classifies it with AI,
logs to Supabase with full agent metadata, routes to the optimal
recovery channel, sends the first recovery message, and logs the
attempt.

::: flow
[Webhook]{.flow-node} [→]{.flow-arrow} [Normalize (15
fields)]{.flow-node} [→]{.flow-arrow} [AI Classify (GPT-5
Mini)]{.flow-node} [→]{.flow-arrow} [Log to Supabase]{.flow-node}
[→]{.flow-arrow} [Route Switch]{.flow-node} [→]{.flow-arrow} [Send + Log
Attempt]{.flow-node}
:::
:::

::: node-detail
::: node-detail-title
Recovery Router Webhook
:::

**Type:** n8n-nodes-base.webhook (v2.1)   **Method:** POST   **Path:**
/recovery-router

Entry point for all three event types. Accepts JSON body with:
`event_type`, `payment_id`, `amount`, `currency`, `method`,
`error_code`, `customer_email`, `customer_phone`, `customer_name`,
`order_id`, `invoice_id`, `cart_value`, `items_in_cart`, `days_overdue`
:::

::: node-detail
::: node-detail-title
Normalize Event Data
:::

**Type:** n8n-nodes-base.set (v3.4)

Extracts and normalizes 15 fields from `$json.body.*` with null-safe
defaults. Converts raw webhook payload into a clean, consistent object
regardless of which event type was sent. Adds `event_timestamp` as ISO
string.
:::

::: node-detail
::: node-detail-title
Classify Revenue Leak
:::

**Type:** \@n8n/n8n-nodes-langchain.agent (v3.1)   **Sub-nodes:** OpenAI
GPT-5 Mini + Classification Parser

AI Agent with a detailed system prompt containing classification rules
for all 12 failure categories. Uses Structured Output Parser to force
JSON schema compliance. The prompt template uses `={{ }}` expressions to
inject normalized event data. Output is wrapped under `.output.*`
prefix.
:::

::: node-detail
::: node-detail-title
Log Recovery Event
:::

**Type:** n8n-nodes-base.supabase (v1)   **Operation:** INSERT into
`recovery_events`

Inserts 23 fields including all normalized event data, all AI
classification results (via `$json.output.*`), and agent metadata:
`attempt_count=0`, `current_strategy='initial'`, `escalation_level=0`,
`recovery_window_ends=now+72h`, and computed `next_action_at` based on
recommended_timing.
:::

::: node-detail
::: node-detail-title
Route by Channel
:::

**Type:** n8n-nodes-base.switch (v3.4)   **Outputs:** WhatsApp \| Email
\| SMS \| No Action (fallback)

Reads `$("Classify Revenue Leak").item.json.output.recommended_channel`
and routes to the matching output. \"none\" falls through to the No
Action fallback.
:::

::: node-detail
::: node-detail-title
Send WhatsApp / Send Recovery Email / Send SMS
:::

**Types:** Twilio (v1) / SendGrid (v1) / Twilio (v1)   **Error
handling:** continueRegularOutput

**WhatsApp/SMS:** From +17372508034 → customer phone. Personalized
message with name, amount, failure category, and retry link. WhatsApp
node has `toWhatsapp: false` (sends SMS due to Twilio trial).

**Email:** From abishekialbert@gmail.com. HTML template with heading,
personalized body, \"Complete Payment\" CTA link, and AI reasoning.
:::

::: node-detail
::: node-detail-title
Log WhatsApp/Email/SMS Attempt
:::

**Type:** n8n-nodes-base.supabase (v1)   **Operation:** INSERT into
`recovery_attempts`

Records: `recovery_event_id` (from Log Recovery Event),
`attempt_number=1`, `channel_used`, `action_taken` (from AI),
`message_id` (Twilio SID or SendGrid header), `outcome='sent'`.
:::

::: node-detail
::: node-detail-title
Log No Action
:::

**Type:** n8n-nodes-base.set (v3.4)

For events routed to \"No Action\" (fraud, low-value carts). Logs the
skip reason from AI classification.
:::

### Classification Categories {#classification-categories style="font-size:1rem;font-weight:600;margin:1.5rem 0 0.75rem;"}

::: table-wrap
  Category                  Event Type         Probability   Channel    Timing
  ------------------------- ------------------ ------------- ---------- -----------
  upi_timeout               payment_failure    0.75--0.85    WhatsApp   Immediate
  bank_downtime             payment_failure    0.70--0.85    WhatsApp   30 min
  card_expired              payment_failure    0.40--0.60    Email      Immediate
  insufficient_funds        payment_failure    0.30--0.50    SMS        4 hours
  fraud_detected            payment_failure    0             None       ---
  high_intent_abandonment   cart_abandonment   0.30--0.50    WhatsApp   1 hour
  browse_only_abandonment   cart_abandonment   0.05--0.10    None       ---
  recently_overdue          invoice_overdue    0.60--0.80    WhatsApp   Immediate
  moderately_overdue        invoice_overdue    0.30--0.50    Email      Immediate
  long_overdue              invoice_overdue    0.10--0.20    Email      ---
:::
:::

------------------------------------------------------------------------

::: section
## Workflow 2: Invoice Overdue Scanner {#workflow-2-invoice-overdue-scanner .section-title}

::: card
::: card-header
[Razorpay Invoice Poller]{.card-title} [ACTIVE]{.tag .tag--green}
[SCHEDULED]{.tag} [4 NODES]{.tag}
:::

**ID:** `iCqvY2FsG4qwnrH5`

**Schedule:** Every 6 hours

**Purpose:** Automatically discovers overdue invoices from Razorpay and
feeds them into the Recovery Router for classification and recovery.
This is the only workflow that calls the Razorpay API directly.

::: flow
[Schedule (6h)]{.flow-node} [→]{.flow-arrow} [GET Razorpay
/v1/invoices]{.flow-node} [→]{.flow-arrow} [Split Items]{.flow-node}
[→]{.flow-arrow} [POST → Recovery Router]{.flow-node}
:::
:::

::: node-detail
::: node-detail-title
Every 6 Hours
:::

**Type:** scheduleTrigger (v1.3)   Fires at 00:00, 06:00, 12:00, 18:00
UTC
:::

::: node-detail
::: node-detail-title
Fetch Razorpay Invoices
:::

**Type:** httpRequest (v4.4)   **Auth:** httpBasicAuth (\"Razor
router\")

**URL:**
`https://api.razorpay.com/v1/invoices?type=invoice&status=issued&count=100`

Fetches up to 100 issued (unpaid) invoices. Response:
`{"entity":"collection","count":N,"items":[...]}`
:::

::: node-detail
::: node-detail-title
Split Invoice Items
:::

**Type:** splitOut (v1)   Splits `items` array so each invoice is
processed individually.
:::

::: node-detail
::: node-detail-title
Send to Recovery Router
:::

**Type:** httpRequest (v4.4)   **Method:** POST

Transforms each Razorpay invoice into the Recovery Router\'s expected
format: converts amount from paise to rupees, extracts customer details,
calculates `days_overdue`, and POSTs to the webhook.
:::
:::

------------------------------------------------------------------------

::: section
## Workflow 3: Recovery Tracker {#workflow-3-recovery-tracker .section-title}

::: card
::: card-header
[The Feedback Loop]{.card-title} [ACTIVE]{.tag .tag--green}
[WEBHOOK]{.tag} [6 NODES]{.tag}
:::

**ID:** `i0Nku6eWdDUj05Dx`

**Webhook:**
`POST https://n8n.betiwonthearback.com/webhook/recovery-tracker`

**Purpose:** Closes the measurement loop. When a payment is captured
(customer pays), this workflow checks if there\'s a matching pending
recovery event and marks it as recovered --- proving the recovery action
worked.

::: flow
[Payment Captured Webhook]{.flow-node} [→]{.flow-arrow} [Extract Payment
Data]{.flow-node} [→]{.flow-arrow} [Find Recovery Event]{.flow-node}
[→]{.flow-arrow} [If Found?]{.flow-node} [→]{.flow-arrow} [Mark
Recovered / Log Organic]{.flow-node}
:::
:::

::: node-detail
::: node-detail-title
Payment Captured Webhook
:::

**Type:** webhook (v2.1)   **Path:** /recovery-tracker   **Method:**
POST

Receives Razorpay `payment.captured` webhook events. Must be configured
in Razorpay Dashboard → Webhooks.
:::

::: node-detail
::: node-detail-title
Extract Payment Data
:::

**Type:** set (v3.4)   Extracts `payment_id`, `amount`, `order_id`,
`method`, `captured_at` from Razorpay\'s nested payload structure.
:::

::: node-detail
::: node-detail-title
Find Recovery Event
:::

**Type:** supabase (v1)   **Operation:** getAll with filters

Queries `recovery_events` where
`payment_id = $json.payment_id AND status = 'pending'`. Limit 1.
:::

::: node-detail
::: node-detail-title
Recovery Event Found? → Mark as Recovered / Log Organic
:::

**If found:** Updates the event: `status='recovered'`,
`recovered_at=now`, `recovered_amount=payment.amount`

**If not found:** Logs as \"organic_payment\" --- customer paid without
a matching recovery event (normal checkout, not a recovery).
:::
:::

------------------------------------------------------------------------

::: section
## Workflow 5: Escalation Agent {#workflow-5-escalation-agent .section-title}

::: card
::: card-header
[The Autonomous AI Agent]{.card-title} [AI AGENT]{.tag .tag--purple}
[ACTIVE]{.tag .tag--green} [13 NODES]{.tag}
:::

**ID:** `PaPzRiBHQaAw5nF0`

**Schedule:** Every 2 hours

**Purpose:** The TRUE autonomous agent. Every 2 hours: observes all
pending events, reasons about the optimal next action for each, acts
(sends messages via the right channel), logs every attempt, updates
state (attempt count, escalation level, next action time), and stops
when recovery window expires or max attempts reached.

::: flow
[Schedule (2h)]{.flow-node} [→]{.flow-arrow} [Fetch Pending]{.flow-node}
[→]{.flow-arrow} [Filter Actionable]{.flow-node} [→]{.flow-arrow} [AI
Escalation Decision]{.flow-node} [→]{.flow-arrow} [Route]{.flow-node}
[→]{.flow-arrow} [Send]{.flow-node} [→]{.flow-arrow} [Log
Attempt]{.flow-node} [→]{.flow-arrow} [Update State]{.flow-node}
:::
:::

::: node-detail
::: node-detail-title
Fetch Pending Events
:::

**Type:** supabase (v1)   **Operation:** getAll where
`status = 'pending'`, returnAll=true
:::

::: node-detail
::: node-detail-title
Filter Actionable
:::

**Type:** code (v2)   **Mode:** runOnceForAllItems

JavaScript filter that removes events that are: opted out, past their
recovery window, at max attempts, or not yet due for next action
(respects `next_action_at` scheduling). Only actionable events proceed.
:::

::: node-detail
::: node-detail-title
Escalation Decision
:::

**Type:** \@n8n/n8n-nodes-langchain.agent (v3.1)   **Sub-nodes:** OpenAI
Model (GPT-5 Mini) + Escalation Parser

AI Agent with escalation strategy rules. Prompt injects all event data
via `={{ }}` expressions. System prompt defines: 5-level escalation
strategy, channel selection by probability tier
(aggressive/moderate/conservative), message tone escalation (friendly →
firm → urgent → final), and give_up rules for fraud/exhausted cases.

**Output schema:**
`{ next_channel, message_text, escalation_level, strategy, reasoning }`

**Error handling:** continueRegularOutput --- if AI fails for one item,
the rest still process.
:::

::: node-detail
::: node-detail-title
Route Escalation
:::

**Type:** switch (v3.2)   **Outputs:** WhatsApp \| Email \| SMS \| Give
Up (fallback)

Routes on `$json.output.next_channel`. \"give_up\" and any unknown value
fall through to the Give Up output.
:::

::: node-detail
::: node-detail-title
Send WhatsApp Esc / Send Email Esc / Send SMS Esc
:::

**Types:** Twilio / SendGrid / Twilio   **Error handling:**
continueRegularOutput

Uses AI-generated `message_text` from the Escalation Decision. Customer
contact info pulled from `$("Filter Actionable").item.json`.
:::

::: node-detail
::: node-detail-title
Mark Exhausted
:::

**Type:** supabase (v1)   **Operation:** UPDATE `recovery_events`

For \"give_up\" items: sets `status='exhausted'`,
`current_strategy='exhausted'`. Matches on
`id = $("Filter Actionable").item.json.id`.
:::

::: node-detail
::: node-detail-title
Log Escalation Attempt
:::

**Type:** supabase (v1)   **Operation:** INSERT into `recovery_attempts`

Records: `recovery_event_id`, `attempt_number` (current + 1),
`channel_used` (from AI), `action_taken` (strategy), `message_id`
(Twilio SID), `outcome='sent'`.
:::

::: node-detail
::: node-detail-title
Update Event State
:::

**Type:** supabase (v1)   **Operation:** UPDATE `recovery_events`

Updates: `attempt_count++`, `last_attempt_at=now`, `escalation_level`
(from AI), `current_strategy` (from AI), `next_action_at=now+4h`.
:::

### Escalation Strategy Matrix {#escalation-strategy-matrix style="font-size:1rem;font-weight:600;margin:1.5rem 0 0.75rem;"}

::: table-wrap
  Attempt     Action                                          Tone
  ----------- ----------------------------------------------- --------------------------------
  0 (first)   Use originally recommended channel              Friendly reminder
  1           Switch channel (WhatsApp↔Email, SMS→WhatsApp)   Firm follow-up
  2           SMS with urgent language                        Urgent --- time-sensitive
  3           Email final notice                              Formal --- mentions escalation
  4+          Give up                                         ---
:::
:::

------------------------------------------------------------------------

::: section
## Workflow 6: Recovery Analytics API {#workflow-6-recovery-analytics-api .section-title}

::: card
::: card-header
[The Dashboard Backend]{.card-title} [ACTIVE]{.tag .tag--green}
[WEBHOOK]{.tag} [4 NODES]{.tag}
:::

**ID:** `N0qClQhURICRTvbU`

**Endpoint:**
`GET https://n8n.betiwonthearback.com/webhook/recovery-analytics`

**Purpose:** Returns aggregate recovery metrics as JSON. Powers the
React dashboard. Includes CORS headers for cross-origin access.

::: flow
[GET Webhook]{.flow-node} [→]{.flow-arrow} [Fetch All
Events]{.flow-node} [→]{.flow-arrow} [Compute Analytics
(JS)]{.flow-node} [→]{.flow-arrow} [Respond with JSON]{.flow-node}
:::
:::

::: node-detail
::: node-detail-title
Compute Analytics
:::

**Type:** code (v2)   **Mode:** runOnceForAllItems

JavaScript that aggregates all events into: `summary` (total, recovered,
pending, exhausted counts, recovery rate %, amounts), `by_event_type`
(payment_failure, cart_abandonment, invoice_overdue), `by_channel`
(whatsapp, email, sms, none), `by_failure_category` (all 12 categories
with avg probability).
:::

::: node-detail
::: node-detail-title
Respond with Analytics
:::

**Type:** respondToWebhook (v1.1)   Response body:
`{{ JSON.stringify($json) }}`

Headers: `Access-Control-Allow-Origin: *`,
`Content-Type: application/json`
:::
:::

------------------------------------------------------------------------

::: section
## Database Schema {#database-schema .section-title}

::: card
::: card-header
[recovery_events]{.card-title} [PRIMARY TABLE]{.tag}
:::

Every revenue leak event, from intake through resolution. Contains both
the original event data, AI classification results, and agent state
columns for the escalation loop.

    -- Event data
    id, event_type, payment_id, order_id, invoice_id, amount, currency
    customer_email, customer_phone, customer_name

    -- AI classification
    leak_type, failure_category, recovery_probability
    recommended_action, recommended_channel, recommended_timing, reasoning

    -- Status tracking
    status (pending | recovered | exhausted), recovered_at, recovered_amount

    -- Agent state (escalation loop)
    attempt_count, last_attempt_at, max_attempts (default 5)
    current_strategy, next_action_at, opted_out
    recovery_window_ends (created_at + 72h), escalation_level

    -- Timestamps
    created_at, updated_at
:::

::: card
::: card-header
[recovery_attempts]{.card-title} [AGENT MEMORY]{.tag}
:::

Every recovery action taken --- the agent\'s memory. Links back to the
recovery event and records what was done, through which channel, and the
outcome.

    id, recovery_event_id (FK → recovery_events.id)
    attempt_number, channel_used, action_taken
    message_content, message_id, sent_at
    outcome (sent | delivered | failed | responded)
    response_received_at, notes, created_at
:::
:::

------------------------------------------------------------------------

::: section
## Recent Executions (All Green) {#recent-executions-all-green .section-title}

::: table-wrap
  ID     Workflow                  Status                        Started     Duration   Notes
  ------ ------------------------- ----------------------------- ----------- ---------- -------------------------------------------------------------------------------------
  3400   Invoice Overdue Scanner   [SUCCESS]{.tag .tag--green}   04:00 UTC   1s         Scheduled. Razorpay returned 0 invoices (none in account).
  3399   Escalation Agent          [SUCCESS]{.tag .tag--green}   04:00 UTC   69s        Scheduled. Processed 5 items: 2→WhatsApp, 1→SMS, 2→Give Up (exhausted). All logged.
  3398   Analytics API             [SUCCESS]{.tag .tag--green}   03:05 UTC   \<1s       Manual test. Returned full analytics for 29 events.
  3397   Escalation Agent          [SUCCESS]{.tag .tag--green}   03:03 UTC   18s        Manual test. First run with fixed prompt + Mark Exhausted. All nodes worked.
  3396   Recovery Router           [SUCCESS]{.tag .tag--green}   03:03 UTC   7s         Manual test. Invoice overdue → classified → logged → WhatsApp → attempt logged.
:::
:::

------------------------------------------------------------------------

::: section
## System Architecture {#system-architecture .section-title}

::: card
How the workflows connect

``` {style="text-align:center;background:var(--surface-alt);font-size:0.75rem;line-height:2;"}
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Your App /      │     │  Invoice Overdue  │     │  Razorpay Webhook   │
│  Razorpay Events │     │  Scanner (6h)     │     │  payment.captured   │
│  (POST)          │     │  GET /v1/invoices │     │  (POST)             │
└────────┬─────────┘     └────────┬──────────┘     └──────────┬──────────┘
         │                        │                            │
         ▼                        ▼                            ▼
┌─────────────────────────────────────────┐     ┌──────────────────────┐
│         RECOVERY ROUTER (WF1)           │     │  RECOVERY TRACKER    │
│  Webhook → Normalize → AI Classify      │     │  (WF3)               │
│  → Log Supabase → Route → Send + Log   │     │  Find Event →        │
└────────────────────┬────────────────────┘     │  Mark Recovered      │
                     │ writes                    └───────────┬──────────┘
                     ▼                                       │ updates
              ┌──────────────┐                               │
              │   SUPABASE   │◄──────────────────────────────┘
              │  recovery_   │
              │  events +    │◄──── reads ──── ESCALATION AGENT (WF5)
              │  attempts    │                 Every 2h: Fetch → Filter
              └──────┬───────┘                 → AI Decide → Send
                     │                         → Log → Update State
                     │ reads
                     ▼
              ┌──────────────┐
              │  ANALYTICS   │
              │  API (WF6)   │──→ JSON response → React Dashboard
              └──────────────┘
    
```
:::
:::

------------------------------------------------------------------------

::: section
## Current Limitations {#current-limitations .section-title}

::: card
::: card-header
[Twilio Trial Account]{.card-title} [LIMITATION]{.tag .tag--amber}
:::

WhatsApp requires ContentSid templates (not available on trial). SMS to
Indian numbers requires templates. Only verified numbers can receive
messages. **Resolution:** Will switch to Resend (email) and other
providers (SMS/WhatsApp) in the FastAPI/React code version.
:::

::: card
::: card-header
[No Real Razorpay Invoices]{.card-title} [TEST DATA]{.tag .tag--amber}
:::

The Invoice Scanner returns 0 items because the Razorpay account has no
real invoices. Test events have been sent manually via webhook.
**Resolution:** Create test invoices in Razorpay Dashboard, or connect
to a live account.
:::

::: card
::: card-header
[Razorpay Webhook Not Configured]{.card-title} [SETUP NEEDED]{.tag
.tag--amber}
:::

The Recovery Tracker webhook URL hasn\'t been registered in Razorpay
Dashboard → Webhooks. Payment captures won\'t auto-trigger recovery
tracking until this is set up.
:::
:::
:::

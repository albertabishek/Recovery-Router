# Recovery Router - Event Data Analysis & Bug Report

**Date:** August 29, 2026
**Events analyzed:** Last 15 events (IDs 411–425) + all 312 exhausted events + 5 recovered events
**Purpose:** Identify all bugs, missing data, wrong values, display issues, and confusing terminology

---

## Summary of Findings

| # | Issue | Severity | Where |
|---|-------|----------|-------|
| 1 | 312 exhausted events have NO reason why they stopped | HIGH | Backend (old data) |
| 2 | 312 exhausted events still show a "next action" time (impossible) | HIGH | Backend (old data) |
| 3 | 312 exhausted events still show a "recovery window" (should be cleared) | MEDIUM | Backend (old data) |
| 4 | Delayed events (not-immediate timing) never got their first message sent | HIGH | Backend pipeline |
| 5 | "current_strategy" says "initial" forever for most events | MEDIUM | Backend pipeline |
| 6 | Frontend doesn't show the reason when recovery is stopped | HIGH | Frontend display |
| 7 | Recovered events show escalation_level = 0 (never updated) | LOW | Backend pipeline |
| 8 | Technical jargon everywhere - users can't understand the status labels | HIGH | Frontend UX |
| 9 | Fallback events show wrong/generic skip_reason text | MEDIUM | Backend classifier |
| 10 | "alternative_action" field never shown in frontend | LOW | Frontend display |
| 11 | No way to see WHY an event was classified a certain way in the list view | LOW | Frontend UX |
| 12 | UTF-8 encoding broken for rupee symbol (₹) in AI responses | LOW | Backend/Display |

---

## Detailed Analysis: Last 15 Events (IDs 411–425)

### Event #425 - Bank Server Down (Netbanking ₹4,999)
- **Status:** Pending (actively being recovered)
- **What happened:** Payment failed because the bank server was temporarily offline. AI correctly identified this and sent a WhatsApp message within 5 minutes.
- **What's right:** escalation_level=1, attempt_count=1, recovery_probability=82%, channel=whatsapp
- **What's wrong:**
  - `current_strategy` still says "initial" - should say something like "first message sent" after the first attempt
  - The next attempt is scheduled for 4 hours later. For a bank downtime (temporary issue), 4 hours is too long - the bank could be back in 30 minutes

### Event #424 - Bank Server Down (Netbanking ₹4,999) - duplicate of 425
- **Status:** Pending
- **Same issues as #425** - these are from the same test run

### Event #423 - Payment System Error (UPI ₹1,599)
- **Status:** Pending
- **What happened:** The payment gateway had a technical error. AI sent WhatsApp immediately.
- **What's right:** escalation_level=1, attempt_count=1, probability=78%
- **What's wrong:**
  - `current_strategy` = "initial" (same issue - not updated after first attempt)

### Event #422 - Payment Timed Out (UPI ₹4,999)
- **Status:** Pending
- **What happened:** UPI payment timed out. WhatsApp sent immediately. Customer later tried to pay via card on the recovery link but cancelled the payment.
- **What's right:** escalation_level=1, 2 attempts logged (1 sent + 1 customer-cancelled)
- **What's wrong:**
  - `attempt_count` = 1 but there are actually 2 attempts in history (the customer's failed retry was logged as attempt #2 but didn't increment the event's attempt_count) - this means the count shown in the UI (1/4) is misleading
  - `current_strategy` = "initial" still, even though customer already tried and cancelled

### Event #421 - Customer Browsed But Didn't Buy (Cart ₹149)
- **Status:** No Action Needed
- **What happened:** Low-value cart (₹149, 1 item), no payment was even attempted. AI correctly decided not to chase this customer.
- **What's right:** status=no_action_needed, max_attempts=0, probability=15%
- **What's wrong:**
  - `skip_reason` = "Browse-only abandonment with no payment attempt and low cart value does not justify immediate outreach. Cost of recovery effort exceeds expected transaction value." - This is GOOD, but too technical for a normal user to understand
  - In the frontend, this event shows perfectly fine

### Event #420 - Suspected Fraud (Card ₹14,999)
- **Status:** No Action Needed
- **What happened:** Bank flagged payment as potentially fraudulent. FALLBACK classification (AI was unavailable).
- **What's right:** status=no_action_needed, probability=0, channel=none
- **What's wrong:**
  - `fallback_classification` = true - AI was unavailable, so the system used hardcoded rules instead. The reasoning says "Rule-based fallback (AI unavailable)" - this is honest but confusing for users
  - `recommended_action` = "fallback_none_recovery" - this is an internal code name, NOT a human-readable message. A user seeing this would have no idea what it means
  - `skip_reason` = "Unrecoverable decline" - very short and unhelpful compared to event #415 (same scenario but WITH AI) which has a full paragraph explaining why

### Event #419 - Invoice Very Late (54 days overdue, ₹30,000)
- **Status:** Pending
- **What happened:** Invoice is 54 days late. AI recommended formal email with payment deadline.
- **What's right:** channel=email, probability=25%, max_attempts=3, escalation_level=1
- **What's wrong:**
  - `current_strategy` = "initial" (same persistent bug)

### Event #418 - Invoice Recently Late (2 days overdue, ₹5,000)
- **Status:** Pending
- **What happened:** Invoice just went overdue. AI sent a friendly email reminder.
- **What's right:** channel=email, probability=75%, max_attempts=5, escalation_level=1
- **What's wrong:**
  - `current_strategy` = "initial"

### Event #417 - Customer Browsed But Didn't Buy (Cart ₹99)
- **Status:** No Action Needed
- **What happened:** Very low value cart. FALLBACK classification.
- **What's wrong:**
  - `fallback_classification` = true - same issues as #420
  - `recommended_action` = "fallback_none_recovery" - internal code, not human-readable
  - `skip_reason` = "Unrecoverable decline" - WRONG! This is a low-value browsing cart, not a "declined" payment. The skip reason is completely incorrect for this scenario. It's using the same generic text for all fallback-classified events regardless of the actual situation
  - `recovery_probability` = 0.07 - AI set this correctly but then the fallback slapped a fraud-related skip reason on a browsing event

### Event #416 - Customer Left High-Value Cart (₹9,999, 4 items)
- **Status:** Pending
- **What happened:** Customer had 4 items worth ₹9,999 in cart but left without paying. AI recommended WhatsApp in 1 hour.
- **What's right:** failure_category=high_intent_abandonment, probability=72%, channel=whatsapp
- **What's wrong:**
  - `attempt_count` = 0, `escalation_level` = 0, `last_attempt_at` = null - because the timing was "1_hour" (delayed), the actual WhatsApp message hasn't been sent yet. The `_send_delayed` Celery task is supposed to fire in 1 hour, but...
  - **BIG ISSUE:** The `next_action_at` was set to 1 hour from creation (01:14 AM). If the Celery Beat/worker wasn't running at that exact time, or the delayed task failed silently, this event would sit forever with no message ever sent and no way to know why
  - No attempt history at all - empty

### Event #415 - Suspected Fraud (Card ₹14,999)
- **Status:** No Action Needed
- **What happened:** Same fraud scenario as #420, but THIS time AI was available.
- **What's right:** Fully detailed reasoning explaining why fraud flags can't be recovered. skip_reason has a complete explanation.
- **Contrast with #420:** Shows how much worse the fallback classification is - #420 has "Unrecoverable decline" (3 words) vs #415 which has a full paragraph explaining what to do

### Event #414 - Payment System Error (UPI ₹3,999)
- **Status:** Pending
- **What happened:** Gateway error on UPI. AI sent WhatsApp immediately.
- **What's right:** escalation_level=1, attempt_count=1, probability=78%
- **What's wrong:** `current_strategy` = "initial"

### Event #413 - Bank Server Down (Netbanking ₹4,999)
- **Status:** Pending
- **What happened:** Bank downtime. AI recommended WhatsApp in 30 minutes (delayed).
- **What's wrong:**
  - `attempt_count` = 0, `escalation_level` = 0 - DELAYED SEND. Same issue as #416. The message was supposed to be sent 30 minutes later, but it's been hours and still attempt_count=0
  - `next_action_at` = 00:44 AM - this was when the delayed send should have happened. It's now long past. Either the delayed task failed or the Celery worker wasn't processing it
  - This event is stuck: it looks like it's "pending" and has a scheduled action, but that action time is already in the past

### Event #412 - Not Enough Money in Account (Card ₹4,999)
- **Status:** Pending
- **What happened:** Card payment failed due to insufficient funds. AI recommended SMS in 4 hours.
- **What's wrong:**
  - `attempt_count` = 0, `escalation_level` = 0 - DELAYED SEND. Same pattern as #413 and #416
  - `next_action_at` = 04:14 AM - the delayed send might not have fired yet (or might have)

### Event #411 - Card Has Expired (Card ₹3,499)
- **Status:** Pending
- **What happened:** Customer's card expired. AI sent WhatsApp immediately.
- **What's right:** escalation_level=1, attempt_count=1, probability=72%
- **What's wrong:** `current_strategy` = "initial"

---

## Analysis: All 312 Exhausted Events

Checked the top 5 exhausted events (IDs 399, 374, 357, 356, 355). ALL of them have:

| Field | Current Value | Should Be |
|-------|--------------|-----------|
| `skip_reason` | `null` (empty!) | Should explain WHY recovery stopped (e.g., "All 4 attempts used" or "Recovery window expired") |
| `next_action_at` | Still has a date/time | Should be `null` - there IS no next action, recovery is over |
| `recovery_window_ends` | Still has a date | Should be `null` - the window already passed |

**Root cause:** These 312 events were marked as "exhausted" by the OLD code (before my bug fixes). The old `_mark_exhausted` functions in `escalation.py` and `tasks/escalation.py` didn't clear `next_action_at`, didn't clear `recovery_window_ends`, and didn't set `skip_reason`.

**The fix is in the code now** - newly exhausted events will get correct values. But the 312 existing events need a one-time database cleanup.

---

## Analysis: 5 Recovered Events

All 5 recovered events (IDs 203, 184, 182, etc.) have `escalation_level` = 0.

**Root cause:** These events were recovered (customer paid) BEFORE I fixed the code to set `escalation_level = 1` after the first attempt. The `handle_payment_captured` webhook handler doesn't update escalation_level when marking as recovered - it only existed events that were already at level 0.

---

## Bug List - Organized by Priority

### CRITICAL (Must fix before demo)

**BUG 1: Delayed sends might be silently failing**
- Events with timing like "1_hour", "30_minutes", "4_hours" schedule a delayed Celery task
- Events #416 (1 hour delay), #413 (30 min delay), #412 (4 hour delay) all have `attempt_count = 0`
- The delayed task may have failed, or the Celery worker may not have been running when it was due
- **Impact:** Customers who need follow-up after a delay are NEVER getting contacted
- **Location:** `backend/app/tasks/recovery.py` → `_send_delayed` task

**BUG 2: 312 exhausted events have broken data (missing reason, stale dates)**
- All previously-exhausted events have null `skip_reason`, stale `next_action_at`, stale `recovery_window_ends`
- The code fix is already in place for NEW events, but existing data needs migration
- **Impact:** Users looking at old exhausted events see no explanation for why recovery stopped, and confusing dates that imply actions are still scheduled

**BUG 3: Fallback classification produces wrong/misleading data**
- When AI is unavailable, the fallback classifier sets:
  - `recommended_action` = "fallback_none_recovery" (internal code name)
  - `skip_reason` = "Unrecoverable decline" (WRONG for non-fraud scenarios like low-value carts)
  - `reasoning` = "Rule-based fallback (AI unavailable). Matched error_code=None"
- Event #417 (low-value cart) incorrectly gets "Unrecoverable decline" as skip reason
- **Impact:** Users see incorrect reasons for why events were skipped
- **Location:** `backend/app/services/classifier.py` → fallback classification logic

### HIGH (Should fix)

**BUG 4: `current_strategy` never updates after first attempt**
- Every event that gets a message sent still shows `current_strategy = "initial"`
- It only changes when the escalation cycle runs and updates it to the AI's "tone" decision
- For the first attempt, the pipeline sets "initial" and never changes it to something meaningful
- **Impact:** The strategy field is useless for first-attempt events - you can't tell if a message was sent or not from this field alone
- **Location:** `backend/app/tasks/recovery.py` lines 150-157

**BUG 5: `attempt_count` doesn't include customer's own retry attempts**
- Event #422: attempt_count=1 but there are 2 entries in attempt history (1 system-sent + 1 customer-cancelled)
- The `handle_recovery_retry_failure` task logs the attempt but doesn't increment `attempt_count`
- **Impact:** The progress display (e.g., "1/4 attempts") understates the actual number of interactions
- **Location:** `backend/app/tasks/recovery.py` → `handle_recovery_retry_failure` (line ~218-223)

**BUG 6: Frontend doesn't show "alternative_action" field**
- Every AI-classified event has a thoughtful `alternative_action` like "If WhatsApp fails, send SMS" or "Follow up with email after 30 minutes"
- This is never displayed anywhere in the frontend
- **Impact:** Users miss useful AI-generated backup strategies

### MEDIUM (Should fix before launch)

**BUG 7: 4-hour fixed delay between all retry attempts**
- Every event gets `next_action_at = now + 4 hours` regardless of urgency
- UPI timeout (customer is actively waiting) gets same 4-hour delay as insufficient funds (customer needs time)
- The AI's `recommended_timing` is only used for the FIRST attempt; all subsequent retry delays are hardcoded to 4 hours
- **Impact:** Suboptimal recovery timing - urgent cases wait too long, non-urgent cases might be too frequent
- **Location:** `backend/app/tasks/recovery.py` line 154, `backend/app/services/escalation.py` line 274

**BUG 8: `recovery_window_ends` not cleared for no_action_needed events that are then marked as such during insert**
- The `process_recovery_event` correctly clears it for `no_action` events, but the initial insert always sets it
- This means for a brief moment, no_action events have a recovery window (then it's removed in the update)
- **Impact:** Minor - the update removes it. But it's a two-step operation that could fail partway

**BUG 9: UTF-8 encoding issues in AI responses**
- The rupee symbol (₹) appears as garbled text: "â‚¹" instead of "₹"
- Dashes appear as "â€"" instead of "-"
- Visible in: reasoning, recommended_action, alternative_action fields
- **Impact:** AI explanations look broken to users
- **Location:** Likely an encoding mismatch when storing/retrieving from Supabase, or in the AI response parsing

---

## Technical Words That Need Renaming

| Current Term | What It Means | Suggested Human-Friendly Name |
|---|---|---|
| `pending` | Actively trying to get the customer to pay | **In Progress** or **Recovering** |
| `exhausted` | Tried everything and gave up | **Gave Up** or **Recovery Stopped** |
| `no_action_needed` | This event doesn't need any follow-up | **Skipped** or **No Follow-Up Needed** |
| `recovered` | Customer paid! | **Paid** or **Payment Received** |
| `paused` | An admin manually paused recovery | **On Hold** |
| `upi_timeout` | UPI payment took too long and expired | **Payment Timed Out** |
| `card_expired` | Customer's card has expired | **Card Expired** |
| `insufficient_funds` | Not enough money in the account | **Low Balance** |
| `bank_downtime` | Bank's servers are temporarily down | **Bank Offline** |
| `gateway_error` | Payment system had a technical error | **System Error** |
| `unrecoverable_decline` | Payment was permanently rejected (fraud, etc.) | **Permanently Declined** |
| `high_intent_abandonment` | Customer had items in cart and was close to buying | **Cart Left Behind** |
| `browse_only_abandonment` | Customer was just browsing, not serious about buying | **Just Browsing** |
| `recently_overdue` | Invoice is a few days late | **Recently Late** |
| `long_overdue` | Invoice is very late (30+ days) | **Very Late** |
| `fallback_classification` | AI was unavailable, so rules were used instead | **Rule-Based** (or hide this entirely) |
| `escalation_level` | How many times the urgency has been escalated | **Follow-Up Round** |
| `current_strategy` | The current approach being used | **Current Approach** |
| `attempt_count` / `max_attempts` | How many messages sent vs. budget | **Messages Sent / Message Limit** |
| `recovery_window_ends` | Deadline to stop trying | **Stop Trying After** |
| `next_action_at` | When the next message will be sent | **Next Message At** |
| `recommended_timing` | When the AI says to send the first message | **Send First Message** |
| `skip_reason` | Why I decided not to pursue this | **Reason** |
| `leak_type` | Category of revenue loss | **Loss Type** |
| `recovery_probability` | AI's estimate of how likely the payment will be recovered | **Recovery Chance** |

---

## Frontend Display Issues

### Issue 1: Exhausted events don't show the reason (when skip_reason is null)
- **Current:** The exhausted banner `{e.status === 'exhausted' && e.skip_reason && (...)}` only shows if skip_reason is non-null
- For 312 old events, skip_reason is null, so users see an exhausted event with NO explanation
- **Fix options:**
  - A) Show a generic fallback: "Recovery attempts completed" when skip_reason is null
  - B) Run a database migration to backfill skip_reason for old events

### Issue 2: "Exhausted" is confusing
- Users don't know what "exhausted" means in a payment recovery context
- Rename to "Recovery Stopped" or "Gave Up" in the UI

### Issue 3: Pipeline stage 3 ("Action Sent") is misleading for delayed events
- Events with delayed timing show "awaiting" in the pipeline, which is correct
- But there's no indication of WHEN the message will be sent or that it's waiting for a timer
- Users don't know if the system is broken or just waiting

### Issue 4: Category names shown as raw snake_case
- The code does `.replace(/_/g, ' ')` which turns "upi_timeout" into "upi timeout" - lowercase, no formatting
- Should be properly capitalized and human-friendly

### Issue 5: Fallback events show "fallback_none_recovery" as the recommended action
- This internal code name is shown directly to users in the detail panel
- Should be replaced with a human-readable description

### Issue 6: No visual distinction between AI-classified and fallback-classified events
- Users can't tell which events got real AI analysis vs. rule-based fallback
- The `fallback_classification` boolean exists but isn't used in the UI

### Issue 7: The "alternative_action" field is never displayed
- AI generates backup strategies but they're hidden from users

### Issue 8: Escalation level shown as raw number
- "Escalation Level: 0" or "Escalation Level: 1" means nothing to users
- Should show something like "Initial Contact" or "First Follow-Up"

---

## Recommended Fix Plan (in order)

### Phase 1: Database Cleanup (one-time)
1. Backfill `skip_reason` for all 312 exhausted events where it's null
2. Set `next_action_at = null` for all exhausted events
3. Set `recovery_window_ends = null` for all exhausted events where status is exhausted

### Phase 2: Backend Bug Fixes
4. Fix fallback classifier to use correct skip_reason per scenario (not "Unrecoverable decline" for everything)
5. Fix fallback classifier to use human-readable `recommended_action` (not "fallback_none_recovery")
6. Update `current_strategy` after first attempt (change from "initial" to something meaningful like "first_contact_sent")
7. Investigate why delayed sends (events #413, #416) have attempt_count=0 - check Celery logs
8. Fix `handle_recovery_retry_failure` to increment attempt_count when customer retries

### Phase 3: Frontend Improvements
9. Rename all technical status labels to human-friendly names
10. Show fallback message for exhausted events when skip_reason is null
11. Show `alternative_action` field in event detail
12. Show visual indicator for fallback-classified events (e.g., small badge)
13. Format category names properly (capitalized, readable)
14. Show escalation level as meaningful text instead of a number
15. Add delay indicator for events with scheduled sends

### Phase 4: Future Improvements
16. Make retry delay dynamic based on event type (not always 4 hours)
17. Fix UTF-8 encoding for rupee symbol in AI responses
18. Add monitoring/alerting for failed delayed sends

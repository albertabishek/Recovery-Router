# What Broke & How I Fixed It

*War stories from building Recovery Router. Every bug, every investigation, every lesson.*

Built by Albert Abishek I for the Razorpay AI Buildathon 2026 (Track 3).

---

## The Short Version

Building an AI-powered payment recovery system that handles real money means every bug is a potential financial incident. Over the course of this buildathon, I hit six significant bugs and several smaller challenges. Three of them were concurrency issues. One was an invisible ghost writing to my database. Here's what happened.

---

## Bug #1: The Premature Give-Up

**Severity:** P0 -- events dying after 1 attempt instead of using their full budget

### What Happened

I was watching the recovery pipeline process its first batch of events. An event worth Rs 15,000 with a recovery probability of 0.7 should have gotten 5 attempts. It got one. Then it was marked "exhausted." Budget of 5, used 1, done.

Every event was doing this. The AI escalation engine was giving up immediately.

### The Hunt

The escalation engine calls Claude Haiku (via OpenRouter) to decide the next recovery action: which channel, what tone, whether to keep trying or give up. The AI returns JSON with an `action` field -- either `"send"` or `"give_up"`.

I looked at what the AI was actually returning. Sometimes it returned well-formed JSON with `"action": "send"`. But sometimes it returned partial JSON, or JSON missing the `action` field entirely. When that happened, the schema parser filled in the default.

The default for `action` was `"give_up"`.

```python
# The bug: default was "give_up"
ESCALATION_SCHEMA = {
    "action": {"type": "str", "allowed": ["send", "give_up"], "default": "give_up"},
    ...
}
```

So any time the AI hiccupped -- returned incomplete JSON, skipped a field, hit a parsing edge case -- the system interpreted silence as "stop trying to recover this customer's money."

### The Fix

Three layers of defense, because one layer is never enough in financial software.

**Layer 1: Schema default.** Changed the default from `"give_up"` to `"send"` in `backend/app/services/escalation.py` (line 81). Now if the AI returns garbage, the system defaults to trying again, not giving up.

```python
ESCALATION_SCHEMA = {
    "action": {"type": "str", "allowed": ["send", "give_up"], "default": "send"},
    ...
}
```

**Layer 2: AI override.** After getting the AI's decision, the code checks: did the AI say give_up, but are there untried channels and remaining budget? If so, override to `"send"` and pick a different channel. This lives in `_get_escalation_decision()` (lines 310-351 of `escalation.py`):

```python
if result.get("action") == "give_up" and attempt_count < max_attempts:
    # Check if all channels truly exhausted
    if not all_truly_exhausted or attempt_count == 0:
        result = {
            "action": "send",
            "channel": _pick_next_channel(last_channel, event, avoid=blocked_chs),
            "tone": "firm" if attempt_count <= 2 else "urgent",
            "reasoning": f"Override: AI suggested give_up but {max_attempts - attempt_count} attempts remain.",
        }
```

**Layer 3: Hard guard.** Even after the AI override, the `run_escalation()` function has a final check (lines 136-155). If `action` is still `"give_up"` but `attempt_count < max_attempts`, it forces a send. This catches any code path that somehow bypasses Layer 2.

### The Lesson

In financial software, a single safety check is never enough. The AI is a suggestion engine, not a decision authority. Every destructive action (marking an event as exhausted = stopping recovery = potentially losing money) needs multiple independent guards. Defense in depth isn't paranoia -- it's engineering discipline.

---

## Bug #2: The TOCTOU Race Condition

**Severity:** P0 -- events still prematurely exhausted after Bug #1 fix

### What Happened

Bug #1 was fixed. The three-layer defense was in place. I was confident.

Then events #16 and #17 showed up as "exhausted" with only 1 attempt. The give-up prevention code was working -- I could see it in the logs. The AI wasn't saying give_up anymore. But the events were still dying early.

### The Hunt

I added more logging. The timeline told the story:

1. Event #16 is created with `delay_seconds=300` (5-minute delayed send)
2. `_send_delayed` task is queued with a 5-minute countdown
3. Five minutes pass. The Celery Beat escalation cycle runs (`run_escalation_cycle` in `backend/app/tasks/escalation.py`). It queries `recovery_events WHERE status='pending' AND next_action_at <= now`. Event #16 matches.
4. Simultaneously, the `_send_delayed` countdown expires. It also picks up event #16.
5. Both tasks read `status='pending'` from the database.
6. Both tasks proceed to process the event.
7. Task A sends the message, increments `attempt_count` to 1, and sees `1 >= max_attempts` for some edge case. Sets status to `"exhausted"`.
8. Task B, which read the old state, also tries to send. Its state update either conflicts or overwrites.

Classic TOCTOU (Time-Of-Check-To-Time-Of-Use). Two concurrent readers, both see "pending", both act, chaos ensues.

### The Fix

Three-pronged concurrency control in `backend/app/services/escalation.py` and `backend/app/tasks/recovery.py`:

**1. Optimistic concurrency via conditional updates.** Every database update that changes event state includes `.eq("status", "pending")` as a guard. If another task already changed the status, the update returns no rows and the task knows to back off.

```python
# From escalation.py _update_event_state() -- line 477
sb.table("recovery_events").update({
    ...
}).eq("id", event["id"]).eq("status", "pending").execute()
```

**2. Redis distributed locks.** Before processing any event, acquire a per-event lock using Redis SET NX with a 300-second TTL. If the lock is already held, skip the event. Both `run_escalation()` and `_send_delayed()` use this:

```python
# From escalation.py -- lines 87-94
def _acquire_event_lock(event_id: int, ttl: int = 300) -> bool:
    r = get_redis()
    return bool(r.set(f"lock:event:{event_id}", "1", nx=True, ex=ttl))
```

**3. Fresh state re-read after lock acquisition.** After acquiring the lock, the escalation engine re-reads the event from the database (lines 111-121). If the status is no longer "pending" (because another task already processed it), it skips. Similarly, `_send_delayed` checks `attempt_count > 0` after acquiring the lock -- if escalation already sent a message, the delayed task backs off (line 428 of `recovery.py`).

### The Lesson

Async systems need explicit serialization. "It works locally" means nothing when you have Celery Beat and countdown tasks hitting the same data from different workers. Every shared-state operation needs: a lock to prevent concurrent access, a re-read to catch stale state, and a conditional write to prevent lost updates. All three. Missing any one of them leaves a window for races.

---

## Bug #3: The Ghost Writer Mystery

**Severity:** P0 -- impossible database state, unknown writer

*This is the star story. This is the one I'd tell at an interview.*

### What Happened

Event #18 was marked `status='exhausted'`. That's not unusual -- events exhaust their budget all the time. But this one was different:

- `skip_reason` was `null`
- `next_action_at` was still set (not cleared)
- `current_strategy` was `"exhausted"` but not `"max_attempts_reached"` or `"window_expired"`

This state was impossible. Every code path in the application that sets `status='exhausted'` also sets `skip_reason` to a meaningful string and clears `next_action_at` to `null`. There was no code path that could produce this combination. I checked.

### The Investigation

This was the most thorough debugging session of the entire project. Here's what I checked, in order:

**1. Every code path that writes `status='exhausted'`.** There are exactly four:
- `_mark_exhausted()` in `escalation.py` -- always sets `skip_reason`, always clears `next_action_at`
- `_update_event_state()` in `escalation.py` -- same
- `_mark_window_expired()` in `tasks/escalation.py` -- always sets skip_reason
- `_mark_attempts_exhausted()` in `tasks/escalation.py` -- always sets skip_reason

None of them could produce `skip_reason=null` with `next_action_at` still set.

**2. Git history.** I went through every version of these files. Had there been a previous version that was buggier, and maybe a stale .pyc was still running? No. The current code was correct, and the worker files were fresh.

**3. Celery task results.** I checked Redis for the task results. All tasks for event #18 completed correctly. The escalation engine had processed it and the result was `"sent"`, not `"exhausted"`.

**4. Worker file timestamps vs .pyc timestamps.** Were the workers running old bytecode? No. Everything was current.

**5. Database triggers.** Were there any PostgreSQL triggers modifying state? Not at that point -- migration 004 (the trigger that would later fix this) hadn't been created yet.

**6. Manual SQL queries.** Had I accidentally run an UPDATE directly? I checked my terminal history. No.

I was stuck. The code couldn't produce this state. The workers were running the right code. No one was running manual queries. But the state existed.

### The Breakthrough

I was about to give up on the investigation when I remembered: this project didn't start as a pure Python/Celery system. It started with n8n workflows.

Early in development, I had built the escalation logic in n8n -- a visual workflow automation tool. Five workflows: Classify, Route, Escalate, Track, and Analytics. They connected directly to Supabase using n8n's built-in Supabase nodes, with their own database credentials. When I rebuilt the pipeline in Python for better control, I... forgot to unpublish the n8n workflows.

I opened the n8n workflow editor and found the "Mark Exhausted" node in `Escalation Agent.json`:

```json
{
  "fieldsUi": {
    "fieldValues": [
      {"fieldId": "status", "fieldValue": "exhausted"},
      {"fieldId": "current_strategy", "fieldValue": "exhausted"}
    ]
  }
}
```

There it was. The n8n node sets `status` to `"exhausted"` and `current_strategy` to `"exhausted"`. That's it. No `skip_reason`. No clearing `next_action_at`. No status guard (it doesn't check if the event is still pending). No budget check (it doesn't verify `attempt_count >= max_attempts`).

**Two independent systems were racing against each other with no mutual awareness.** The Python/Celery escalation engine was carefully managing event state with locks, conditional updates, and budget checks. Meanwhile, the n8n workflow was firing on its own schedule, writing directly to Supabase, blowing past every safety guard because it predated all of them.

The ghost writer was me, from two weeks ago.

### The Fix

**Immediate:** Unpublished all five n8n workflows. The Python pipeline was the source of truth now, and the n8n workflows were a liability.

**Permanent:** Created migration 004 (`backend/migrations/004_prevent_premature_exhaustion.sql`) -- a PostgreSQL BEFORE UPDATE trigger that acts as a database-level safety net:

```sql
CREATE OR REPLACE FUNCTION prevent_premature_exhaustion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.status = 'exhausted' AND (OLD.status IS NULL OR OLD.status != 'exhausted') THEN
    IF (COALESCE(NEW.attempt_count, 0) < COALESCE(NEW.max_attempts, 5))
       AND COALESCE(NEW.max_attempts, 5) > 0
       AND NEW.skip_reason IS NULL THEN
      RAISE WARNING 'Blocked premature exhaustion of event %: attempt_count=% < max_attempts=%',
        NEW.id, COALESCE(NEW.attempt_count, 0), COALESCE(NEW.max_attempts, 5);
      NEW.status := OLD.status;
      NEW.current_strategy := OLD.current_strategy;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
```

This trigger fires on every UPDATE to `recovery_events`, regardless of who's writing -- the Python backend, an n8n workflow, a manual SQL query, a future microservice, anything. If something tries to set `status='exhausted'` when `attempt_count < max_attempts` and no `skip_reason` is provided, the trigger silently reverts the status change and logs a warning.

The defense is now at the data layer, not just the application layer. No writer can bypass it.

### The Lesson

**When you can't find the bug in your code, look for systems you forgot were still running.** This is especially dangerous in projects that evolve -- you build version 1 with tool A, rebuild with tool B, but never fully decommission tool A. The old system keeps running, writing to the same database, with none of the safety guards you added in the rebuild.

And the deeper lesson: in financial software, the database trigger is your last line of defense. Application code can be bypassed by other applications. Business logic in the ORM can be bypassed by direct SQL. But a database trigger catches everything. If an invariant must never be violated (like "don't mark a recovery event as exhausted when attempts remain"), enforce it at the data layer.

---

## Bug #4: Railway Build Failures

**Severity:** P1 -- couldn't deploy the backend at all

### What Happened

The backend needed to be deployed somewhere. I chose Railway. It should have been simple: push code, Railway auto-detects Python, builds, deploys. Three attempts told a different story.

### The Three Attempts

**Attempt 1:** I added a `nixpacks.toml` with `python311` in the Nix packages list. Railway uses Nixpacks to build Docker images. The build ran... and failed with `pip: command not found`. The Nix `python311` package includes the Python interpreter but not pip.

**Attempt 2:** Added `python311Packages.pip` to the Nix packages. Build ran... `No module named pip`. The Nix pip package and the system Python were not friends.

**Attempt 3:** Deleted the entire `nixpacks.toml`. Removed all manual Nix configuration. Let Nixpacks auto-detect Python from `requirements.txt`. Build succeeded. Deployment worked.

The fix was in commit `ce859cf`: "Fix Railway build: let Nixpacks auto-detect Python instead of manual Nix packages."

### The Lesson

Don't fight the platform. Nixpacks is specifically designed to auto-detect Python projects from `requirements.txt` and set up the correct build environment. My manual Nix package configuration was overriding the auto-detection with a broken setup. The platform already knew how to do this -- I just needed to get out of its way.

---

## Bug #5: WhatsApp Personalization

**Severity:** P2 -- messages were correct but generic, losing the AI personalization advantage

### What Happened

One of Recovery Router's differentiators is AI-personalized messaging. The AI generates custom recovery messages based on the failure category, amount, attempt history, and customer context. A UPI timeout gets a different tone than a card expiry. A first attempt is friendly; a third attempt is urgent.

But WhatsApp messages were coming through as generic templates. "Hi {customer_name}, your payment of {amount} failed. Please retry." No personalization. No AI. Just a Twilio template.

### The Root Cause

Twilio's WhatsApp Business API requires pre-approved message templates. You can't send arbitrary text -- every message must use a `content_sid` that references a template approved by WhatsApp/Meta. The template has fixed structure with variable placeholders, but you can't change the wording, add AI-generated sentences, or adjust the tone.

This is a fundamental API limitation, not a bug in the code. Twilio WhatsApp is a template-only channel.

### The Fix

Restructured the messenger provider hierarchy in `backend/app/services/messenger.py`:

```
WhatsApp: Green API (personalized text) -> Twilio WhatsApp (template) -> Email
SMS:      Twilio SMS -> Green API WhatsApp -> Twilio WhatsApp -> Email
Email:    Resend (primary, with AI-personalized content)
```

Green API connects to WhatsApp via a direct phone number connection and supports free-form text messages. It became the primary WhatsApp provider, with Twilio demoted to template-based fallback. If Green API is unavailable, the system falls back to Twilio's template (better than nothing), and if that fails too, it degrades to email (which supports full HTML personalization via Resend).

The degradation path is tracked in every attempt's metadata as `degradation_path`, so the analytics dashboard shows exactly which events got personalized messages vs. template fallbacks.

### The Lesson

Not all APIs are equal, even for the same channel. Provider limitations shape architecture. When choosing between messaging providers, "supports WhatsApp" is not enough -- you need to know: does it support free-form text? Templates only? What's the approval process? What are the rate limits? These constraints flow upstream into your entire messaging design.

---

## Bug #6: The Dynamic Budget Discovery

**Severity:** P2 -- technically working but fundamentally wrong approach

### What Happened

I was reviewing the dashboard after processing a batch of test events. Every single event showed "1/5" in the attempt counter. A Rs 50 browse-only cart abandonment: 1/5. A Rs 30,000 failed invoice: 1/5. A cancelled UPI payment for Rs 200: 1/5.

"Why is everyone showing 1/5?"

Because `max_attempts` was hardcoded to 5 for every event. Every event got the same recovery budget regardless of value, probability, or failure type.

### Why This Was Wrong

Every recovery attempt has a cost: messaging fees (SMS, WhatsApp, email), AI inference costs, payment link generation, and most importantly, customer goodwill. Sending 5 recovery messages for a Rs 50 browse-only cart abandonment is not just wasteful -- it's annoying for the customer and damages the merchant's brand.

Meanwhile, a Rs 30,000 invoice with a 0.8 recovery probability absolutely deserves 5 attempts across multiple channels with escalating urgency. The expected value of recovery justifies the cost of outreach.

### The Fix

Dynamic `max_attempts` computation based on three signals, implemented in `backend/app/services/router.py`:

```python
def compute_max_attempts(
    amount: float,
    recovery_probability: float,
    failure_category: str,
) -> int:
    if failure_category == "unrecoverable_decline":
        return 0
    if failure_category == "browse_only_abandonment":
        return 0
    if failure_category == "user_cancelled":
        return 2
    if recovery_probability <= 0.1:
        return 1
    if recovery_probability >= 0.7 and amount >= 5000:
        return 5
    if recovery_probability >= 0.5 and amount >= 2000:
        return 4
    if recovery_probability >= 0.3 or amount >= 1000:
        return 3
    return 2
```

The budget now ranges from 0 (unrecoverable declines, browse-only carts) to 5 (high-value, high-probability events). This means:

- **0 attempts:** Unrecoverable declines (stolen card, closed account), browse-only cart abandonment (no purchase intent signal). Zero messaging cost.
- **1 attempt:** Very low probability events (<=10%). One try, move on.
- **2 attempts:** User cancellations (they actively chose to cancel -- respect that signal), default low-value events.
- **3-4 attempts:** Medium-value or medium-probability events.
- **5 attempts:** High-value (>=Rs 5,000) with high probability (>=70%). Worth the full effort.

### The Lesson

One-size-fits-all is the enemy of ROI. Every attempt has a cost -- balance it against recovery probability and potential value. A dynamic budget system means the system spends more effort where recovery is likely and valuable, and zero effort where it's not. This isn't just cost optimization; it's also customer experience optimization. Nobody wants 5 messages about a cart they browsed for 10 seconds.

---

## Bug #7: The Security Audit

**Severity:** Mixed P0/P1 -- multiple issues found in a single audit pass

### What Happened

Before final submission, I ran a thorough security and accuracy audit of the entire codebase. The findings were sobering. Commit `32aa745` ("Fix P0/P1 security and accuracy issues from audit") addressed six issues in one pass.

### The Findings and Fixes

**1. Recovery verification was too loose (P0).** The `process_payment_captured()` function in `recovery_tracker.py` wasn't checking whether the payment entity's status was actually `"captured"`. It also wasn't requiring a non-null `payment_id` or doing exact amount matching. A webhook with a missing or wrong payment status could falsely mark an event as recovered.

Fix: Added three reconciliation checks -- reject if entity status isn't `"captured"`, reject if `payment_id` is missing, and reject if the captured amount doesn't match the event amount within a Rs 0.01 (1 paisa) tolerance. Currency matching was also added.

**2. Inflated baseline rate (P1).** The analytics code was using 17.5% as the industry baseline recovery rate. The actual figure from Razorpay's published data is 15-20% for automated retries. I was using the midpoint, which felt dishonest when my system was being compared against it.

Fix: Changed to 15.0% across backend analytics, frontend dashboard, and n8n workflows, with an honest disclaimer that this is from Razorpay's published figures.

**3. Missing idempotency keys (P1).** The `recovery_attempts` table inserts in both `recovery.py` and `escalation.py` had no idempotency keys. If a Celery worker crashed and retried, it could insert duplicate attempt records.

Fix: Added `idempotency_key` field with format `{event_id}:initial:1` for first attempts and `{event_id}:escalation:{attempt_number}` for escalation attempts. Created a unique partial index in migration 005.

**4. CORS was too permissive (P1).** The CORS regex allowed any Vercel preview domain, not just Recovery Router's.

Fix: Tightened the regex to only match `recovery-router` Vercel preview deployments.

**5. Health endpoint leaked internals (P1).** The `/api/health` endpoint was exposing raw error messages, event counts, and Celery queue depth. In production, this would leak operational details to anyone who hit the endpoint.

Fix: Sanitized the response to show component-level status (healthy/degraded/unhealthy) without raw errors or counts.

**6. Missing database columns (P0).** The application code was writing `message_id` and `notes` columns to `recovery_attempts`, but migration 001 never created these columns. Supabase was silently accepting the extra fields (schemaless JSON behavior), but proper columns with types were needed.

Fix: Migration 005 adds the missing columns and enables Row Level Security on both tables with service-role-only policies.

### The Lesson

Security audits find things. Always do one before shipping. And "it works" doesn't mean "it's correct" -- the recovery verification had been accepting webhooks for weeks without checking payment status, and I never noticed because all test payments happened to have the right status.

---

## Debugging Methodology

Looking back at these bugs, a pattern emerges in how I found and fixed them. Since this was a solo project, I couldn't rubber-duck with a teammate. Here's what I did instead.

### The Investigation Protocol

**1. Reproduce the exact state.** Before hypothesizing, I'd query the database and look at the actual data. What are the exact field values? What's the timestamp? What should they be? The gap between "what is" and "what should be" narrows the search.

**2. Enumerate all writers.** For any unexpected database state, list every code path that could write to that table/column. Check each one. This is how I found bugs #1, #2, and eventually #3 -- by exhausting the known writers and realizing there must be an unknown one.

**3. Check the timeline.** Celery task results in Redis have timestamps. Database rows have `updated_at`. Correlating these reveals concurrency issues that don't appear in sequential thinking. Bug #2 was found by noticing two tasks processing the same event within the same second.

**4. Check what's still running.** Processes, scheduled tasks, external integrations, n8n workflows, cron jobs. Bug #3 was the hardest precisely because I forgot to check systems outside the Python codebase.

**5. Fix at the right layer.** Application bugs get application fixes. But invariants that must never be violated -- regardless of which application is writing -- get database-level enforcement. The PostgreSQL trigger in migration 004 is the most important safety mechanism in the entire system.

### The Solo Developer's Advantage

Working alone meant every bug was mine. I couldn't blame a teammate's code or a miscommunication. Every investigation started with "what did I do wrong?" and that honesty accelerated debugging. The Ghost Writer bug was found because I eventually asked "what did I build that I forgot about?" -- a question that's harder to ask in a team where you might assume someone else's system is behaving correctly.

---

## Summary

| Bug | Root Cause | Impact | Fix | Key Code |
|-----|-----------|--------|-----|----------|
| #1 Premature Give-Up | Schema default was "give_up" | Events exhausted after 1 attempt | Three-layer defense: schema + AI override + hard guard | `escalation.py` lines 81, 310-351, 136-155 |
| #2 TOCTOU Race | Concurrent Celery tasks, no locking | Same event processed twice | Redis locks + conditional updates + fresh re-read | `escalation.py` lines 87-94, 111-121 |
| #3 Ghost Writer | Forgotten n8n workflows writing to DB | Impossible exhausted state | Unpublished n8n + PostgreSQL trigger | `004_prevent_premature_exhaustion.sql` |
| #4 Railway Build | Manual Nix config overriding auto-detect | Backend wouldn't deploy | Deleted nixpacks.toml, let auto-detect work | Commit `ce859cf` |
| #5 WhatsApp Templates | Twilio requires pre-approved templates | No AI personalization on WhatsApp | Prioritized Green API over Twilio | `messenger.py` provider hierarchy |
| #6 Fixed Budgets | Hardcoded max_attempts=5 | Wasted effort on low-value events | Dynamic budget from amount + probability + category | `router.py` compute_max_attempts() |
| #7 Security Audit | Multiple issues across codebase | Loose verification, leaked internals | Six fixes in one commit | Commit `32aa745`, migration 005 |

Total bugs that could cause financial impact: 4 (bugs #1, #2, #3, #7).
Total bugs found through systematic investigation vs. accident: 6 out of 7.
Total lines of defense added: 3 (schema), 3 (concurrency), 1 (database trigger), 3 (reconciliation checks) = 10 independent safety mechanisms.

The system is more robust for having broken. Every bug taught a lesson that's now encoded in the code, not just in my head.

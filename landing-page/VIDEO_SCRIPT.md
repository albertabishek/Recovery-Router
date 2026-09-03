# Recovery Router - Demo Video Script

**Total duration:** ~5 minutes 45 seconds
**Style:** Calm, conversational. You're showing a friend what you built - not pitching to investors.
**Resolution:** 1920x1080, quiet room, mic ~6 inches away

---

## SCENE 1 - The Problem (0:00 - 0:25)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 0:00 | "Hey. I'm Albert." | Landing page hero section | Center of screen, still | Relaxed, like greeting a friend | 1.5s |
| 0:02 | "So here's something I noticed about Razorpay." | Landing page hero | Slowly scroll down toward problem stats | Curious, conversational | -- |
| 0:05 | "D2C merchants on Razorpay have around a 68% payment success rate." | Problem section - stat cards | Hover over the 68% stat | Matter-of-fact | 1s |
| 0:09 | "That means roughly 1 in 3 payments... just fails." | Problem section - stat cards | Hover over the "1 in 3" stat | Slow down on "just fails" | 1.5s |
| 0:13 | "And most of those customers? They never come back." | Problem section - "70% abandon" stat | Point to the 70% abandon stat | Slightly lower pitch | 1.5s |
| 0:16 | "There's no system that takes that failed payment... figures out why it failed... and reaches out to the customer to bring them back." | Problem section, slow scroll | Slowly scroll through problem text | Slow, deliberate - one phrase at a time | -- |
| 0:23 | "So I built one." | Landing page - Recovery Router title visible | Stop scrolling, let title sit | Confident, simple | 2s |

---

## SCENE 2 - What It Does (0:25 - 0:50)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 0:25 | "Recovery Router is an autonomous engine. It handles three types of revenue leaks — on its own." | Landing page - architecture/pipeline section | Scroll to the pipeline diagram | Clear, emphasis on "autonomous" and "on its own" | -- |
| 0:28 | "Failed payments. Abandoned carts. Overdue invoices." | Pipeline diagram | Point to each leak type as you say it | Distinct pause between each one | 1s |
| 0:33 | "All three go through the same pipeline. No one else does this — Stripe, Adyen, Chargebee all handle these separately." | Pipeline diagram | Trace the flow arrow with cursor | Emphasis on "same" | 1s |
| 0:35 | "AI classifies the failure... decides which channel to use - WhatsApp, email, or SMS... generates a personalized message... and sends it. No manual intervention." | Pipeline diagram steps | Point to each pipeline step as you describe it: classify, route, generate, send | Slow, steady - one step at a time | 1.5s |
| 0:45 | "Let me show you what that looks like for real." | Pipeline diagram | Move cursor toward browser tab bar | Slightly more energy - transitioning | 2s |

---

## SCENE 3 - Live Payment Demo (0:50 - 2:40)

### 3a - Trigger the payment (0:50 - 1:20)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 0:50 | "I'm going to make a real payment through Razorpay's test gateway." | Dashboard - Overview page | Click "Live Checkout" button in the simulator section | Casual, demonstrating | -- |
| 0:55 | "This creates an actual Razorpay order - test mode, but the full API flow." | Razorpay Checkout modal opens | Let the checkout UI load, cursor idle | Explaining context | -- |
| 1:00 | [silence] | Razorpay Checkout modal | Slowly move cursor across the checkout form so viewer can read it | -- | 2s |
| 1:02 | "I'll enter a test card that's going to get declined." | Razorpay Checkout - card form | Click Card tab, start typing test card number | Narrating your action | -- |
| 1:07 | "This is what happens to real customers. They want to pay... they enter their details... and the bank says no." | Razorpay Checkout - filling form | Continue filling card details, then click Pay | Empathetic, painting a picture | -- |
| 1:15 | "And... payment failed." | Razorpay Checkout - failure screen | Point to the error message | Slight drop in energy | -- |
| 1:18 | [silence] | Failure screen | Keep cursor near error message, let viewer absorb | -- | 2s |

### 3b - Watch the pipeline react (1:20 - 2:00)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 1:20 | "Now watch the dashboard." | Switch to Dashboard - Overview / Live Feed | Close checkout, navigate to Overview tab | Building anticipation | -- |
| 1:22 | "Quick thing you'll notice — I cloned Razorpay's actual UI. Their design tokens, their icons, their color system. I want this to feel like it already belongs in their product suite." | Dashboard - Overview | Let the dashboard sit, cursor idle | Quick aside, matter-of-fact | 1s |
| 1:28 | "Razorpay just fired a webhook to my backend." | Dashboard - Live Feed | Point to the live event feed area | Explaining what's happening | -- |
| 1:31 | [silence] | Dashboard - Live Feed | Wait for the new event to appear, cursor near the feed | -- | 2s |
| 1:33 | "There. The event just landed." | Dashboard - Live Feed | Point directly at the new event row | Small excitement - it worked | -- |
| 1:35 | "Let me click into it so you can see what happened." | Dashboard - Live Feed | Click on the event row | Transitioning | -- |
| 1:38 | [silence] | Dashboard - Event Trace / Detail panel | Let the trace view load | -- | 1.5s |
| 1:40 | "The AI classified this as a card failure — one of 12 categories it knows. Each one gets a different recovery strategy and attempt budget." | Event Trace - Classification section | Point to `failure_category` field, then `recovery_probability` | Narrating the data | 1.5s |
| 1:48 | "And the AI behind this? It's a 3-model fallback chain. Claude Haiku first, then Gemini Flash, then GPT-4o-mini. If one goes down, the next one picks up. And if all three are down, there's a rules-based fallback that still classifies using error codes." | Event Trace - Classification section | Cursor idle near the classification fields | Technically proud, steady | 1.5s |
| 2:00 | "It picked WhatsApp as the channel. Generated a personalized message. And sent it." | Event Trace - Attempt timeline | Scroll down through the attempt history, point to channel, message, status | Steady pace, one fact at a time | -- |
| 2:06 | [silence] | Event Trace - Full timeline visible | Let cursor rest, viewer reads the timeline | -- | 2s |
| 2:08 | "You can see the actual message it sent right here." | Event Trace - Message content | Point directly at the message text in the attempt row | Drawing attention | -- |
| 2:11 | "And this is the payment link it generated - a real Razorpay checkout page." | Event Trace - Payment link field | Point to the payment link URL | -- | -- |
| 2:15 | "All of this happened automatically. In seconds." | Event Trace - Overview | Cursor idle, center of the trace | Emphasis on "automatically" | 2s |

### 3c - Show the WhatsApp message (2:18 - 2:38)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 2:18 | "And here's the actual WhatsApp message that arrived." | Switch to phone screenshot / WhatsApp image | Show WhatsApp screenshot (overlay or new tab) | Reveal moment | -- |
| 2:21 | [silence] | WhatsApp message screenshot | Cursor traces the message text slowly | -- | 3s |
| 2:24 | "It's not a template. The AI wrote this based on the failure type, the amount, and which attempt this is." | WhatsApp message screenshot | Point to the personalized parts: customer name, amount, tone | Proud but measured | -- |
| 2:30 | "If I click this link... it opens a Razorpay checkout page, pre-filled with my details." | Checkout page from the recovery link | Show the checkout page loaded from the link | Demonstrating the full loop | -- |
| 2:34 | "That's the full loop. Payment fails, customer gets a message, one tap to pay again." | Checkout page | Cursor idle at center | Wrapping up the demo beat | 2s |

### 3d - Show recovery tracking (2:38 - 2:58)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 2:38 | "Now - if the customer actually pays through that link..." | Dashboard - Event list | Navigate back to Events tab | Setting up the next beat | -- |
| 2:41 | "Razorpay fires a payment.captured webhook back to me." | Dashboard - Event list | Point to a recovered event row (green status badge) | Explaining the mechanism | -- |
| 2:44 | "And the event status changes from 'pending' to 'recovered'." | Dashboard - Recovered event | Point to the green "recovered" status badge | Clear, factual | -- |
| 2:48 | "But here's the thing I'm careful about." | Dashboard - Event list | Cursor idle | Tone shift - serious, thoughtful | 1s |
| 2:50 | "If the customer paid on their own - before my message even reached them - I mark it as 'organic recovery', not 'recovered'." | Dashboard - Organic recovery event | Point to an organic_recovery event (different color badge) | Deliberate, emphasizing honesty | -- |
| 2:56 | "I don't want to take credit for something the AI didn't cause." | Dashboard - Organic recovery event | Cursor idle near the badge | Quiet conviction | 2s |

---

## SCENE 4 - Simulated Scenarios (3:00 - 3:55)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 3:00 | "The live demo shows a card decline. But the system handles ten different scenarios across all three leak types." | Dashboard - Simulator page | Navigate to Simulator tab | Transitioning, widening scope | -- |
| 3:06 | "Let me fire a cart abandonment." | Simulator - Scenario list | Click "High Intent Cart" scenario button | Casual, demonstrating | -- |
| 3:09 | [silence] | Simulator - Event processing | Wait for event to appear in feed | -- | 2s |
| 3:11 | "See - different classification. 'High intent abandonment'. Recovery probability is still decent." | Event Trace for cart event | Point to `failure_category` and `recovery_probability` | Comparing to previous | -- |
| 3:16 | "But now look at the budget. It gave this 3 attempts instead of 5." | Event Trace - max_attempts field | Point directly at `max_attempts: 3` | Drawing attention to the difference | -- |
| 3:20 | "Because a cart is worth less than a failed payment." | Event Trace - max_attempts | Cursor idle | Explaining the logic | 1.5s |
| 3:22 | "And if I fire a browse-only cart..." | Simulator - Scenario list | Click "Browse Only Cart" scenario | Quick transition | -- |
| 3:25 | [silence] | Simulator - Event processing | Wait for event | -- | 2s |
| 3:27 | "Zero attempts. Budget is zero. The AI decided this person was just browsing - don't bother them." | Event Trace for browse-only | Point to `max_attempts: 0` and `status: no_action_needed` | Slight smile in voice | -- |
| 3:33 | "Now let me show the third leak type - overdue invoices." | Simulator - Scenario list | Click an overdue invoice scenario | Transitioning | -- |
| 3:36 | [silence] | Simulator - Event processing | Wait for event to appear | -- | 2s |
| 3:38 | "In production, these get picked up automatically - there's a scanner that polls Razorpay's API every 6 hours for overdue invoices and feeds them into the same pipeline." | Event Trace for invoice event | Point to `failure_category` showing invoice classification | Explaining the mechanism | 1s |
| 3:47 | "That's the dynamic budget system. Three leak types, one pipeline, and the AI decides how much effort each one deserves." | Event Trace | Cursor idle | Summarizing the concept | 2s |

---

## SCENE 5 - Safety and Escalation (3:50 - 4:38)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 3:50 | "One thing I spent a lot of time on is making sure this system doesn't do dumb things." | Dashboard - Event with multiple attempts | Navigate to an event that has 3+ attempts | Honest, conversational | -- |
| 3:55 | [silence] | Event Trace - multiple attempts visible | Let the attempt list load | -- | 1s |
| 3:56 | "Like... sending the same message twice. Or spamming someone at 2 AM." | Event Trace | Cursor idle | Light, relatable | -- |
| 4:00 | "There's a quiet hours block - no messages between 9 PM and 9 AM." | Event Trace - a rescheduled attempt | Point to a `next_action_at` that shows rescheduled time | Factual | -- |
| 4:05 | "There's Redis dedup - so the same webhook can't trigger two events." | Event Trace | Cursor idle (no specific UI element for this) | Quick, technical | -- |
| 4:08 | "And there's distributed locks - so two Celery workers can't process the same event at the same time." | Event Trace | Cursor idle | Quick, technical | -- |
| 4:12 | "Even the messaging has fallbacks. WhatsApp goes through Green API first - if that fails, it falls back to Twilio, then to email. The system doesn't just try once and give up." | Event Trace | Cursor idle | Explaining resilience | 1s |
| 4:20 | [silence] | Event Trace - attempt history | -- | -- | 1.5s |
| 4:22 | "The escalation engine runs every 5 minutes." | Event Trace - attempt history | Point to the timestamps on attempts (spaced ~5 min apart) | Shifting to escalation | -- |
| 4:26 | "It picks up pending events, rotates channels - WhatsApp first, then email, then SMS." | Event Trace - attempt list | Point to attempt 1 (whatsapp), attempt 2 (email), attempt 3 (sms) | Walking through the sequence | -- |
| 4:31 | "And the tone progresses. First message is friendly. Second is firmer. Third is urgent." | Event Trace - attempt messages | Point to the tone/message text in each attempt | Demonstrating progression | -- |
| 4:36 | [silence] | Event Trace | Cursor idle | -- | 2s |

---

## SCENE 6 - Best Bug Story (4:38 - 5:10)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 4:38 | "Quick story about the weirdest bug I found." | Landing page - War Stories section OR stay on dashboard | Scroll to War Stories on landing page, or just keep dashboard open | Lighter, storytelling mode | -- |
| 4:41 | "Event number 18 was marked 'exhausted' after just one attempt. But the budget was 5." | War Stories section (if on landing page) | Point to the Ghost Writer story card | Setting up the mystery | -- |
| 4:46 | [silence] | -- | -- | -- | 1s |
| 4:47 | "I checked every code path. Every Celery task. Git blame. Everything was correct." | -- | Cursor idle | Building tension | -- |
| 4:52 | "Turns out... my old n8n workflow was still running." | -- | -- | The reveal - slight pause before "n8n" | 1s |
| 4:55 | "It was writing directly to Supabase with its own credentials. Completely bypassing my backend." | -- | -- | Explaining the root cause | -- |
| 5:00 | "Two systems racing against each other with no idea the other one existed." | -- | -- | Landing the punchline | -- |
| 5:04 | "So I added a PostgreSQL trigger - a database-level guard that blocks any writer from marking an event exhausted when attempts are still remaining." | -- | -- | Technical but clear | -- |
| 5:10 | [silence] | -- | -- | -- | 2s |

---

## SCENE 7 - Honest Gaps and Close (5:12 - 5:45)

| Time | Say | Screen / Page | Cursor / Point To | Tone | Pause After |
|------|-----|---------------|-------------------|------|-------------|
| 5:12 | "I want to be upfront about what this isn't." | Landing page - Honest Gaps section | Scroll to Honest Gaps section | Honest, grounded | -- |
| 5:16 | "This runs on Razorpay test-mode keys. No real merchant data." | Honest Gaps - first bullet | Point to test-mode gap | Factual, not defensive | -- |
| 5:20 | "I track whether the message was sent, not whether the customer read it." | Honest Gaps - delivery tracking gap | Point to delivery gap | -- | -- |
| 5:24 | "And the dashboard uses a single shared password - not production-grade auth." | Honest Gaps - auth gap | Point to auth gap | -- | -- |
| 5:28 | [silence] | Honest Gaps section | Cursor idle | -- | 1.5s |
| 5:30 | "But the pipeline is real. The AI classification is real. The Razorpay integration is real." | Switch to Dashboard - Overview | Navigate back to dashboard overview | Rising energy, confident | -- |
| 5:35 | "114 tests. Zero mocks. Everything runs against live services." | Dashboard - Overview | Cursor idle on the overview metrics | Emphasis on "zero mocks" | -- |
| 5:39 | [silence] | Dashboard - Overview | -- | -- | 1.5s |
| 5:41 | "That's Recovery Router." | Dashboard - Overview | Cursor idle, center screen | Calm, final | Hold 1s, end |

---

## Recording Checklist

Before you record, have these ready:

- [ ] Dashboard loaded and logged in at razorpay.albertabishek.com
- [ ] Landing page open in another browser tab
- [ ] Simulator page ready with all 10 scenarios loaded
- [ ] At least one event with 3+ attempts (for escalation demo in Scene 5)
- [ ] At least one "recovered" event with green badge
- [ ] At least one "organic_recovery" event with different badge
- [ ] WhatsApp screenshot of an actual received message saved as image
- [ ] Razorpay test card number ready to paste (don't type live)
- [ ] Screen recording tool set to 1920x1080
- [ ] Microphone tested - speak from ~6 inches, quiet room
- [ ] Close all notifications, unrelated browser tabs, desktop clutter

## Speaking Tips

- **Talk TO someone, not AT a camera.** Imagine a friend sitting next to you.
- **Pause after every important point.** The pause is where the viewer understands.
- **Don't read the UI out loud.** They can see it. Tell them what it means.
- **If you stumble, just pause and continue.** Don't restart the whole section.
- **Vary your pace.** Slow for important parts, slightly faster for transitions.
- **End sentences down, not up.** Statements, not questions.
- **Follow the cursor column.** Your cursor is the viewer's eye - guide them.

## Tab Order (keep these open left to right)

1. Landing page (for Scene 1, 2, 6, 7)
2. Dashboard - Overview (for Scene 3b, 3d, 7)
3. Dashboard - Events (for Scene 3d)
4. Dashboard - Simulator (for Scene 4)
5. WhatsApp screenshot image (for Scene 3c)

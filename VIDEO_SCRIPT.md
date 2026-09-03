# Recovery Router, 5-minute demo video script

Razorpay AI Buildathon 2026, Track 3: AI Revenue Recovery
Built by Albert Abishek I

Target: 630-660 spoken words | 140 wpm | 5:00 total with clicks and pauses

---

## Claim verification log

Every number in this script has been checked against published sources:

| Claim | Figure | Source | URL |
|-------|--------|--------|-----|
| D2C payment success rate | 68-74% average success for Indian D2C brands | Razorpay "Payment Success Rate Optimization India (2026 Guide)", May 5, 2026 | razorpay.com/blog/payment-success-rate-optimization-india/ |
| Customer loss after card decline | 40% won't return after their card is declined | Same article, May 2026 | razorpay.com/blog/payment-success-rate-optimization-india/ |
| Cart abandonment cause | 70% of cart abandonment in India happens due to payment failures | Same article, May 2026 | razorpay.com/blog/payment-success-rate-optimization-india/ |
| Retry recovery rate | 15-20% of failed transactions recovered by automated retries | Same article, May 2026 | razorpay.com/blog/payment-success-rate-optimization-india/ |
| Vulcan improvement | 8-10% improvement in success rates | Razorpay Vulcan product page | razorpay.com/foundation-model |
| Vulcan training data | 4 billion payments, 3 trillion data points, ~3,000 signals per transaction | Same page | razorpay.com/foundation-model |
| Stripe combined Billing recovery | 55% of failed payments recovered on average using combined Billing tools (Smart Retries + card updates + recovery automations) | Stripe Billing page | stripe.com/billing |

Removed claims:
- "$10 billion lost to cart abandonment" (no published source found)
- "52% never come back" (exists in a 2023 Razorpay article but using the more recent 40% figure from May 2026)
- "26-32% failure rate" (mathematically inferred from 68-74% success; the article publishes the success rate, not the failure rate)
- Stripe "+0.11% revenue uplift" (no direct case-study URL with exact context)

---

## 0:00-0:15, the problem (15 seconds)

[Screen: Landing page hero]

"Razorpay's 2026 guide puts D2C payment success rates at 68 to 74 percent. One in four payments fails. 40 percent of those customers won't try again. Razorpay built Vulcan to prevent failures, but once a payment still fails, the recovery tools don't talk to each other."

---

## 0:15-0:30, the thesis (15 seconds)

[Screen: Pipeline steps on landing page]

"Recovery Router puts all three revenue leaks, failed payments, abandoned carts, unpaid invoices, through one pipeline. Figure out why it failed, pick the best recovery action, send it, and track whether it worked."

---

## 0:30-2:30, live payment demo (120 seconds)

[Screen: Dashboard at razorpay.albertabishek.com]

"I'll start with a real Razorpay payment.

[Open Simulator, scroll to 'Try Live Payment']
This is a real Razorpay checkout. I'll enter 499 rupees and use a test card that Razorpay provides for testing failures.

[Click 'Try Live Payment', Razorpay checkout opens, enter test failure card]

The payment just failed through Razorpay's actual gateway. Razorpay sends a webhook to our system.

[Switch to Recovery Events, new event appears]
There it is. The AI looked at the error and came back with a failure category, recovery probability, recommended channel, and timing. A checkout link was created and a recovery message was queued. That's the full loop: real payment fails, webhook arrives, AI classifies, recovery sent.

[Show event detail panel, point to AI classification fields]
The AI model names are on screen. If one model goes down, it tries the next. If all three are down, built-in rules take over. The system never gets stuck waiting for AI.

[Point to attempt budget]
Each event gets a budget for how many times to try. A 50,000 rupee failed payment gets more tries than a small abandoned cart."

---

## 2:30-3:10, simulated cart abandonment (40 seconds)

[Scroll to Simulator scenarios, select cart abandonment]

"Now a different leak type. This customer added 12,000 rupees to their cart and left.

[Click Simulate, switch to Recovery Events]
Same pipeline, different result. The AI gives this lower recovery odds because the customer never tried to pay. Smaller budget, gentler message tone.

[Compare the two events side by side]
Compare them. The live failed payment got more attempts because that customer was actively trying to pay. The cart abandonment gets fewer. The system adjusts on its own."

---

## 3:10-3:40, honest tracking (30 seconds)

[Show a reconciled event]

"When a customer pays, Razorpay confirms it. The system matches it back to the original event. Did we send this person a message? If yes, it counts as recovered. If we never reached them and they came back on their own, it's marked organic. We track whether the message provider accepted the send, not whether the customer opened it, because delivery receipts aren't built yet. That's how the numbers stay honest."

---

## 3:40-4:05, safety proofs (25 seconds)

[Show Audit Logs, point to idempotency_key column on an attempt]

"Every message send is reserved in the database before it goes out. If a worker crashes mid-send, the retry sees the reservation and skips instead of double-sending. Each attempt gets a unique idempotency key.

[Show an event with multiple attempts]
The system rechecks every five minutes whether to try a different channel. Three safety layers stop it from giving up too early. 18 defense layers total, from webhook signature verification down to a database trigger."

---

## 4:05-4:20, the ghost writer bug (15 seconds)

[Screen: War Stories section]

"My favorite bug. Event 18 was marked as done with no reason recorded. Impossible. Turns out my old prototype was still running, writing to the database behind the backend's back. The fix: a database rule that blocks bad writes no matter where they come from."

---

## 4:20-4:40, the infinite retry loop (20 seconds)

[Screen: War Stories section, Bug #6 card]

"The scariest bug. Event 36 had fake contact info. Every send attempt was rejected by the provider. But attempt_count only moves on success. So the safety guard always passed, and the system retried forever. A deadlock: the counter that stops retries only moves when you succeed, but you can never succeed. The fix: a separate delivery_failure_count that tracks provider rejections. After enough failures, the system gives up, even if it never succeeded."

---

## 4:40-5:00, limitations and close (20 seconds)

[Screen: Impact section]

"This runs on Razorpay test-mode data. I track sent, not delivered, because I don't have delivery receipts yet. The dashboard uses a single shared password, not per-user auth.

What is real: one system for three types of revenue loss, AI that always has a backup, smart budgets that know when to stop, honest tracking that separates our recoveries from customers who came back on their own, 18 defense layers down to the database level, and 368 tests across offline and live suites. Thank you."

---

## Recording notes

- Pre-test both the live payment and the simulated scenario before recording. Use the exact same test card and scenario during the real take.
- For the live payment, use Razorpay's test failure card. The Razorpay checkout popup will appear and the payment will fail, triggering the webhook and recovery pipeline.
- Keep the dashboard loaded before recording. Do not wait for API calls on camera.
- Speak at about 140 words per minute. About 650 spoken words, leaving 20-30 seconds for clicks and loading.
- Record screen and audio separately, then sync them.
- If judges question a number, every statistic has a source URL in the verification log above.

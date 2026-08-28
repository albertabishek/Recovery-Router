# Security Model — Recovery Router

**Razorpay AI Buildathon Track 3** | Last updated: 2026-08-27

This document describes the security measures implemented in Recovery Router. All findings from the [codebase audit](AUDIT.md) (31 findings, 8 critical) have been fixed.

---

## 1. Webhook Signature Verification

**File:** `backend/app/routers/webhooks.py:17–22`

Both `/webhook/recovery-router` and `/webhook/recovery-tracker` verify the `X-Razorpay-Signature` header using HMAC-SHA256 with a timing-safe comparison (`hmac.compare_digest`). The webhook secret is stored in `.env` as `RAZORPAY_WEBHOOK_SECRET`.

If the secret is not configured (empty string), signature verification is bypassed to allow development without Razorpay — this should be set in production.

## 2. XSS Prevention

**File:** `backend/app/routers/checkout.py:8, 18`

- **Order ID validation:** Regex `^order_[A-Za-z0-9]{8,30}$` rejects any order_id that doesn't match Razorpay's format. This prevents JS injection via crafted URLs like `/pay/';alert(1);//`.
- **HTML escaping:** All user-supplied query params (`name`, `email`, `phone`) passed into the checkout page HTML are escaped.
- **Email templates:** `backend/app/services/message_generator.py:140–141` uses `html.escape()` on all interpolated values. Payment link URLs are validated to start with `http://` or `https://` before being placed in `href` attributes.

## 3. AI Input Sanitization

**File:** `backend/app/services/classifier.py:114–118`

All user-supplied fields sent to the AI are sanitized before the API call:
- Truncated to max length (200 chars for descriptions, 100 for names/codes, 50 for methods)
- Control characters (`\x00-\x08`, `\x0b`, `\x0c`, `\x0e-\x1f`, `\x7f`) stripped via regex

This prevents prompt injection attacks where a malicious `error_description` could manipulate the classification output.

## 4. Deduplication

**File:** `backend/app/utils/dedup.py`

Redis-based deduplication with 1-hour TTL prevents duplicate event processing:
- Uses `payment_id`, `order_id`, or `invoice_id` as the dedup key
- If none exist, a SHA256 hash of the full payload is used as fallback
- Empty identifiers bypass dedup (by design — such events are rare and non-critical)

## 5. Rate Limiting

**File:** `backend/app/utils/rate_limiter.py`

Sliding window rate limiter using Redis sorted sets:
- `/webhook/recovery-router`: 100 requests/minute
- `/webhook/recovery-tracker`: 100 requests/minute
- `/api/simulate`: 10 requests/minute

### Per-Resource Cooldowns

Prevents message spam to individual customers:
- **WhatsApp:** 5 minutes per phone number
- **SMS:** 5 minutes per phone number
- **Email:** 5 minutes per email address

Cooldowns use Redis `SET NX EX` for atomic check-and-set.

## 6. Race Condition Prevention

**File:** `backend/app/services/recovery_tracker.py:61, 75`

All status updates use optimistic concurrency by adding `.eq("status", "pending")` to the UPDATE query. If two concurrent processes try to update the same event, only one succeeds (the other gets 0 rows affected and logs a warning). This prevents:
- Double-counting of recovered revenue
- Duplicate recovery messages
- Escalation processing events that are already being handled

## 7. CORS Configuration

**File:** `backend/app/main.py:18–31`

CORS is restricted to:
- **Origins:** `settings.FRONTEND_URL`, `localhost:5173`, `localhost:3000`, `albertabishek.com`, `app.albertabishek.com`, `api.albertabishek.com`
- **Methods:** `GET`, `POST`, `OPTIONS` only
- **Headers:** `Content-Type`, `Authorization` only
- **Credentials:** Enabled (for cookie-based auth if added)

## 8. SSL/TLS

**File:** `backend/app/celery_app.py:12–13`

All Redis/Upstash connections use `ssl.CERT_REQUIRED` for TLS certificate verification on both the Celery broker and backend connections. This prevents MITM attacks on the message broker.

## 9. Credential Management

- All secrets stored in `.env` files, never hardcoded in source
- `.gitignore` excludes: `.env`, `.env.*` (except `.env.example`), `Credentials_for_you/`, `*.pem`, `*.key`
- `.env.example` files provide templates with placeholder values
- Frontend uses `VITE_` prefixed env vars (Vite strips non-prefixed vars from the bundle)
- Supabase anon key is intentionally exposed in frontend (by design) — RLS policies should restrict it to SELECT on `recovery_events` only

## 10. Ghost Recovery Prevention

**File:** `backend/app/services/recovery_tracker.py:55–68`

When a payment is captured, the tracker checks `attempt_count`:
- `attempt_count == 0`: Logged as `organic_recovery` (customer paid on their own, no recovery messages sent)
- `attempt_count > 0`: Logged as `recovered` (AI-driven recovery)

This prevents inflating AI Lift metrics by counting recoveries that would have happened anyway.

## 11. Error Handling

- Webhook endpoints return generic error messages (`"Invalid payload format"`) — full errors logged server-side only
- Celery tasks use exponential backoff retry: `60 * (2^retries)` seconds (60s, 120s, 240s)
- `acks_late=True` and `task_reject_on_worker_lost=True` ensure tasks survive worker crashes
- All provider send functions catch exceptions and return structured error results (never crash the pipeline)

## 12. Provider Fallback Resilience

**File:** `backend/app/services/messenger.py`

Every channel has a complete fallback chain so messages are delivered even when individual providers fail:

```
WhatsApp: Green API → Twilio WhatsApp → Email (Resend)
SMS:      Twilio SMS → Green API WhatsApp → Twilio WhatsApp → Email (Resend)
Email:    Resend
```

Every provider attempt (success or failure) is recorded in the `degradation_path` array for full observability.

---

## Known Limitations

1. **No API authentication:** Endpoints are protected by rate limiting and webhook signatures, but there is no JWT/API key auth on `/api/events`, `/api/analytics`, or `/api/simulate`. For the buildathon demo this is acceptable; production would need auth middleware.

2. **Supabase anon key in frontend:** The anon key is bundled into the frontend JS. RLS policies must be properly configured to restrict the anon role to SELECT-only on `recovery_events`.

3. **Webhook secret bypass:** If `RAZORPAY_WEBHOOK_SECRET` is empty, signature verification is bypassed. This must be set in production.

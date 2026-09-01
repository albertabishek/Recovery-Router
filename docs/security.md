# Security Architecture — Recovery Router

> Recovery Router is an AI-powered payment recovery system handling real money flows through Razorpay. This document describes every security layer in the system, with exact file paths, line numbers, and code snippets.
>
> Author: Albert Abishek I  
> Last updated: 2026-08-31

---

## Table of Contents

1. [Webhook Signature Verification](#1-webhook-signature-verification)
2. [Request Body Size Limits](#2-request-body-size-limits)
3. [Rate Limiting](#3-rate-limiting)
4. [Event Deduplication](#4-event-deduplication)
5. [Race Condition Prevention](#5-race-condition-prevention)
6. [AI Safety](#6-ai-safety)
7. [Checkout Security](#7-checkout-security)
8. [PII Protection](#8-pii-protection)
9. [Database-Level Safety](#9-database-level-safety)
10. [CORS Configuration](#10-cors-configuration)
11. [Authentication](#11-authentication)
12. [Known Limitations and Open Items](#12-known-limitations-and-open-items)

---

## 1. Webhook Signature Verification

**File:** `backend/app/routers/webhooks.py`, lines 20-26

**What it does:** Every inbound Razorpay webhook is authenticated using HMAC-SHA256. The raw request body is hashed with a shared secret, and the result is compared against the `X-Razorpay-Signature` header that Razorpay sends.

**Implementation:**

```python
def _verify_razorpay_signature(raw_body: bytes, signature: str) -> bool:
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        logger.warning("RAZORPAY_WEBHOOK_SECRET not configured — rejecting webhook")
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**Security properties:**

- **Timing-safe comparison:** `hmac.compare_digest()` (line 26) prevents timing side-channel attacks. A naive `==` comparison leaks information about how many bytes matched by returning faster on the first mismatch. `compare_digest` always compares the full string in constant time.
- **Fail-closed:** If `RAZORPAY_WEBHOOK_SECRET` is not configured, the function returns `False` and rejects all webhooks (line 23-24), rather than silently accepting unverified traffic.
- **Raw body integrity:** The signature is computed over the raw bytes (line 35), not the parsed JSON. This is critical because JSON parsing can reorder keys or normalize whitespace, which would invalidate the signature.

**What happens on failure:** HTTP 401 with `"Invalid webhook signature"` (line 40). The request is rejected before any processing occurs.

Both webhook endpoints (`/webhook/recovery-router` and `/webhook/recovery-tracker`) enforce this check identically (lines 38-40 and lines 97-99).

---

## 2. Request Body Size Limits

**File:** `backend/app/routers/webhooks.py`, lines 17, 36-37

**Implementation:**

```python
MAX_WEBHOOK_BODY_SIZE = 1024 * 256  # 256 KB

raw_body = await request.body()
if len(raw_body) > MAX_WEBHOOK_BODY_SIZE:
    raise HTTPException(status_code=413, detail="Request body too large")
```

**Attack prevented:** Denial-of-service via oversized payloads. Without this limit, an attacker could send multi-gigabyte bodies to exhaust memory or stall HMAC computation.

**Why 256 KB:** Razorpay webhook payloads are typically 1-5 KB. A 256 KB ceiling leaves generous headroom for legitimate payloads while blocking abuse. The check runs before signature verification (line 36 precedes line 38), so oversized payloads are rejected without spending CPU on HMAC.

Both webhook endpoints enforce this limit (lines 36-37 and lines 95-96).

---

## 3. Rate Limiting

**File:** `backend/app/utils/rate_limiter.py`, lines 5-21

**Implementation:** A sliding window rate limiter built on Redis sorted sets.

```python
def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    r = get_redis()
    now = time.time()
    window_key = f"ratelimit:{key}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(window_key, 0, now - window_seconds)
    pipe.zadd(window_key, {str(now): now})
    pipe.zcard(window_key)
    pipe.expire(window_key, window_seconds)
    results = pipe.execute()

    current_count = results[2]
    if current_count > max_requests:
        r.zrem(window_key, str(now))
        return False
    return True
```

**How it works:**

1. Old entries outside the window are pruned (`ZREMRANGEBYSCORE`).
2. The current request timestamp is added to the sorted set.
3. The total count is checked against the limit.
4. If over-limit, the just-added entry is removed (line 20) so it does not pollute the window.
5. A `TTL` is set on the key so it auto-expires if traffic stops.

All operations use a Redis pipeline (single round-trip), making this atomic and fast.

**Per-endpoint limits:**

| Endpoint | Key | Limit | Window |
|---|---|---|---|
| `POST /webhook/recovery-router` | `webhook:recovery-router` | 100 requests | 60 seconds |
| `POST /webhook/recovery-tracker` | `webhook:recovery-tracker` | 100 requests | 60 seconds |
| `GET /api/analytics` | `api:analytics` | 30 requests | 60 seconds |

**Sources:** `webhooks.py` line 32, line 91; `analytics.py` line 16.

**Per-resource cooldowns** (lines 25-31): A separate mechanism prevents messaging the same customer too often. Uses Redis `SET NX` with a configurable TTL per resource type and ID.

**What happens on limit exceeded:** HTTP 429 `"Rate limit exceeded"`.

---

## 4. Event Deduplication

Recovery Router uses two-level deduplication to ensure each payment event is processed exactly once, even under network retries and worker crashes.

### Level 1: Redis Fast-Path (Hot Cache)

**File:** `backend/app/utils/dedup.py`, lines 8-14

```python
DEDUP_TTL_SECONDS = 3600  # 1 hour

def is_duplicate(event_type: str, identifier: str) -> bool:
    r = get_redis()
    key = f"dedup:{event_type}:{identifier}"
    if r.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS):
        return False   # First time seeing this — not a duplicate
    return True        # Key already exists — duplicate
```

**How it works:** `SET NX` (set-if-not-exists) is an atomic Redis operation. The first request for a given identifier wins; all subsequent requests within the 1-hour TTL are rejected as duplicates. This runs in the webhook handler before any database work.

**Identifier extraction** (`get_dedup_identifier`, lines 17-28): For Razorpay `payment.failed` events, the payment entity ID is used. For other events, the function tries `payment_id`, `order_id`, or `invoice_id` in order, falling back to a SHA-256 hash of the entire payload (lines 31-33).

### Level 2: PostgreSQL Durable Indexes

**File:** `backend/migrations/003_durable_idempotency.sql`

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_events_payment_id_unique
  ON recovery_events (payment_id)
  WHERE payment_id IS NOT NULL AND payment_id NOT LIKE 'pay_TEST_%';

CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_events_order_id_unique
  ON recovery_events (order_id)
  WHERE order_id IS NOT NULL AND order_id NOT LIKE 'order_TEST_%';

CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_events_invoice_id_unique
  ON recovery_events (invoice_id)
  WHERE invoice_id IS NOT NULL;
```

These are partial unique indexes. They guarantee that even if Redis is unavailable (failover, eviction), the database will reject duplicate inserts at the constraint level.

**Application-level DB dedup** (`backend/app/tasks/recovery.py`, lines 55-81): Before inserting, the Celery task queries the database to check for existing records with the same `payment_id`, `order_id`, or `invoice_id`. This provides a friendly "duplicate" response rather than letting the unique index throw an error.

Test events (prefixed `pay_TEST_` or `order_TEST_`) are excluded from uniqueness constraints so the simulator can generate repeated test data without constraint violations.

**Action-level idempotency** (`backend/migrations/005_missing_columns_and_rls.sql`, lines 10-12): Recovery attempts have an `idempotency_key` with a unique index, preventing duplicate message sends if a Celery worker crashes and retries.

### Why two levels?

| Layer | Speed | Durability | Failure mode |
|---|---|---|---|
| Redis `SET NX` | Sub-millisecond | Volatile (eviction, restart) | Lets duplicates through |
| PostgreSQL unique index | Milliseconds | Durable (WAL, replication) | Constraint error |

Redis handles the common case (repeated webhook deliveries within minutes) cheaply. PostgreSQL catches anything Redis missed, including events replayed after Redis restarts or across worker restarts.

---

## 5. Race Condition Prevention

Processing real money requires protection against concurrent operations on the same event. Recovery Router uses three mechanisms.

### 5a. Redis Distributed Locks

**File:** `backend/app/tasks/recovery.py`, lines 412-413 (delayed send), lines 324-325 (retry failure)

```python
lock_key = f"lock:event:{event_id}"
if not r.set(lock_key, "delayed", nx=True, ex=300):
    logger.info("Delayed send: event %d locked by another process, skipping", event_id)
    return {"status": "skipped_locked", "event_id": event_id}
```

Each event gets a per-event lock with a 300-second TTL (`ex=300`). If another process already holds the lock, the current task skips rather than competing. Locks are released in `finally` blocks (e.g., line 557: `r.delete(lock_key)`) to avoid stale locks.

**File:** `backend/app/tasks/escalation.py`, lines 13-14, 19

```python
LOCK_KEY = "lock:escalation"
LOCK_TTL = 240  # 4 minutes
```

The escalation cycle itself uses a global lock so only one escalation sweep runs at a time, even with multiple Celery workers.

### 5b. Optimistic Concurrency (Conditional Updates)

**File:** `backend/app/tasks/recovery.py`, line 282

```python
sb.table("recovery_events").update(update_data).eq("id", event_id).eq("status", "pending").execute()
```

Every status-changing database update includes `.eq("status", "pending")` as a condition. If another process already changed the status (e.g., the payment was recovered between classification and send), the update silently becomes a no-op rather than overwriting the newer state. This pattern appears throughout `recovery.py` and `escalation.py`.

### 5c. Three-Layer Give-Up Prevention

A critical safety invariant: the system must never mark an event as "exhausted" before actually trying to reach the customer. Three layers enforce this:

1. **Schema default:** `backend/migrations/001_initial_schema.sql`, line 47: `max_attempts INTEGER DEFAULT 5`. Every new event starts with budget for 5 recovery attempts.

2. **AI/application override:** `backend/app/services/router.py`, `compute_max_attempts()` (lines 13-35). The AI classification dynamically adjusts `max_attempts` based on amount, probability, and failure type. Unrecoverable declines get 0; high-value high-probability events get up to 5.

3. **Database trigger (hard guard):** `backend/migrations/004_prevent_premature_exhaustion.sql`. A PostgreSQL `BEFORE UPDATE` trigger that blocks any attempt to set `status = 'exhausted'` when `attempt_count < max_attempts` and no `skip_reason` is provided. See section 9 for full details.

---

## 6. AI Safety

**File:** `backend/app/services/classifier.py`

### Input Sanitization

**Lines 122-126:**

```python
def _sanitize(value: str | None, max_len: int = 200) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value))
    return cleaned[:max_len]
```

Every user-supplied field is sanitized before being sent to the AI:

- **Control character stripping:** The regex removes ASCII control characters (NULL through BACKSPACE, vertical tab, form feed, shift-in through unit separator, and DEL). These could be used for prompt injection or to confuse model tokenizers.
- **Length truncation:** Fields are capped at their specific limits (method: 50 chars, error_code: 100 chars, error_description/customer_name: 200 chars). This prevents prompt stuffing.
- **Applied at:** Lines 147-150. Each field in the AI input payload goes through `_sanitize()` with appropriate length limits.

### Prompt Injection Prevention

The system prompt (lines 16-70) defines a rigid output schema. The AI is instructed to return a single JSON object with specific fields and enumerated values.

### Output Validation

**File:** `backend/app/services/ai_client.py`, lines 168-191

```python
def _validate_fields(parsed: dict, schema: dict):
    for field, rules in schema.items():
        value = parsed.get(field)
        allowed = rules.get("allowed")
        if allowed and value not in allowed:
            parsed[field] = rules.get("default", allowed[0])
```

The response schema (`classifier.py`, lines 72-101) defines strict validation rules:

| Field | Constraint |
|---|---|
| `leak_type` | Must be one of 3 values: `payment_failure`, `cart_abandonment`, `invoice_overdue` |
| `failure_category` | Must be one of 12 enumerated categories |
| `recovery_probability` | Float clamped to 0.0-1.0 |
| `recommended_channel` | Must be one of: `whatsapp`, `email`, `sms`, `none` |
| `recommended_timing` | Must be one of 5 timing values |

If the AI returns a value outside the allowed set, it is silently replaced with the default. If a float is out of range, it is clamped. This means a compromised or hallucinating model cannot inject arbitrary categories, channels, or probabilities into the pipeline.

### Model Fallback

**File:** `backend/app/services/ai_client.py`, lines 18-37

The system uses a three-model fallback chain (Claude Haiku 4.5 -> Gemini 3.7 Flash -> GPT-4o-mini). If all three fail, the classifier falls back to deterministic rule-based classification (`classifier.py`, lines 244-293). This ensures the system never silently drops events when AI services are unavailable.

### Pydantic Enforcement

**File:** `backend/app/models.py`, lines 28-41

The `ClassificationResult` model uses `Literal` types for critical fields (`leak_type`, `recommended_channel`, `recommended_timing`), providing a final Pydantic validation layer that would reject any value not in the allowed set.

---

## 7. Checkout Security

**File:** `backend/app/routers/checkout.py`

### XSS Prevention: Order ID Validation

**Lines 13, 21:**

```python
ORDER_ID_PATTERN = re.compile(r"^order_[A-Za-z0-9]{8,30}$")

if not ORDER_ID_PATTERN.match(order_id):
    raise HTTPException(status_code=400, detail="Invalid order ID format")
```

The order ID is a path parameter that gets interpolated into HTML. The regex ensures it contains only `order_` followed by 8-30 alphanumeric characters. This eliminates any possibility of script injection through the order ID.

### JavaScript String Escaping

**Lines 152-155:**

```python
def _esc_js(s: str) -> str:
    import json
    safe = json.dumps(str(s))[1:-1]  # JSON-encode, strip outer quotes
    return safe.replace("'", "\\'").replace("</", "<\\/")
```

Values interpolated into JavaScript contexts use `json.dumps()` for proper escaping (handles quotes, backslashes, unicode), plus additional escaping for single quotes (the JS strings use single-quote delimiters) and `</` sequences (prevents script tag injection via `</script>`).

### HTML Escaping

**Lines 148-149:**

```python
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
```

Customer names displayed in HTML context are escaped for `&`, `<`, `>`, and `"`.

---

## 8. PII Protection

**File:** `backend/app/services/payment_links.py`

### Server-Side PII Storage

**Lines 19-30:**

```python
CHECKOUT_TOKEN_TTL = 86400  # 24 hours

def _store_checkout_context(order_id, customer_name, customer_email, customer_phone):
    r = get_redis()
    token = secrets.token_urlsafe(24)
    data = json.dumps({
        "order_id": order_id,
        "name": customer_name or "Customer",
        "email": customer_email or "",
        "phone": customer_phone or "",
    })
    r.set(f"checkout:{token}", data, ex=CHECKOUT_TOKEN_TTL)
    return token
```

**Design:** Customer PII (name, email, phone) is never placed in URLs. Instead:

1. A cryptographically random token (`secrets.token_urlsafe(24)` = 192 bits of entropy) is generated.
2. The PII is stored in Redis keyed by this token, with a 24-hour TTL.
3. The checkout URL contains only the opaque token: `/pay/{order_id}?t={token}`.
4. On page load, the server retrieves PII from Redis and renders it into the HTML server-side.

**Why this matters:**

- URLs appear in browser history, server access logs, referrer headers, and analytics tools. Keeping PII out of URLs prevents inadvertent exposure.
- The 24-hour TTL ensures PII is automatically purged. After expiry, the checkout page still works but shows "Customer" as the name and empty prefill fields.
- The token is 192 bits of randomness, making brute-force enumeration infeasible.

---

## 9. Database-Level Safety

### Premature Exhaustion Trigger

**File:** `backend/migrations/004_prevent_premature_exhaustion.sql`

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

**What it blocks:** Any `UPDATE` that tries to set `status = 'exhausted'` when `attempt_count < max_attempts` and no `skip_reason` is provided. Instead of allowing the update, the trigger silently reverts the status to its previous value.

**Why it exists:** This is the last line of defense against bugs or external writers (manual SQL queries, n8n workflows, third-party integrations) that might prematurely mark an event as exhausted before the customer has been contacted. In a payment recovery system, a premature exhaustion means lost revenue.

**Allowed exhaustion conditions:**
1. `attempt_count >= max_attempts` — the recovery budget is genuinely used up.
2. `max_attempts = 0` — the event was classified as unrecoverable (e.g., fraud).
3. `skip_reason IS NOT NULL` — the application code provided an explicit reason (e.g., window expired).

### Row-Level Security (RLS)

**File:** `backend/migrations/005_missing_columns_and_rls.sql`, lines 14-22

```sql
ALTER TABLE recovery_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE recovery_attempts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_recovery_events" ON recovery_events
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_recovery_attempts" ON recovery_attempts
  FOR ALL USING (auth.role() = 'service_role');
```

RLS is enabled on both tables. Only the `service_role` (used by the backend via the Supabase service key) can read or write data. This means:

- The Supabase anon key cannot access recovery data.
- Direct Supabase client connections from the frontend cannot bypass the API.
- PostgREST endpoints without the service role key are blocked.

---

## 10. CORS Configuration

**File:** `backend/app/main.py`, lines 21-36

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "https://albertabishek.com",
        "https://app.albertabishek.com",
        "https://api.albertabishek.com",
        "https://razorpay.albertabishek.com",
    ],
    allow_origin_regex=r"https://recovery-router[a-z0-9-]*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
```

**Properties:**

- **Explicit allowlist:** No wildcard `*` origins. Only known production domains and local development servers are permitted.
- **Vercel preview regex:** `recovery-router[a-z0-9-]*\.vercel\.app` allows Vercel preview deployments (which have dynamic subdomains) without opening to all `.vercel.app` domains.
- **Credentials enabled:** Required for the cookie-based auth flow.
- **Restricted headers:** Only `Content-Type` and `Authorization` are allowed, limiting the attack surface for header-based exploits.

---

## 11. Authentication

**File:** `backend/app/auth.py`

### Dashboard Auth

```python
def require_auth(authorization: str = Header(None)):
    if not settings.APP_PASSWORD:
        raise HTTPException(status_code=500, detail="APP_PASSWORD not configured on server")
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:]
    if not hmac.compare_digest(token, settings.APP_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")
    return True
```

- **Fail-closed:** If `APP_PASSWORD` is not configured, all requests are rejected with a 500 (line 8), not silently allowed.
- **Timing-safe comparison:** `hmac.compare_digest()` (line 13) prevents password guessing via timing attacks.
- The analytics endpoint uses this as a dependency: `dependencies=[Depends(require_auth)]` (`analytics.py`, line 7).

### Login Endpoint

**File:** `backend/app/main.py`, lines 71-75

The `/api/login` endpoint also uses `hmac.compare_digest` via `verify_login()`.

**Note:** The login endpoint returns the password itself as the token (line 74: `"token": settings.APP_PASSWORD`). This is a single-user demo system with a shared password, not a production auth system. See "Known Limitations" below.

---

## 12. Known Limitations and Open Items

### Security concerns present in the current implementation

1. **Single shared password for dashboard auth.** The `APP_PASSWORD` is used both as the credential and the bearer token. There is no session management, token rotation, or multi-user support. Acceptable for a buildathon demo; needs replacement for production.

2. **No HTTPS enforcement in application code.** The application relies on the deployment platform (Railway, Vercel) to terminate TLS. There is no HSTS header or HTTP-to-HTTPS redirect at the application level.

3. **Checkout page loads external script.** The checkout page (`checkout.py`, line 102) loads `https://checkout.razorpay.com/v1/checkout.js` from Razorpay's CDN. This is required by Razorpay's integration but means the page's security depends on Razorpay's CDN integrity. No Subresource Integrity (SRI) hash is used (Razorpay does not publish SRI hashes for their checkout script).

4. **No Content-Security-Policy header on checkout page.** The inline `<script>` and external Razorpay CDN script would need explicit CSP directives. Currently no CSP is set, which means the checkout page relies on output escaping alone for XSS prevention.

5. **Redis as single point of failure for rate limiting and deduplication.** If Redis goes down, rate limiting and fast-path deduplication stop working. The database dedup layer provides a safety net for duplicates, but rate limiting has no fallback.

6. **RLS policies are service-role only.** The current RLS setup grants full access to `service_role` and blocks everything else. There are no per-user or per-merchant row-level policies. This is appropriate for a single-tenant system but would need extension for multi-tenancy.

7. **Razorpay API credentials in environment variables.** `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` are stored as environment variables. This is standard practice for server deployments but requires the deployment platform to protect these values.

8. **AI model API key in environment.** `OPENROUTER_API_KEY` is similarly stored as an environment variable. A compromised key could run up costs on the OpenRouter account but cannot access payment data.

### What is NOT a concern

- **Test-mode vs. live-mode separation:** The system uses Razorpay test-mode keys. Test and live webhooks use different signing secrets, so test-mode code cannot accidentally process live payments.
- **SQL injection:** The application uses Supabase's Python client with parameterized queries, not raw SQL string concatenation.
- **Webhook replay attacks:** Deduplicated at both Redis and database levels, so replaying a captured webhook has no effect.

---

## Summary of Defense Layers

```
Inbound webhook
  |
  +-- [1] Body size check (256 KB)
  +-- [2] HMAC-SHA256 signature verification
  +-- [3] Rate limiting (100/min sliding window)
  +-- [4] Redis dedup (SET NX, 1h TTL)
  |
  v
Celery task
  |
  +-- [5] DB dedup query (payment_id/order_id/invoice_id)
  +-- [6] DB unique partial indexes (durable dedup)
  +-- [7] Input sanitization (truncation + control char strip)
  +-- [8] AI output validation (12 categories, clamped floats)
  +-- [9] Per-event Redis distributed lock (300s TTL)
  +-- [10] Conditional DB update (.eq("status", "pending"))
  +-- [11] Per-resource messaging cooldown
  |
  v
Database
  |
  +-- [12] Premature exhaustion trigger
  +-- [13] Row-Level Security (service_role only)
  +-- [14] Unique indexes on payment_id/order_id/invoice_id
  +-- [15] Idempotency key on recovery_attempts
```

Each layer is independent. A failure in any single layer does not compromise the system because the next layer catches it.

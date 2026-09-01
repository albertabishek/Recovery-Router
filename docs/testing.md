# Recovery Router -- Testing Documentation

**Author:** Albert Abishek I
**Project:** Recovery Router (Razorpay AI Buildathon 2026, Track 3)
**Last updated:** 2026-08-31

---

## 1. Test Suite Overview

| Metric | Value |
|---|---|
| Total test functions | 114 |
| Test files | 6 |
| Pytest test files | 5 (`test_api.py`, `test_pipeline.py`, `test_security.py`, `test_errors.py`, `test_load.py`) |
| Standalone test script | 1 (`e2e_test.py`) |
| Parametrized test cases | 10 (pipeline scenario matrix) |
| Effective test cases (with parametrize expansion) | 123 |
| Framework | pytest (pytest files) + custom runner (e2e_test.py) |
| Shared fixtures | `conftest.py` |
| Support scripts | `generate_test_data.py`, `process_queue.py`, `generate_and_process.py` |

### How to Run

```bash
# Run all pytest tests (requires server + Redis + Celery running)
cd backend
pytest tests/ -v

# Run a specific test file
pytest tests/test_api.py -v
pytest tests/test_security.py -v

# Run the standalone e2e suite
python tests/e2e_test.py

# Generate bulk test data (100 events)
python tests/generate_test_data.py

# Generate and process events directly (bypasses Celery)
python tests/generate_and_process.py
```

**Prerequisites:** The server must be running at `http://localhost:8000` (or `http://127.0.0.1:8000` for e2e_test.py). Redis and Celery workers must be active for pipeline tests.

---

## 2. Test File Inventory

### 2.1 `conftest.py` -- Shared Fixtures and Helpers

**Path:** `backend/tests/conftest.py`
**Purpose:** Provides pytest fixtures, scenario definitions, expected outcomes, and helper functions used across all pytest test files.

**Key components:**

- **`SCENARIOS`** (line 15): List of 10 `(event_type, scenario)` tuples covering all built-in simulation scenarios.
- **`EXPECTED`** (line 28): Dictionary mapping each scenario to its expected classification category, recommended channel, status, max_attempts range, and recovery probability range.
- **Fixtures:**
  - `client` (line 42): Session-scoped httpx client with 30s timeout.
  - `api` (line 48): Alias for `client`, used by all test classes.
- **Helper functions:**
  - `wait_for_celery()` (line 53): Polls an event by ID until it reaches a target status (pending, no_action_needed, exhausted, recovered). Max wait configurable, defaults to 45 seconds.
  - `simulate_and_wait()` (line 76): Fires a simulation via `/api/simulate`, waits for the new event to appear and be processed, then returns `(event_id, event_data)`. Handles rate limiting with retries.

**Scenario matrix defined in conftest:**

| Scenario | Event Type | Expected Category | Expected Channel | Expected Status |
|---|---|---|---|---|
| `upi_timeout` | payment_failure | upi_timeout | whatsapp | pending |
| `card_expired` | payment_failure | card_expired | email, whatsapp | pending |
| `insufficient_funds` | payment_failure | insufficient_funds | sms, email, whatsapp | pending |
| `bank_downtime` | payment_failure | bank_downtime | whatsapp, sms | pending |
| `gateway_error` | payment_failure | gateway_error | whatsapp, sms | pending |
| `fraud_decline` | payment_failure | unrecoverable_decline | none | no_action_needed |
| `high_value_cart` | cart_abandonment | high_intent or browse_only | whatsapp, email, none | pending or no_action_needed |
| `low_value_cart` | cart_abandonment | browse_only_abandonment | none | no_action_needed |
| `recent_invoice` | invoice_overdue | recently_overdue | whatsapp, email | pending |
| `old_invoice` | invoice_overdue | long_overdue | email | pending |

---

### 2.2 `test_api.py` -- API Endpoint Tests (38 tests)

**Path:** `backend/tests/test_api.py`
**Purpose:** Tests all 12 API endpoints with valid, invalid, and edge-case inputs.

#### TestHealthEndpoint (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 1 | `test_health_returns_ok` | Health endpoint returns 200 with status "ok", Redis "ok", Celery present, Supabase "configured" |
| 2 | `test_health_has_queue_depth` | Health response includes `queue_depth` as an integer |

#### TestRootEndpoint (1 test)

| # | Test Function | What It Tests |
|---|---|---|
| 3 | `test_root_returns_info` | Root endpoint returns API name "Recovery Router API" and version |

#### TestEventsEndpoint (8 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 4 | `test_get_events_default` | GET /api/events returns events list and total count |
| 5 | `test_get_events_with_limit` | Limit parameter caps the number of returned events |
| 6 | `test_get_events_with_offset` | Offset parameter returns different events than offset=0 |
| 7 | `test_get_events_filter_by_status_pending` | Status filter "pending" returns only pending events |
| 8 | `test_get_events_filter_by_status_exhausted` | Status filter "exhausted" returns only exhausted events |
| 9 | `test_get_events_filter_by_status_no_action` | Status filter "no_action_needed" returns only no-action events |
| 10 | `test_get_events_filter_by_status_recovered` | Status filter "recovered" returns only recovered events |
| 11 | `test_events_schema_completeness` | Event objects contain all 11 required fields (id, event_type, amount, currency, status, failure_category, recovery_probability, recommended_channel, attempt_count, max_attempts, created_at) |

#### TestEventTraceEndpoint (3 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 12 | `test_trace_existing_event` | Trace endpoint returns event details and attempts list for a valid event ID |
| 13 | `test_trace_nonexistent_event` | Trace for ID 999999 returns 404 or 200 gracefully |
| 14 | `test_trace_attempts_ordered` | Attempt records are ordered by attempt_number (ascending) |

#### TestAnalyticsEndpoint (5 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 15 | `test_analytics_returns_data` | Analytics returns summary with total_events, recovered_count, recovered_amount, pending_count, exhausted_count, no_action_count |
| 16 | `test_analytics_has_ai_lift` | Analytics response includes `ai_lift` metric |
| 17 | `test_analytics_has_channel_ranking` | Analytics includes `channel_ranking` as a list |
| 18 | `test_analytics_has_by_event_type` | Analytics includes breakdown `by_event_type` |
| 19 | `test_analytics_totals_consistent` | Sum of recovered + pending + exhausted + no_action does not exceed total_events |

#### TestAuditLogsEndpoint (3 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 20 | `test_audit_logs_returns_data` | Audit logs endpoint returns a list |
| 21 | `test_audit_log_schema` | Audit log entries contain required fields: id, recovery_event_id, channel_used, outcome, created_at |
| 22 | `test_audit_logs_filter_by_event_id` | Filtering audit logs by event_id returns only logs for that event |

#### TestSimulateEndpoint (5 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 23 | `test_simulate_valid` | Valid simulation (upi_timeout) returns 200 with status "accepted" |
| 24 | `test_simulate_with_customer_details` | Simulation with customer name, email, and phone is accepted |
| 25 | `test_simulate_invalid_scenario` | Invalid scenario name returns 400 or 422 |
| 26 | `test_simulate_missing_event_type` | Missing event_type returns 422 |
| 27 | `test_simulate_invalid_event_type` | Invalid event_type returns 400 or 422 |

#### TestControlEndpoint (5 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 28 | `test_pause_pending_event` | Pausing a pending event returns status "paused" (then resumes for cleanup) |
| 29 | `test_resume_paused_event` | Resuming a paused event returns status "resumed" |
| 30 | `test_pause_exhausted_event_fails` | Pausing an exhausted event returns 400 or 409 |
| 31 | `test_control_nonexistent_event` | Control action on nonexistent event returns 404 |
| 32 | `test_control_invalid_action` | Invalid action "explode" returns 400 or 422 |

#### TestLiveCheckoutEndpoint (4 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 33 | `test_live_checkout_valid` | Valid checkout with amount=100 returns order_id starting with "order_" |
| 34 | `test_live_checkout_zero_amount` | Zero amount returns 400 |
| 35 | `test_live_checkout_negative_amount` | Negative amount returns 400 |
| 36 | `test_live_checkout_exceeds_max` | Amount 99999 (exceeds maximum) returns 400 |

#### TestCheckoutPageEndpoint (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 37 | `test_pay_page_returns_html` | Checkout page for a valid order contains "razorpay" text |
| 38 | `test_pay_page_invalid_order` | Invalid order ID still serves the page (Razorpay handles the error client-side) |

---

### 2.3 `test_pipeline.py` -- End-to-End Pipeline Tests (6 functions, 15 cases)

**Path:** `backend/tests/test_pipeline.py`
**Purpose:** Tests the full pipeline: simulate -> classify -> route -> send -> track.

#### TestPipelineScenarios (1 function, 10 parametrized cases)

| # | Test Function | What It Tests |
|---|---|---|
| 1-10 | `test_scenario_classification[upi_timeout]` through `test_scenario_classification[old_invoice]` | For each of the 10 scenarios: fires simulation, waits for processing, then verifies (a) failure_category matches expected, (b) recommended_channel is in the expected set, (c) status matches expected, (d) max_attempts is within expected range, (e) recovery_probability is within expected range |

#### TestNoActionPipeline (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 11 | `test_fraud_decline_no_action` | Fraud decline results in status "no_action_needed", max_attempts 0, attempt_count 0, no next_action_at, no recovery_window_ends |
| 12 | `test_low_value_cart_no_action` | Low-value cart abandonment results in "no_action_needed" with 0 attempts |

#### TestPipelineAuditTrail (1 test)

| # | Test Function | What It Tests |
|---|---|---|
| 13 | `test_pending_event_creates_attempt` | A pending event has at least one audit log attempt with attempt_number=1 and a valid channel (whatsapp, email, or sms) |

#### TestPipelineRecoveryWindow (1 test)

| # | Test Function | What It Tests |
|---|---|---|
| 14 | `test_pending_has_recovery_window` | Pending events have a non-null `recovery_window_ends` timestamp |

#### TestPipelineDedup (1 test)

| # | Test Function | What It Tests |
|---|---|---|
| 15 | `test_duplicate_simulations_distinct` | Two identical simulations via `/api/simulate` create 2 or more separate events (simulation dedup differs from webhook dedup) |

---

### 2.4 `test_security.py` -- Security Tests (20 tests)

**Path:** `backend/tests/test_security.py`
**Purpose:** Tests SQL injection, XSS, CORS, webhook signatures, input validation, and path traversal.

#### TestSQLInjection (3 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 1 | `test_events_status_injection` | SQL injection via status parameter `'; DROP TABLE recovery_events;--` does not crash the DB; subsequent query still works |
| 2 | `test_audit_logs_event_id_injection` | SQL injection `1 OR 1=1` in event_id parameter is handled safely |
| 3 | `test_trace_id_injection` | SQL injection `1;DROP TABLE recovery_events` in URL path returns error, not execution |

#### TestXSS (3 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 4 | `test_simulate_xss_in_name` | `<script>alert('xss')</script>` in customer_name is sanitized in the response |
| 5 | `test_simulate_xss_in_email` | XSS payload `<img onerror=alert(1) src=x>@evil.com` in email is rejected or sanitized |
| 6 | `test_events_response_is_json` | Events endpoint returns `application/json` content type (prevents browser XSS interpretation) |

#### TestCORS (3 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 7 | `test_cors_preflight` | OPTIONS request from localhost:5173 returns 200 or 204 |
| 8 | `test_cors_allows_frontend_origin` | CORS header allows `http://localhost:5173` or `*` |
| 9 | `test_cors_allows_tunnel_origin` | CORS header allows the production tunnel origin `https://app.albertabishek.com` |

#### TestWebhookSecurity (4 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 10 | `test_webhook_without_signature` | Webhook POST without signature header is handled (returns 200, 400, 401, or 403) |
| 11 | `test_webhook_invalid_signature` | Webhook with invalid `X-Razorpay-Signature` header is handled |
| 12 | `test_webhook_empty_body` | Webhook with empty body returns an error status |
| 13 | `test_webhook_malformed_json` | Webhook with non-JSON body and JSON content-type returns error |

#### TestInputValidation (5 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 14 | `test_simulate_oversized_payload` | 10,000-char customer_name and 5,000-char email are handled without crash |
| 15 | `test_simulate_special_chars` | Python code injection attempt in customer_name is safely handled |
| 16 | `test_control_invalid_json` | Non-JSON body with JSON content-type on control endpoint returns 400/422 |
| 17 | `test_live_checkout_string_amount` | String "abc" as amount returns 400 or 422 |
| 18 | `test_live_checkout_huge_amount` | Amount 999999999 is rejected |

#### TestPathTraversal (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 19 | `test_event_id_path_traversal` | Path traversal `/../../../etc/passwd/trace` in event URL returns error |
| 20 | `test_pay_path_traversal` | Path traversal in `/pay/` URL returns error or safe response |

---

### 2.5 `test_errors.py` -- Edge Cases and Error Handling (13 tests)

**Path:** `backend/tests/test_errors.py`
**Purpose:** Tests duplicate webhooks, invalid state transitions, missing fields, boundary values, and organic recovery detection.

#### TestDuplicateWebhooks (1 test)

| # | Test Function | What It Tests |
|---|---|---|
| 1 | `test_duplicate_payment_captured_idempotent` | Sending the same `payment.captured` webhook twice to recovery-tracker does not cause errors (idempotency check) |

#### TestStatusTransitions (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 2 | `test_cannot_resume_recovered` | Resuming a recovered event returns 400 or 409 (invalid transition) |
| 3 | `test_cannot_pause_no_action` | Pausing a no_action_needed event returns 400 or 409 |

#### TestMissingFields (4 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 4 | `test_simulate_empty_body` | Empty JSON body to simulate returns 422 |
| 5 | `test_simulate_missing_scenario` | Missing `scenario` field returns 422 or is handled |
| 6 | `test_live_checkout_empty_body` | Empty JSON body to live-checkout is handled |
| 7 | `test_control_empty_body` | Empty JSON body to control endpoint returns 400/422 |

#### TestBoundaryValues (5 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 8 | `test_events_limit_zero` | Limit=0 is handled gracefully |
| 9 | `test_events_negative_offset` | Negative offset is handled gracefully |
| 10 | `test_events_very_large_limit` | Limit=99999 is handled (returns 200 or error) |
| 11 | `test_trace_zero_id` | Event ID 0 returns 200 or 404 |
| 12 | `test_trace_negative_id` | Event ID -1 returns 200, 404, or 422 |

#### TestOrganicRecovery (1 test)

| # | Test Function | What It Tests |
|---|---|---|
| 13 | `test_unmatched_payment_logged` | A `payment.captured` webhook with no matching recovery event is logged as organic recovery |

---

### 2.6 `test_load.py` -- Load and Concurrency Tests (6 tests)

**Path:** `backend/tests/test_load.py`
**Purpose:** Tests parallel requests, race conditions, and endpoint performance.

#### TestConcurrentSimulations (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 1 | `test_parallel_simulations` | 5 concurrent simulations (different scenarios) all return 200 or 429; at least 1 succeeds |
| 2 | `test_parallel_event_reads` | 10 concurrent GET /api/events requests all return 200 |

#### TestRaceConditions (1 test)

| # | Test Function | What It Tests |
|---|---|---|
| 3 | `test_concurrent_pause_resume` | Concurrent pause and resume on the same event does not corrupt state; final status is either "pending" or "paused" |

#### TestEndpointPerformance (3 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 4 | `test_health_response_time` | Health check responds in under 15 seconds |
| 5 | `test_events_response_time` | Events list (limit=20) responds in under 5 seconds |
| 6 | `test_analytics_response_time` | Analytics endpoint responds in under 15 seconds |

---

### 2.7 `e2e_test.py` -- Standalone End-to-End Test Suite (31 tests)

**Path:** `backend/tests/e2e_test.py`
**Purpose:** Comprehensive standalone test script that exercises every endpoint and feature. Uses `requests` library with its own test runner (not pytest). Run directly with `python tests/e2e_test.py`.

#### Section 1: Root and Health (3 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 1 | `test_root` | Root returns name "Recovery Router API", version "1.0.0", docs link |
| 2 | `test_health` | Health returns "ok" or "degraded", checks supabase/redis/celery services |
| 3 | `test_docs` | Swagger/OpenAPI docs page loads |

#### Section 2: Webhook recovery-router (8 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 4 | `test_webhook_payment_failure` | Payment failure webhook with UPI timeout is accepted |
| 5 | `test_webhook_cart_abandonment` | Cart abandonment webhook with items and cart_value is accepted |
| 6 | `test_webhook_invoice_overdue` | Invoice overdue webhook with days_overdue is accepted |
| 7 | `test_webhook_razorpay_raw_format` | Razorpay native `payment.failed` event format (nested payload.payment.entity) is accepted |
| 8 | `test_webhook_dedup` | Same payment_id sent twice: first accepted, second returns "duplicate" |
| 9 | `test_webhook_dedup_hash_fallback` | Identical payloads without explicit IDs are deduped via content hash |
| 10 | `test_webhook_invalid_payload` | Payload with only `{"bad": "data"}` returns 400 |
| 11 | `test_webhook_invalid_event_type` | Invalid event_type returns 400 or 422 |

#### Section 3: Webhook recovery-tracker (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 12 | `test_tracker_ignored_event` | `payment.authorized` event type is ignored (returns status "ignored") |
| 13 | `test_tracker_no_match` | `payment.captured` with no matching recovery event returns "no_match" |

#### Section 4: Events API (4 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 14 | `test_events_list` | Events list returns events array and total count |
| 15 | `test_events_pagination` | Pagination with limit=5 returns at most 5 events |
| 16 | `test_events_filter_status` | Status filter returns only matching events |
| 17 | `test_events_filter_event_type` | Event type filter returns only matching events |

#### Section 5: Analytics (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 18 | `test_analytics` | Analytics returns all expected keys (summary, ai_lift, by_event_type, by_channel, channel_ranking, by_failure_category, generated_at), recovery_rate_percent is 0-100 |
| 19 | `test_analytics_cached` | Second analytics call is not significantly slower than first (cache working) |

#### Section 6: Simulator (2 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 20 | `test_simulate_invalid_scenario` | Invalid scenario returns 400 or 429 |
| 21 | `test_simulate_all_scenarios` | All 10 built-in scenarios are accepted; at least 8 out of 10 succeed (allows for rate limiting) |

#### Section 7: Checkout Page (4 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 22 | `test_checkout_valid` | Checkout page renders with "Razorpay" and "Complete Your Payment" text |
| 23 | `test_checkout_xss_blocked` | `<script>alert(1)</script>` in name parameter is escaped to `&lt;script&gt;` |
| 24 | `test_checkout_invalid_order_id` | Path traversal in order ID returns 400, 404, or 422 |
| 25 | `test_checkout_order_id_injection` | SQL injection in order ID is rejected |

#### Section 8: Rate Limiting (1 test)

| # | Test Function | What It Tests |
|---|---|---|
| 26 | `test_rate_limit_simulation` | Sending 15 rapid simulate requests triggers 429 rate limit (configured at 10 req/60s) |

#### Section 9: Edge Cases (5 tests)

| # | Test Function | What It Tests |
|---|---|---|
| 27 | `test_minimal_payload` | Webhook accepts a minimal payload (just event_type, payment_id, amount) |
| 28 | `test_large_amount` | Very large amount (9,999,999.99) is handled |
| 29 | `test_unicode_customer_name` | Unicode customer name (Hindi script) is accepted |
| 30 | `test_empty_optional_fields` | Null values for optional fields (email, phone, name) are accepted |
| 31 | `test_zero_amount_cart` | Zero cart_value and zero items_in_cart are accepted |

---

## 3. What's Tested

### AI Classification Accuracy

The pipeline tests (`test_pipeline.py`) verify that the AI classifier returns valid, expected categories for each scenario. Each of the 10 scenarios has a defined expected category (or set of acceptable categories) and probability range. For example:

- **UPI timeout** must classify as `upi_timeout` with probability 0.6-1.0
- **Fraud decline** must classify as `unrecoverable_decline` with probability 0.0-0.1
- **High-value cart** may classify as either `high_intent_abandonment` or `browse_only_abandonment`

### Recovery Pipeline (End-to-End)

Tests verify the full flow: webhook/simulation intake -> AI classification -> channel routing -> attempt creation -> status tracking. The `simulate_and_wait` helper polls until processing completes, verifying that Celery workers process events correctly.

### Escalation Logic

- Channel routing is verified per scenario (e.g., UPI timeout -> WhatsApp, card expired -> email or WhatsApp)
- Max attempts ranges are validated (e.g., 2-5 for most recoverable scenarios, 0 for no-action)
- No-action events (fraud, low-value carts) correctly skip all recovery attempts

### Analytics

- Summary statistics contain all required fields
- Totals are internally consistent (parts do not exceed total)
- AI lift metric is present
- Channel ranking and per-event-type breakdowns are returned
- Cache performance is validated

### Deduplication

- **Webhook-level dedup:** Same `payment_id` sent twice returns "duplicate" on second call (e2e_test.py)
- **Hash-based dedup:** Identical payloads without explicit IDs are caught via content hash (e2e_test.py)
- **Simulation dedup:** Duplicate simulations via `/api/simulate` correctly create separate events (test_pipeline.py)

### Webhook Handling

- Razorpay native format (`payload.payment.entity`) is normalized and accepted
- Flat format (`event_type`, `payment_id`, etc.) is accepted
- Missing/invalid signatures are handled gracefully
- Empty and malformed bodies return proper error codes
- Recovery tracker: `payment.captured` matching, `payment.authorized` ignored, unmatched events logged as organic

---

## 4. Key Test Scenarios

### AI Fallback Chain

The `test_scenario_classification` parametrized test verifies that each of the 10 scenarios produces a valid classification even when AI models may return varying results. Acceptable category lists (e.g., `high_value_cart` can be either `high_intent_abandonment` or `browse_only_abandonment`) account for AI variability.

### Dynamic Budget Calculation

Recovery probability ranges and max_attempts ranges are validated per scenario. For example:
- Recoverable scenarios (UPI timeout, bank downtime) have probability 0.5-1.0 and 2-5 max attempts
- Unrecoverable scenarios (fraud decline) have probability 0.0-0.1 and 0 max attempts

### Ghost Recovery Prevention

- `test_fraud_decline_no_action`: Verifies fraud declines get `no_action_needed` status with zero attempts, no next_action_at, and no recovery_window_ends
- `test_low_value_cart_no_action`: Verifies low-value carts are not pursued
- `test_unmatched_payment_logged`: Unmatched payment captures are logged as organic, not falsely attributed

### Race Condition Handling

- `test_concurrent_pause_resume`: Sends pause and resume simultaneously on the same event, verifies final state is valid (pending or paused), not corrupted
- `test_parallel_simulations`: 5 threads fire different scenarios concurrently
- `test_parallel_event_reads`: 10 concurrent read requests all succeed

### Edge Cases

- **Invalid input:** Empty bodies, missing fields, wrong types (string for amount)
- **Boundary values:** Limit=0, negative offset, limit=99999, event ID=0, event ID=-1
- **Oversized input:** 10,000-char names, 5,000-char emails
- **Unicode:** Hindi script customer names
- **Null fields:** Null email, phone, and name
- **Invalid state transitions:** Cannot resume recovered events, cannot pause no-action events

---

## 5. Test Infrastructure

### Fixtures (`conftest.py`)

| Fixture | Scope | Purpose |
|---|---|---|
| `client` | session | httpx.Client pointed at `http://localhost:8000` with 30s timeout |
| `api` | session | Alias for `client` |

### Mocking Strategy

**No mocks are used.** All tests are integration tests that run against a live server. This means:

- The actual Razorpay AI classification pipeline runs
- Real Redis is used for deduplication and queue management
- Real Supabase database stores events
- Real Celery workers process tasks
- Rate limiting is real (tests handle 429 responses)

This design choice ensures tests validate the actual production behavior, not mocked approximations.

### Test Configuration

- **Server URL:** `http://localhost:8000` (pytest) / `http://127.0.0.1:8000` (e2e_test.py)
- **Test emails:** `include1iostream2@gmail.com`, `albertabishek369@gmail.com`, `study1only2@gmail.com`
- **Test phones:** `+919042824369`, `+918940715740`
- **Timeouts:** 30s for HTTP client, up to 60s for pipeline processing waits
- **Rate limit handling:** Tests retry on 429 with exponential backoff (3s * attempt)

### Test Helpers

| Helper | Location | Purpose |
|---|---|---|
| `wait_for_celery()` | conftest.py:53 | Polls event status until processing completes |
| `simulate_and_wait()` | conftest.py:76 | Fires simulation, finds new event, waits for processing |
| `test()` | e2e_test.py:21 | Custom test runner with pass/fail counting and error collection |

---

## 6. Bulk Data Generator

### `generate_test_data.py`

**Path:** `backend/tests/generate_test_data.py`
**Purpose:** Generates 100 diverse recovery events via the webhook API to populate the database for demo and testing.

**What it generates:**
- 50 payment failures (random error codes: TIMEOUT, BANK_DOWNTIME, CARD_EXPIRED, INSUFFICIENT_FUNDS, GATEWAY_ERROR, NETWORK_ERROR, UPI_PIN_ERROR, CARD_DECLINED)
- 30 cart abandonments (60% high-value, 40% low-value)
- 20 overdue invoices (days overdue: 1 to 90, amounts: 5,000 to 100,000)

**Data variety:**
- 30 Indian names for customer diversity
- 5 email domains (gmail.com, yahoo.co.in, outlook.com, hotmail.com, rediffmail.com)
- Random phone numbers in +91 format
- 15 different amount tiers from 199 to 24,999

**Usage:**
```bash
cd backend
python tests/generate_test_data.py
```
Requires the server to be running. Sends events via `POST /webhook/recovery-router` with 100ms delays between requests. Prints analytics summary after completion.

### `generate_and_process.py`

**Path:** `backend/tests/generate_and_process.py`
**Purpose:** Generates 100 events and processes them directly by calling `process_recovery_event()`, bypassing the Celery queue. Useful for populating the database when Celery workers are not running.

**What it generates:**
- 60 payment failures
- 25 cart abandonments
- 15 overdue invoices

**Usage:**
```bash
cd backend
python tests/generate_and_process.py
```

### `process_queue.py`

**Path:** `backend/tests/process_queue.py`
**Purpose:** Reads pending Celery tasks from the Redis queue and executes them synchronously. Useful for testing without a Celery worker running.

**Usage:**
```bash
cd backend
python tests/process_queue.py
```
Processes up to 150 tasks from the `celery` Redis key, decoding Base64-encoded task bodies and calling `process_recovery_event()` directly.

---

## 7. Built-in Simulator Scenarios

The system includes 10 built-in simulation scenarios, all testable via `POST /api/simulate`. Each scenario generates a realistic event with appropriate metadata.

| # | Scenario | Event Type | What It Tests |
|---|---|---|---|
| 1 | `upi_timeout` | payment_failure | UPI payment timeout -- high recovery probability, WhatsApp channel |
| 2 | `card_expired` | payment_failure | Expired card -- medium recovery, email/WhatsApp channel |
| 3 | `insufficient_funds` | payment_failure | Insufficient funds -- variable recovery, multi-channel routing |
| 4 | `bank_downtime` | payment_failure | Bank server down -- high recovery, WhatsApp/SMS channel |
| 5 | `gateway_error` | payment_failure | Gateway technical error -- high recovery, WhatsApp/SMS channel |
| 6 | `fraud_decline` | payment_failure | Fraudulent transaction -- no recovery action taken |
| 7 | `high_value_cart` | cart_abandonment | High-value abandoned cart -- variable classification and channel |
| 8 | `low_value_cart` | cart_abandonment | Low-value abandoned cart -- no recovery action taken |
| 9 | `recent_invoice` | invoice_overdue | Recently overdue invoice -- moderate-high recovery, WhatsApp/email |
| 10 | `old_invoice` | invoice_overdue | Long-overdue invoice -- low recovery probability, email only |

**Event types covered:** payment_failure, cart_abandonment, invoice_overdue

**Channels exercised:** whatsapp, email, sms, none

**Statuses exercised:** pending, no_action_needed

---

## 8. Test Coverage Analysis

### Well-Tested Areas

- **API endpoints:** All 12 endpoints thoroughly tested with valid inputs, invalid inputs, and edge cases
- **Security:** SQL injection (3 vectors), XSS (3 vectors), CORS (3 origins), webhook signatures, input validation (5 cases), path traversal (2 vectors)
- **Pipeline classification:** All 10 scenarios verified for category, channel, status, max_attempts, and probability
- **State transitions:** Invalid transitions (resume recovered, pause no-action) are blocked
- **Deduplication:** Both payment_id-based and hash-based dedup verified
- **Concurrency:** Parallel reads, parallel writes, and race conditions tested
- **Edge cases:** Boundary values, missing fields, empty bodies, oversized inputs, unicode, null fields

### Potential Coverage Gaps

1. **Retry/escalation chain:** No tests verify what happens when attempt 1 fails and the system escalates to attempt 2 with a different channel. The recovery window and multi-attempt flow are not exercised end-to-end.

2. **Webhook signature verification with valid signature:** Tests only check invalid/missing signatures. No test sends a correctly signed webhook using HMAC-SHA256 to verify the happy path of signature validation.

3. **Recovery tracking (payment.captured matching):** The `recovery-tracker` webhook is tested for ignored events and no-match cases, but there is no test that creates a recovery event and then sends a matching `payment.captured` to verify the event transitions to "recovered" status.

4. **Celery task failure handling:** No tests simulate Celery task failures, retries, or dead-letter queue behavior.

5. **Database failure resilience:** No tests verify behavior when Supabase is down or returns errors.

6. **Rate limit reset:** Tests verify the rate limit triggers but do not verify it resets after the window expires.

7. **Pause/resume effect on scheduling:** Tests verify pause/resume status changes but not whether scheduled recovery attempts are actually suspended and resumed.

8. **Analytics accuracy under known data:** No test seeds a known set of events and verifies the exact analytics calculations (recovery rate, AI lift, channel ranking).

---

## 9. Running the Tests

### Full Pytest Suite

```bash
cd backend
pytest tests/ -v
```

### Individual Test Files

```bash
pytest tests/test_api.py -v          # 38 API endpoint tests
pytest tests/test_pipeline.py -v     # 15 pipeline tests (6 functions, 10 parametrized)
pytest tests/test_security.py -v     # 20 security tests
pytest tests/test_errors.py -v       # 13 edge case tests
pytest tests/test_load.py -v         # 6 load/concurrency tests
```

### Standalone E2E Suite

```bash
cd backend
python tests/e2e_test.py
```

### Running by Test Class

```bash
pytest tests/test_api.py::TestHealthEndpoint -v
pytest tests/test_security.py::TestSQLInjection -v
pytest tests/test_load.py::TestRaceConditions -v
```

### Running a Single Test

```bash
pytest tests/test_api.py::TestHealthEndpoint::test_health_returns_ok -v
pytest tests/test_pipeline.py::TestPipelineScenarios::test_scenario_classification[upi_timeout] -v
```

### Environment Setup

1. **Start the backend server:**
   ```bash
   cd backend
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. **Start Redis** (required for dedup, queue, caching)

3. **Start Celery worker** (required for pipeline tests):
   ```bash
   cd backend
   celery -A app.celery_app worker --loglevel=info
   ```

4. **Environment variables required:**
   - `SUPABASE_URL` and `SUPABASE_KEY` -- database access
   - `REDIS_URL` -- Redis connection
   - `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` -- for live checkout tests
   - AI provider keys (Gemini/OpenAI) -- for classification pipeline

5. **Install test dependencies:**
   ```bash
   pip install pytest httpx requests
   ```

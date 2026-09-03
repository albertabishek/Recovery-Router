-- Migration 006: Add delivery_failure_count to recovery_events
-- Tracks hard delivery failures separately from attempt_count (which only counts successes).
-- When delivery_failure_count > max_attempts and no message was ever delivered,
-- the escalation engine stops retrying instead of looping forever on invalid contacts.

ALTER TABLE recovery_events
  ADD COLUMN IF NOT EXISTS delivery_failure_count INTEGER DEFAULT 0;

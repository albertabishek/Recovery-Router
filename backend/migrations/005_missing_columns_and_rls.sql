-- Migration 005: Add missing columns to recovery_attempts + RLS policies
-- Fixes P0: escalation.py and recovery.py write message_id and notes columns
-- that don't exist in the original schema (migration 001).

-- 1. Add missing columns to recovery_attempts
ALTER TABLE recovery_attempts ADD COLUMN IF NOT EXISTS message_id TEXT;
ALTER TABLE recovery_attempts ADD COLUMN IF NOT EXISTS notes TEXT;

-- 2. Add action-level idempotency key to prevent duplicate sends on worker crash/retry
ALTER TABLE recovery_attempts ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_attempts_idempotency
  ON recovery_attempts (idempotency_key) WHERE idempotency_key IS NOT NULL;

-- 3. RLS policies — restrict access to service-role only
ALTER TABLE recovery_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE recovery_attempts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_recovery_events" ON recovery_events
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_recovery_attempts" ON recovery_attempts
  FOR ALL USING (auth.role() = 'service_role');

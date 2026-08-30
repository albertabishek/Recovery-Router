-- Prevent premature exhaustion: block status='exhausted' when attempt_count < max_attempts
-- This catches any external writer (n8n workflows, manual queries) that bypasses
-- the application-level safety guards in the Celery escalation engine.

CREATE OR REPLACE FUNCTION prevent_premature_exhaustion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  -- Only check when status is changing TO 'exhausted'
  IF NEW.status = 'exhausted' AND (OLD.status IS NULL OR OLD.status != 'exhausted') THEN
    -- Allow exhaustion only when:
    -- 1. attempt_count >= max_attempts (budget used up), OR
    -- 2. max_attempts = 0 (unrecoverable/no_action), OR
    -- 3. skip_reason is set (explicit reason provided by application code)
    IF (COALESCE(NEW.attempt_count, 0) < COALESCE(NEW.max_attempts, 5))
       AND COALESCE(NEW.max_attempts, 5) > 0
       AND NEW.skip_reason IS NULL THEN
      -- Block the exhaustion: revert status to pending
      RAISE WARNING 'Blocked premature exhaustion of event %: attempt_count=% < max_attempts=%, no skip_reason',
        NEW.id, COALESCE(NEW.attempt_count, 0), COALESCE(NEW.max_attempts, 5);
      NEW.status := OLD.status;
      NEW.current_strategy := OLD.current_strategy;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prevent_premature_exhaustion ON recovery_events;
CREATE TRIGGER trg_prevent_premature_exhaustion
  BEFORE UPDATE ON recovery_events
  FOR EACH ROW
  EXECUTE FUNCTION prevent_premature_exhaustion();

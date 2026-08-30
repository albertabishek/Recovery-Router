-- Reset sequences function for clearing all data
-- Run in Supabase SQL Editor

CREATE OR REPLACE FUNCTION reset_sequences()
RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
BEGIN
  ALTER SEQUENCE recovery_events_id_seq RESTART WITH 1;
  ALTER SEQUENCE recovery_attempts_id_seq RESTART WITH 1;
END;
$$;

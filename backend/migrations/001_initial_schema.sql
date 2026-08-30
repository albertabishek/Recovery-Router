-- Recovery Router: Initial Schema
-- Run against Supabase SQL Editor
-- Tables: recovery_events, recovery_attempts

CREATE TABLE IF NOT EXISTS recovery_events (
  id BIGSERIAL PRIMARY KEY,

  -- Event data
  event_type TEXT NOT NULL,
  payment_id TEXT,
  order_id TEXT,
  invoice_id TEXT,
  amount DECIMAL NOT NULL DEFAULT 0,
  currency TEXT DEFAULT 'INR',
  method TEXT,
  error_code TEXT,
  error_description TEXT,
  customer_email TEXT,
  customer_phone TEXT,
  customer_name TEXT,
  cart_value DECIMAL,
  items_in_cart INTEGER,
  days_overdue INTEGER,

  -- AI classification
  leak_type TEXT,
  failure_category TEXT,
  recovery_probability FLOAT,
  recommended_action TEXT,
  recommended_channel TEXT,
  recommended_timing TEXT,
  reasoning TEXT,
  alternative_action TEXT,
  skip_reason TEXT,

  -- Status tracking
  -- Values: pending | paused | recovered | exhausted | no_action_needed | organic_recovery
  status TEXT DEFAULT 'pending',
  recovered_at TIMESTAMPTZ,
  recovered_amount DECIMAL,

  -- Agent state (escalation loop)
  attempt_count INTEGER DEFAULT 0,
  last_attempt_at TIMESTAMPTZ,
  max_attempts INTEGER DEFAULT 5,
  current_strategy TEXT DEFAULT 'initial',
  next_action_at TIMESTAMPTZ,
  opted_out BOOLEAN DEFAULT false,
  recovery_window_ends TIMESTAMPTZ,
  escalation_level INTEGER DEFAULT 0,

  -- Metadata
  source TEXT DEFAULT 'api',
  razorpay_raw BOOLEAN DEFAULT false,
  fallback_classification BOOLEAN DEFAULT false,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_recovery_events_status ON recovery_events(status);
CREATE INDEX IF NOT EXISTS idx_recovery_events_pending_next ON recovery_events(status, next_action_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_recovery_events_order_id ON recovery_events(order_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_recovery_events_payment_id ON recovery_events(payment_id);
CREATE INDEX IF NOT EXISTS idx_recovery_events_invoice_id ON recovery_events(invoice_id);
CREATE INDEX IF NOT EXISTS idx_recovery_events_created_at ON recovery_events(created_at DESC);

-- Enable realtime for frontend
ALTER PUBLICATION supabase_realtime ADD TABLE recovery_events;


CREATE TABLE IF NOT EXISTS recovery_attempts (
  id BIGSERIAL PRIMARY KEY,
  recovery_event_id BIGINT REFERENCES recovery_events(id),
  attempt_number INTEGER NOT NULL,
  channel_used TEXT,
  action_taken TEXT,
  outcome TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recovery_attempts_event_id ON recovery_attempts(recovery_event_id);
CREATE INDEX IF NOT EXISTS idx_recovery_attempts_created_at ON recovery_attempts(created_at DESC);

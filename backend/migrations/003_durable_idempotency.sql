-- Durable idempotency: DB-backed deduplication for webhook events.
-- The application checks existing payment_id/order_id/invoice_id before inserting.
-- Redis remains the fast-path cache; these unique indexes are the durable fallback.
-- Simulator events use TEST_ prefixes and are excluded from uniqueness.

CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_events_payment_id_unique
  ON recovery_events (payment_id)
  WHERE payment_id IS NOT NULL AND payment_id NOT LIKE 'pay_TEST_%';

CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_events_order_id_unique
  ON recovery_events (order_id)
  WHERE order_id IS NOT NULL AND order_id NOT LIKE 'order_TEST_%';

CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_events_invoice_id_unique
  ON recovery_events (invoice_id)
  WHERE invoice_id IS NOT NULL;

-- Unique constraint for reconciliation: prevent double-attribution of recovered payments.
ALTER TABLE recovery_events
  ADD COLUMN IF NOT EXISTS recovered_payment_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_events_recovered_payment_unique
  ON recovery_events (recovered_payment_id)
  WHERE recovered_payment_id IS NOT NULL;

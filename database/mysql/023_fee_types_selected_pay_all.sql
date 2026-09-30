-- 023: fee types, fees for chosen students, and paying several fees at once.
-- category: tuition, transport, exam, books, uniform, admission or other.
--   Fees made before this are 'other' (their names still say what they are).
-- applies_to: 'class' bills every student in the class (and joiners, on sync),
--   'selected' bills only the students the office picked (e.g. bus users).
-- gateway_batch_id: one Cashfree order that pays several student fees
--   together, each fee getting its own payment row and receipt.
-- Applied automatically by the backend.

ALTER TABLE fee_items
    ADD COLUMN category VARCHAR(20) NOT NULL DEFAULT 'other' AFTER name,
    ADD COLUMN applies_to VARCHAR(10) NOT NULL DEFAULT 'class' AFTER category;

ALTER TABLE fee_payments
    ADD COLUMN gateway_batch_id VARCHAR(45) NULL AFTER gateway_order_id,
    ADD KEY idx_fee_payments_batch (gateway_batch_id);

-- 022: application fee for admissions. A school can set a fee (0 = none).
-- Parents pay it online with the school's own Cashfree account after applying,
-- or at the office, where the admin marks it paid.
-- fee_status: 'none' (no fee), 'pending', 'paid' or 'waived'.
-- fee_method: 'online' or 'office' once paid.
-- Applied automatically by the backend.

ALTER TABLE school_settings ADD COLUMN admission_fee DECIMAL(10,2) NOT NULL DEFAULT 0;

ALTER TABLE admission_applications
    ADD COLUMN fee_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    ADD COLUMN fee_status VARCHAR(10) NOT NULL DEFAULT 'none',
    ADD COLUMN fee_method VARCHAR(10) NOT NULL DEFAULT '',
    ADD COLUMN fee_order_id VARCHAR(45) NULL,
    ADD COLUMN fee_payment_ref VARCHAR(100) NOT NULL DEFAULT '',
    ADD COLUMN fee_paid_at TIMESTAMP NULL,
    ADD KEY idx_admission_applications_fee_order (fee_order_id);

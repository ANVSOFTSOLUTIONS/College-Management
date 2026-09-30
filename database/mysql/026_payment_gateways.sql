-- 026: schools can take online payments through Cashfree, Razorpay or
-- PhonePe, each with the school's own account.
-- schools.payment_gateways: the gateways the super admin allows the school
-- to choose from (a JSON list).
-- school_payment_settings.client_version: PhonePe's client version (only
-- PhonePe needs it).
-- fee_payments.gateway and admission_applications.fee_gateway: which
-- gateway took the payment. gateway_ref / fee_gateway_ref: that gateway's
-- own order id (Razorpay makes its own, the others use ours).
-- Applied automatically by the backend.

ALTER TABLE schools ADD COLUMN payment_gateways VARCHAR(100) NOT NULL DEFAULT '["cashfree", "razorpay", "phonepe"]';

ALTER TABLE school_payment_settings ADD COLUMN client_version VARCHAR(10) NOT NULL DEFAULT '' AFTER key_secret;

ALTER TABLE fee_payments
    ADD COLUMN gateway VARCHAR(20) NULL AFTER gateway_batch_id,
    ADD COLUMN gateway_ref VARCHAR(100) NULL AFTER gateway,
    ADD KEY idx_fee_payments_gateway_ref (gateway_ref);

ALTER TABLE admission_applications
    ADD COLUMN fee_gateway VARCHAR(20) NULL,
    ADD COLUMN fee_gateway_ref VARCHAR(100) NULL,
    ADD KEY idx_admission_applications_fee_gateway_ref (fee_gateway_ref);

UPDATE fee_payments SET gateway = 'cashfree', gateway_ref = COALESCE(gateway_batch_id, gateway_order_id)
WHERE method = 'online' AND gateway_order_id IS NOT NULL;

UPDATE admission_applications SET fee_gateway = 'cashfree', fee_gateway_ref = fee_order_id WHERE fee_order_id IS NOT NULL;

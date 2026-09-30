-- 019: online fee payment moves from Razorpay to Cashfree. Razorpay keys
-- don't work with Cashfree, so any saved ones are cleared and online payment
-- is switched off until the school enters its Cashfree App ID and secret key.
-- environment: 'production' (live money) or 'sandbox' (Cashfree test mode).
-- Applied automatically by the backend.

ALTER TABLE school_payment_settings ADD COLUMN environment VARCHAR(10) NOT NULL DEFAULT 'production' AFTER key_secret;

ALTER TABLE school_payment_settings ALTER COLUMN provider SET DEFAULT 'cashfree';

UPDATE school_payment_settings SET provider = 'cashfree', key_id = '', key_secret = '', enabled = 0
WHERE provider <> 'cashfree';

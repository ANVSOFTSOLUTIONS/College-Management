-- 027: a demo payment gateway for showing online fee payment without a real
-- gateway account. Its payment page is part of the app and no money moves.
-- The super admin switches it on per school (it is not on by default), and
-- the ANV Demo School gets it now, switched on, so demos work straight away.
-- demo_payment_orders: one row per demo order. status: 'pending', 'paid' or 'failed'.
-- Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS demo_payment_orders (
    ref        VARCHAR(64)   NOT NULL PRIMARY KEY,
    amount     DECIMAL(10,2) NOT NULL,
    status     VARCHAR(10)   NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

UPDATE schools SET payment_gateways = '["cashfree", "razorpay", "phonepe", "demo"]' WHERE code = 'ANVDEMO';

INSERT INTO school_payment_settings (school_id, provider, key_id, key_secret, environment, enabled)
SELECT id, 'demo', '', '', 'sandbox', 1 FROM schools WHERE code = 'ANVDEMO'
ON DUPLICATE KEY UPDATE provider = IF(school_payment_settings.enabled = 1, school_payment_settings.provider, 'demo'),
                        enabled = 1;

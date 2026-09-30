-- 020: Pro website templates, platform earnings, website customisation and
-- phone push notifications. Applied automatically by the backend.

-- Two templates are free. The other eight need Pro, which the super admin
-- switches on once the school has paid. A school keeps whatever template it
-- already uses.
ALTER TABLE schools ADD COLUMN pro_templates TINYINT(1) NOT NULL DEFAULT 0 AFTER template;

-- Money the platform receives from schools (recorded by the super admin).
CREATE TABLE IF NOT EXISTS platform_payments (
    id           CHAR(36)       NOT NULL PRIMARY KEY,
    school_id    CHAR(36)       NOT NULL,
    amount       DECIMAL(10,2)  NOT NULL,
    paid_on      DATE           NOT NULL,
    purpose      VARCHAR(20)    NOT NULL,
    method       VARCHAR(20)    NOT NULL DEFAULT 'bank',
    note         VARCHAR(200)   NOT NULL DEFAULT '',
    recorded_by  CHAR(36)       NULL,
    created_at   TIMESTAMP(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_platform_payments_paid_on (paid_on),
    KEY idx_platform_payments_school (school_id),
    CONSTRAINT fk_platform_payments_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_platform_payments_user FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_platform_payments_amount CHECK (amount > 0),
    CONSTRAINT chk_platform_payments_purpose CHECK (purpose IN ('subscription', 'pro_templates', 'setup', 'other'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- The school admin's own touches on top of the chosen template.
ALTER TABLE school_sites ADD COLUMN tagline VARCHAR(200) NOT NULL DEFAULT '';
ALTER TABLE school_sites ADD COLUMN primary_color CHAR(7) NULL;
ALTER TABLE school_sites ADD COLUMN accent_color CHAR(7) NULL;
ALTER TABLE school_sites ADD COLUMN hidden_sections VARCHAR(100) NOT NULL DEFAULT '';

-- Web Push: one row per browser/phone that allowed notifications.
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id          CHAR(36)      NOT NULL PRIMARY KEY,
    user_id     CHAR(36)      NOT NULL,
    endpoint    VARCHAR(700)  NOT NULL,
    endpoint_hash CHAR(64)    NOT NULL,
    p256dh      VARCHAR(200)  NOT NULL,
    auth        VARCHAR(100)  NOT NULL,
    user_agent  VARCHAR(200)  NOT NULL DEFAULT '',
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_push_subscriptions_endpoint (endpoint_hash),
    KEY idx_push_subscriptions_user (user_id),
    CONSTRAINT fk_push_subscriptions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- The platform's VAPID key pair for Web Push, made on first use.
ALTER TABLE platform_settings ADD COLUMN vapid_public_key VARCHAR(200) NOT NULL DEFAULT '';
ALTER TABLE platform_settings ADD COLUMN vapid_private_key VARCHAR(300) NOT NULL DEFAULT '';

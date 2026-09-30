-- 011: ten public-site templates, platform contact settings for the
-- marketing landing page, and demo requests (leads) from that page.
-- Applied automatically by the backend.

ALTER TABLE schools DROP CONSTRAINT chk_schools_template;
ALTER TABLE schools ADD CONSTRAINT chk_schools_template CHECK (template IN (
    'classic', 'modern', 'vibrant', 'emerald', 'royal', 'neon', 'sunrise', 'ocean', 'editorial', 'split'
));

-- Single-row contact details shown on the marketing landing page.
CREATE TABLE IF NOT EXISTS platform_settings (
    id                TINYINT      NOT NULL PRIMARY KEY DEFAULT 1,
    whatsapp_number   VARCHAR(20)  NOT NULL DEFAULT '',
    phone             VARCHAR(20)  NOT NULL DEFAULT '',
    email             VARCHAR(255) NOT NULL DEFAULT '',
    updated_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_platform_settings_single CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- "Book a demo" requests from the landing page, followed up by the super admin.
CREATE TABLE IF NOT EXISTS demo_requests (
    id           CHAR(36)     NOT NULL PRIMARY KEY,
    name         VARCHAR(150) NOT NULL,
    institution  VARCHAR(200) NOT NULL,
    phone        VARCHAR(20)  NOT NULL,
    email        VARCHAR(255) NOT NULL DEFAULT '',
    city         VARCHAR(100) NOT NULL DEFAULT '',
    students     VARCHAR(20)  NOT NULL DEFAULT '',
    message      VARCHAR(1000) NOT NULL DEFAULT '',
    status       VARCHAR(12)  NOT NULL DEFAULT 'new',
    notes        VARCHAR(1000) NOT NULL DEFAULT '',
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_demo_requests_status_created (status, created_at),
    CONSTRAINT chk_demo_requests_status CHECK (status IN ('new', 'contacted', 'converted', 'closed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

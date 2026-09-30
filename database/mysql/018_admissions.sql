-- 018: admissions. Parents apply online (no login) or the office records a
-- walk-in enquiry. The admin approves (which creates the student, with the
-- application's documents) or rejects with a reason.
-- Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS admission_applications (
    id               CHAR(36)      NOT NULL PRIMARY KEY,
    school_id        CHAR(36)      NOT NULL,
    application_no   VARCHAR(30)   NOT NULL,
    source           VARCHAR(10)   NOT NULL DEFAULT 'online',
    student_name     VARCHAR(200)  NOT NULL,
    date_of_birth    DATE          NULL,
    gender           VARCHAR(10)   NOT NULL DEFAULT '',
    class_applied    VARCHAR(50)   NOT NULL,
    previous_school  VARCHAR(200)  NOT NULL DEFAULT '',
    address          VARCHAR(500)  NOT NULL DEFAULT '',
    father_name      VARCHAR(200)  NOT NULL DEFAULT '',
    father_phone     VARCHAR(20)   NOT NULL DEFAULT '',
    mother_name      VARCHAR(200)  NOT NULL DEFAULT '',
    mother_phone     VARCHAR(20)   NOT NULL DEFAULT '',
    email            VARCHAR(255)  NOT NULL DEFAULT '',
    message          VARCHAR(1000) NOT NULL DEFAULT '',
    status           VARCHAR(10)   NOT NULL DEFAULT 'new',
    review_note      VARCHAR(300)  NOT NULL DEFAULT '',
    reviewed_by      CHAR(36)      NULL,
    reviewed_at      TIMESTAMP     NULL,
    student_id       CHAR(36)      NULL,
    upload_token     CHAR(64)      NULL,
    created_at       TIMESTAMP(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_admission_applications_no (school_id, application_no),
    KEY idx_admission_applications_school_status (school_id, status),
    CONSTRAINT fk_admission_applications_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_admission_applications_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL,
    CONSTRAINT fk_admission_applications_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_admission_applications_status CHECK (status IN ('new', 'approved', 'rejected')),
    CONSTRAINT chk_admission_applications_source CHECK (source IN ('online', 'office'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admission_documents (
    id              CHAR(36)      NOT NULL PRIMARY KEY,
    application_id  CHAR(36)      NOT NULL,
    doc_type        VARCHAR(30)   NOT NULL,
    file_path       VARCHAR(300)  NOT NULL,
    content_type    VARCHAR(100)  NOT NULL,
    size_bytes      INT           NOT NULL,
    original_name   VARCHAR(255)  NOT NULL DEFAULT '',
    created_at      TIMESTAMP(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_admission_documents_application (application_id),
    CONSTRAINT fk_admission_documents_application FOREIGN KEY (application_id) REFERENCES admission_applications(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admission_counters (
    school_id    CHAR(36)  NOT NULL,
    kind         VARCHAR(12) NOT NULL,  -- 'application' or 'admission'
    year         SMALLINT  NOT NULL,
    last_number  INT       NOT NULL DEFAULT 0,
    PRIMARY KEY (school_id, kind, year),
    CONSTRAINT fk_admission_counters_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE school_settings ADD COLUMN admissions_open TINYINT(1) NOT NULL DEFAULT 1;

-- Admissions is a new module: switch it on for existing schools like the others.
UPDATE schools SET enabled_modules = JSON_ARRAY_APPEND(enabled_modules, '$', 'admissions')
WHERE NOT JSON_CONTAINS(enabled_modules, '"admissions"');

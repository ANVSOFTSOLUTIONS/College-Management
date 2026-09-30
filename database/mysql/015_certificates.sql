-- 015: transfer and bonafide certificates. Each certificate keeps a snapshot
-- of what was printed (details JSON) so a reprint always matches the
-- original, and gets a serial number per school, kind and year.
-- Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS student_certificates (
    id            CHAR(36)     NOT NULL PRIMARY KEY,
    school_id     CHAR(36)     NOT NULL,
    student_id    CHAR(36)     NOT NULL,
    kind          VARCHAR(10)  NOT NULL,
    serial_no     VARCHAR(30)  NOT NULL,
    issued_on     DATE         NOT NULL,
    details       JSON         NOT NULL,
    issued_by     CHAR(36)     NULL,
    cancelled_at  TIMESTAMP    NULL,
    cancel_reason VARCHAR(200) NOT NULL DEFAULT '',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_student_certificates_serial (school_id, serial_no),
    KEY idx_student_certificates_student (student_id),
    CONSTRAINT fk_student_certificates_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_certificates_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_certificates_user FOREIGN KEY (issued_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_student_certificates_kind CHECK (kind IN ('tc', 'bonafide'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS certificate_counters (
    school_id    CHAR(36)     NOT NULL,
    kind         VARCHAR(10)  NOT NULL,
    year         SMALLINT     NOT NULL,
    last_number  INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (school_id, kind, year),
    CONSTRAINT fk_certificate_counters_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

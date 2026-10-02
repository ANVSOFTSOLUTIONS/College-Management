-- Social category (OC / BC-A ... / SC / ST / EWS) for AISHE and NAAC reports.
ALTER TABLE students ADD COLUMN social_category VARCHAR(10) NOT NULL DEFAULT '' AFTER quota;

-- Grievances raised by students, parents or faculty from the app; handled by the college office.
CREATE TABLE IF NOT EXISTS grievances (
    id                 CHAR(36)     NOT NULL PRIMARY KEY,
    school_id          CHAR(36)     NOT NULL,
    ticket_number      VARCHAR(20)  NOT NULL,
    raised_by_user_id  CHAR(36)     NOT NULL,
    student_id         CHAR(36)     NULL,
    category           VARCHAR(20)  NOT NULL,
    priority           VARCHAR(10)  NOT NULL DEFAULT 'normal',
    subject            VARCHAR(150) NOT NULL,
    description        TEXT         NOT NULL,
    status             VARCHAR(12)  NOT NULL DEFAULT 'open',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at        TIMESTAMP    NULL,
    UNIQUE KEY uq_grievances_ticket (school_id, ticket_number),
    KEY idx_grievances_raiser (raised_by_user_id),
    CONSTRAINT fk_grievances_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_grievances_user FOREIGN KEY (raised_by_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_grievances_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS grievance_replies (
    id              CHAR(36)   NOT NULL PRIMARY KEY,
    grievance_id    CHAR(36)   NOT NULL,
    author_user_id  CHAR(36)   NULL,
    from_office     TINYINT(1) NOT NULL,
    message         TEXT       NOT NULL,
    created_at      TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_grievance_replies_grievance FOREIGN KEY (grievance_id) REFERENCES grievances (id) ON DELETE CASCADE,
    CONSTRAINT fk_grievance_replies_user FOREIGN KEY (author_user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

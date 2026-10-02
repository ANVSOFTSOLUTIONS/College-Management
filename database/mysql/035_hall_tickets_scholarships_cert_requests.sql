-- Hall tickets: an exam can require minimum attendance and is released to the app when ready.
ALTER TABLE exams ADD COLUMN hall_ticket_min_attendance TINYINT NULL;
ALTER TABLE exams ADD COLUMN hall_tickets_released TINYINT(1) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS exam_rooms (
    id        CHAR(36)     NOT NULL PRIMARY KEY,
    exam_id   CHAR(36)     NOT NULL,
    name      VARCHAR(60)  NOT NULL,
    capacity  SMALLINT     NOT NULL,
    position  SMALLINT     NOT NULL,
    CONSTRAINT fk_exam_rooms_exam FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- The office can allow a short-attendance student (condonation) or hold back anyone.
CREATE TABLE IF NOT EXISTS hall_ticket_overrides (
    exam_id     CHAR(36)   NOT NULL,
    student_id  CHAR(36)   NOT NULL,
    allowed     TINYINT(1) NOT NULL,
    PRIMARY KEY (exam_id, student_id),
    CONSTRAINT fk_hall_ticket_overrides_exam FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE,
    CONSTRAINT fk_hall_ticket_overrides_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Government scholarships (e.g. Vidya Deevena, post-matric) tracked per student and year.
CREATE TABLE IF NOT EXISTS student_scholarships (
    id                 CHAR(36)      NOT NULL PRIMARY KEY,
    school_id          CHAR(36)      NOT NULL,
    student_id         CHAR(36)      NOT NULL,
    scheme             VARCHAR(100)  NOT NULL,
    academic_year      VARCHAR(9)    NOT NULL,
    application_no     VARCHAR(50)   NOT NULL DEFAULT '',
    amount_sanctioned  DECIMAL(10,2) NOT NULL DEFAULT 0,
    amount_received    DECIMAL(10,2) NOT NULL DEFAULT 0,
    status             VARCHAR(12)   NOT NULL DEFAULT 'applied',
    remarks            VARCHAR(300)  NOT NULL DEFAULT '',
    updated_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_student_scholarships (student_id, scheme, academic_year),
    CONSTRAINT fk_student_scholarships_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_student_scholarships_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Certificate requests from the app; the office issues the certificate on approval.
CREATE TABLE IF NOT EXISTS certificate_requests (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    school_id       CHAR(36)     NOT NULL,
    student_id      CHAR(36)     NOT NULL,
    requested_by    CHAR(36)     NOT NULL,
    kind            VARCHAR(10)  NOT NULL,
    purpose         VARCHAR(200) NOT NULL,
    status          VARCHAR(10)  NOT NULL DEFAULT 'pending',
    note            VARCHAR(300) NOT NULL DEFAULT '',
    certificate_id  CHAR(36)     NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at      TIMESTAMP    NULL,
    KEY idx_certificate_requests_student (student_id),
    CONSTRAINT fk_certificate_requests_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_certificate_requests_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
    CONSTRAINT fk_certificate_requests_user FOREIGN KEY (requested_by) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_certificate_requests_certificate FOREIGN KEY (certificate_id) REFERENCES student_certificates (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

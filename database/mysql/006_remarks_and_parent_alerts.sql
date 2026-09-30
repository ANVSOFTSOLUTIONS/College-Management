-- 006: teacher remarks on students, and the parent alert log (SMS).
-- Applied automatically by the backend (see database/README.md).

-- A note a teacher records about a student: missed an exam, absent from a
-- period, homework, behaviour, appreciation.
CREATE TABLE IF NOT EXISTS student_remarks (
    id             CHAR(36)     NOT NULL PRIMARY KEY,
    school_id      CHAR(36)     NOT NULL,
    student_id     CHAR(36)     NOT NULL,
    class_id       CHAR(36)     NOT NULL,
    subject_id     CHAR(36)     NULL,
    author_id      CHAR(36)     NULL,
    category       VARCHAR(20)  NOT NULL,
    note           VARCHAR(500) NOT NULL DEFAULT '',
    remark_date    DATE         NOT NULL,
    notify_parent  TINYINT(1)   NOT NULL DEFAULT 0,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_student_remarks_class_date (class_id, remark_date),
    KEY idx_student_remarks_student (student_id),
    KEY idx_student_remarks_author (author_id),
    CONSTRAINT fk_student_remarks_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_remarks_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_remarks_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_remarks_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    CONSTRAINT fk_student_remarks_author FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_student_remarks_category CHECK (category IN ('missed_exam', 'absent_class', 'homework', 'behaviour', 'appreciation', 'other'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Every alert meant for a parent, whether or not it could be sent. dedupe_key
-- stops the same event (e.g. one absence) alerting twice.
CREATE TABLE IF NOT EXISTS parent_alerts (
    id                   CHAR(36)     NOT NULL PRIMARY KEY,
    school_id            CHAR(36)     NOT NULL,
    student_id           CHAR(36)     NOT NULL,
    class_id             CHAR(36)     NOT NULL,
    kind                 VARCHAR(20)  NOT NULL,
    dedupe_key           VARCHAR(120) NOT NULL,
    recipient_name       VARCHAR(200) NOT NULL DEFAULT '',
    recipient_phone      VARCHAR(20)  NOT NULL DEFAULT '',
    message              VARCHAR(500) NOT NULL,
    status               VARCHAR(10)  NOT NULL,
    status_detail        VARCHAR(300) NOT NULL DEFAULT '',
    provider_message_id  VARCHAR(100) NOT NULL DEFAULT '',
    created_by           CHAR(36)     NULL,
    created_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at              TIMESTAMP    NULL,
    UNIQUE KEY uq_parent_alerts_dedupe (school_id, dedupe_key),
    KEY idx_parent_alerts_class_created (class_id, created_at),
    KEY idx_parent_alerts_student (student_id),
    CONSTRAINT fk_parent_alerts_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_parent_alerts_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_parent_alerts_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_parent_alerts_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_parent_alerts_kind CHECK (kind IN ('absence', 'remark')),
    CONSTRAINT chk_parent_alerts_status CHECK (status IN ('sent', 'failed', 'not_sent'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

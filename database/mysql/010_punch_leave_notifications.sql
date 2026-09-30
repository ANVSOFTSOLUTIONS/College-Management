-- 010: staff punch in/out, leave requests (teachers and students), and
-- in-app notifications. Applied automatically by the backend.

-- Per-school settings; a punch after day_starts_at + late_grace_minutes is late.
CREATE TABLE IF NOT EXISTS school_settings (
    school_id           CHAR(36)  NOT NULL PRIMARY KEY,
    day_starts_at       TIME      NOT NULL DEFAULT '09:00:00',
    late_grace_minutes  INT       NOT NULL DEFAULT 15,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_school_settings_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT chk_school_settings_grace CHECK (late_grace_minutes BETWEEN 0 AND 240)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- One row per teacher per (IST) day. Times are stored in UTC.
CREATE TABLE IF NOT EXISTS staff_punches (
    id            CHAR(36)    NOT NULL PRIMARY KEY,
    school_id     CHAR(36)    NOT NULL,
    teacher_id    CHAR(36)    NOT NULL,
    punch_date    DATE        NOT NULL,
    punch_in_at   DATETIME    NOT NULL,
    punch_out_at  DATETIME    NULL,
    is_late       TINYINT(1)  NOT NULL DEFAULT 0,
    UNIQUE KEY uq_staff_punches_teacher_date (teacher_id, punch_date),
    KEY idx_staff_punches_school_date (school_id, punch_date),
    CONSTRAINT fk_staff_punches_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_staff_punches_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A leave request by a teacher (reviewed by an admin) or a student (reviewed
-- by their class teacher or an admin).
CREATE TABLE IF NOT EXISTS leave_requests (
    id                 CHAR(36)     NOT NULL PRIMARY KEY,
    school_id          CHAR(36)     NOT NULL,
    applicant_user_id  CHAR(36)     NOT NULL,
    teacher_id         CHAR(36)     NULL,
    student_id         CHAR(36)     NULL,
    class_id           CHAR(36)     NULL,
    leave_type         VARCHAR(20)  NOT NULL,
    from_date          DATE         NOT NULL,
    to_date            DATE         NOT NULL,
    reason             VARCHAR(500) NOT NULL,
    status             VARCHAR(10)  NOT NULL DEFAULT 'pending',
    reviewer_id        CHAR(36)     NULL,
    review_note        VARCHAR(300) NOT NULL DEFAULT '',
    reviewed_at        TIMESTAMP    NULL,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_leave_requests_school_status (school_id, status),
    KEY idx_leave_requests_class (class_id),
    KEY idx_leave_requests_applicant (applicant_user_id),
    CONSTRAINT fk_leave_requests_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_leave_requests_applicant FOREIGN KEY (applicant_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_leave_requests_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    CONSTRAINT fk_leave_requests_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_leave_requests_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL,
    CONSTRAINT fk_leave_requests_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_leave_requests_type CHECK (leave_type IN ('sick', 'casual', 'family', 'other')),
    CONSTRAINT chk_leave_requests_status CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    CONSTRAINT chk_leave_requests_dates CHECK (to_date >= from_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- In-app notifications (the bell). `link` is the app section to open.
CREATE TABLE IF NOT EXISTS notifications (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NULL,
    user_id     CHAR(36)     NOT NULL,
    title       VARCHAR(200) NOT NULL,
    body        VARCHAR(500) NOT NULL DEFAULT '',
    link        VARCHAR(50)  NOT NULL DEFAULT '',
    read_at     TIMESTAMP    NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_notifications_user_created (user_id, created_at),
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_notifications_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

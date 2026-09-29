-- 002: teacher (staff) attendance, kept separate from student attendance.
-- Apply after schema.sql. Safe to run more than once (IF NOT EXISTS).
-- cPanel: phpMyAdmin → select the database → Import → this file.

CREATE TABLE IF NOT EXISTS staff_attendance (
    id               CHAR(36)    NOT NULL PRIMARY KEY,
    school_id        CHAR(36)    NOT NULL,
    teacher_id       CHAR(36)    NOT NULL,
    attendance_date  DATE        NOT NULL,
    status           VARCHAR(10) NOT NULL,
    marked_by        CHAR(36)    NOT NULL,
    marked_at        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_staff_attendance_teacher_date (teacher_id, attendance_date),
    KEY idx_staff_attendance_school_date (school_id, attendance_date),
    CONSTRAINT fk_staff_attendance_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_staff_attendance_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    CONSTRAINT fk_staff_attendance_marked_by FOREIGN KEY (marked_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_staff_attendance_status CHECK (status IN ('present', 'absent', 'late', 'leave'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

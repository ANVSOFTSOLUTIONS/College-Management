-- 003: teacher profile details, subjects, and subject-teacher assignments.
-- Apply once, after 002_staff_attendance.sql. The ALTER TABLE is not
-- re-runnable (MySQL has no ADD COLUMN IF NOT EXISTS); the CREATE TABLEs are.
-- cPanel: phpMyAdmin → select the database → Import → this file.

ALTER TABLE teachers
    ADD COLUMN employee_code  VARCHAR(30)  NULL AFTER department,
    ADD COLUMN phone          VARCHAR(20)  NOT NULL DEFAULT '' AFTER employee_code,
    ADD COLUMN qualification  VARCHAR(200) NOT NULL DEFAULT '' AFTER phone,
    ADD COLUMN joined_on      DATE         NULL AFTER qualification,
    ADD UNIQUE KEY uq_teachers_school_employee_code (school_id, employee_code);

-- A school's subject catalogue (Maths, Telugu, ...).
CREATE TABLE IF NOT EXISTS subjects (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(20)  NOT NULL DEFAULT '',
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_subjects_school_name (school_id, name),
    CONSTRAINT fk_subjects_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Who teaches which subject in which class/section. The class teacher stays
-- on classes.teacher_id; this table is the subject teachers.
CREATE TABLE IF NOT EXISTS class_subjects (
    id          CHAR(36)   NOT NULL PRIMARY KEY,
    school_id   CHAR(36)   NOT NULL,
    class_id    CHAR(36)   NOT NULL,
    subject_id  CHAR(36)   NOT NULL,
    teacher_id  CHAR(36)   NOT NULL,
    created_at  TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_class_subjects_class_subject (class_id, subject_id),
    KEY idx_class_subjects_teacher (teacher_id),
    CONSTRAINT fk_class_subjects_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_class_subjects_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_class_subjects_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_class_subjects_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 028: college structure. Departments (with a head of department), and
-- classes become batches: a department, a program (B.Tech, B.Sc, MBA ...),
-- a semester and a regulation. Subjects get credits and a type (theory, lab,
-- project, elective) for SGPA / CGPA. Faculty get a designation.
-- College students sign in again (with the college code and their roll
-- number), so their accounts are no longer switched off by default.
-- Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS departments (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    school_id       CHAR(36)     NOT NULL,
    name            VARCHAR(150) NOT NULL,
    code            VARCHAR(20)  NOT NULL,
    hod_teacher_id  CHAR(36)     NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_departments_code (school_id, code),
    CONSTRAINT fk_departments_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_departments_hod FOREIGN KEY (hod_teacher_id) REFERENCES teachers (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE classes ADD COLUMN department_id CHAR(36) NULL AFTER teacher_id;
ALTER TABLE classes ADD COLUMN program VARCHAR(60) NOT NULL DEFAULT '' AFTER department_id;
ALTER TABLE classes ADD COLUMN semester TINYINT NULL AFTER section;
ALTER TABLE classes ADD COLUMN regulation VARCHAR(20) NOT NULL DEFAULT '' AFTER semester;
ALTER TABLE classes ADD CONSTRAINT fk_classes_department FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL;

ALTER TABLE subjects ADD COLUMN credits DECIMAL(3,1) NOT NULL DEFAULT 3.0 AFTER code;
ALTER TABLE subjects ADD COLUMN subject_type VARCHAR(12) NOT NULL DEFAULT 'theory' AFTER credits;
ALTER TABLE subjects ADD COLUMN department_id CHAR(36) NULL AFTER subject_type;
ALTER TABLE subjects ADD COLUMN semester TINYINT NULL AFTER department_id;
ALTER TABLE subjects ADD CONSTRAINT fk_subjects_department FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL;

ALTER TABLE teachers ADD COLUMN designation VARCHAR(60) NOT NULL DEFAULT '' AFTER department;
ALTER TABLE teachers ADD COLUMN department_id CHAR(36) NULL AFTER designation;
ALTER TABLE teachers ADD CONSTRAINT fk_teachers_department FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL;

ALTER TABLE students ADD COLUMN email VARCHAR(255) NULL AFTER full_name;
ALTER TABLE students ADD COLUMN phone VARCHAR(15) NULL AFTER email;
ALTER TABLE students ADD COLUMN quota VARCHAR(20) NOT NULL DEFAULT '' AFTER phone;

-- Exam type: 'internal' (mid exams, assignments) or 'semester' (semester-end).
-- Only semester-end exams count towards CGPA.
ALTER TABLE exams ADD COLUMN exam_type VARCHAR(10) NOT NULL DEFAULT 'semester' AFTER term_label;

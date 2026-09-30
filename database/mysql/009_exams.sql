-- 009: exams, the subjects each class sits in an exam, and marks.
-- Applied automatically by the backend (see database/README.md).

-- An exam (Unit Test 1, Quarterly, Half-yearly...). Students and parents see
-- results only once it is published; marks are locked while published.
CREATE TABLE IF NOT EXISTS exams (
    id             CHAR(36)     NOT NULL PRIMARY KEY,
    school_id      CHAR(36)     NOT NULL,
    name           VARCHAR(150) NOT NULL,
    term_label     VARCHAR(50)  NOT NULL DEFAULT '',
    academic_year  VARCHAR(9)   NOT NULL,
    start_date     DATE         NULL,
    end_date       DATE         NULL,
    published_at   TIMESTAMP    NULL,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_exams_school_year (school_id, academic_year),
    CONSTRAINT fk_exams_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- One paper: a subject a class sits in an exam, with its maximum and pass marks.
CREATE TABLE IF NOT EXISTS exam_subjects (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    exam_id     CHAR(36)     NOT NULL,
    class_id    CHAR(36)     NOT NULL,
    subject_id  CHAR(36)     NOT NULL,
    max_marks   DECIMAL(6,2) NOT NULL,
    pass_marks  DECIMAL(6,2) NOT NULL,
    exam_date   DATE         NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_exam_subjects_paper (exam_id, class_id, subject_id),
    KEY idx_exam_subjects_class (class_id),
    CONSTRAINT fk_exam_subjects_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_exam_subjects_exam FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    CONSTRAINT fk_exam_subjects_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_exam_subjects_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT chk_exam_subjects_marks CHECK (max_marks > 0 AND pass_marks >= 0 AND pass_marks <= max_marks)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A student's result in one paper: marks, or absent.
CREATE TABLE IF NOT EXISTS exam_marks (
    id               CHAR(36)     NOT NULL PRIMARY KEY,
    school_id        CHAR(36)     NOT NULL,
    exam_subject_id  CHAR(36)     NOT NULL,
    student_id       CHAR(36)     NOT NULL,
    marks            DECIMAL(6,2) NULL,
    is_absent        TINYINT(1)   NOT NULL DEFAULT 0,
    entered_by       CHAR(36)     NULL,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_exam_marks_paper_student (exam_subject_id, student_id),
    KEY idx_exam_marks_student (student_id),
    CONSTRAINT fk_exam_marks_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_exam_marks_paper FOREIGN KEY (exam_subject_id) REFERENCES exam_subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_exam_marks_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_exam_marks_entered_by FOREIGN KEY (entered_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_exam_marks_value CHECK ((is_absent = 1 AND marks IS NULL) OR (is_absent = 0 AND marks >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

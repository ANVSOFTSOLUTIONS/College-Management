-- 032: internal + external marks, supplementary exams, subject-wise attendance.
-- A semester-end exam can take internal marks from internal exams (mid exams):
-- internal_exam_ids is a JSON list of those exams, internal_weight the share of
-- the 100 marks they carry (e.g. 30, leaving 70 for the semester-end paper).
-- exam_type gains 'supplementary': re-exams for students with backlogs, whose
-- result replaces the failed grade in CGPA.
-- subject_attendance: attendance per subject and period, marked by the subject's
-- faculty; one row per student, subject, date and period.
-- Applied automatically by the backend.

ALTER TABLE exams MODIFY COLUMN exam_type VARCHAR(15) NOT NULL DEFAULT 'semester';
ALTER TABLE exams ADD COLUMN internal_exam_ids LONGTEXT NULL AFTER exam_type;
ALTER TABLE exams ADD COLUMN internal_weight TINYINT NOT NULL DEFAULT 0 AFTER internal_exam_ids;

CREATE TABLE IF NOT EXISTS subject_attendance (
    id               CHAR(36)    NOT NULL PRIMARY KEY,
    school_id        CHAR(36)    NOT NULL,
    class_id         CHAR(36)    NOT NULL,
    subject_id       CHAR(36)    NOT NULL,
    student_id       CHAR(36)    NOT NULL,
    attendance_date  DATE        NOT NULL,
    period           TINYINT     NOT NULL DEFAULT 1,
    status           VARCHAR(10) NOT NULL,
    marked_by        CHAR(36)    NULL,
    marked_at        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_subject_attendance (student_id, subject_id, attendance_date, period),
    KEY ix_subject_attendance_class (class_id, subject_id, attendance_date),
    CONSTRAINT fk_subj_att_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_subj_att_class FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE,
    CONSTRAINT fk_subj_att_subject FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
    CONSTRAINT fk_subj_att_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

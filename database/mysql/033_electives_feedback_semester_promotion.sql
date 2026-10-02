-- Electives: a batch's elective slot (e.g. "Professional Elective I") offers
-- several subjects with limited seats; each student picks one per slot.
CREATE TABLE IF NOT EXISTS elective_groups (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    class_id    CHAR(36)     NOT NULL,
    name        VARCHAR(100) NOT NULL,
    is_open     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_elective_groups_name (class_id, name),
    CONSTRAINT fk_elective_groups_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_elective_groups_class FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS elective_options (
    id          CHAR(36)  NOT NULL PRIMARY KEY,
    group_id    CHAR(36)  NOT NULL,
    subject_id  CHAR(36)  NOT NULL,
    seats       SMALLINT  NOT NULL,
    UNIQUE KEY uq_elective_options_subject (group_id, subject_id),
    CONSTRAINT fk_elective_options_group FOREIGN KEY (group_id) REFERENCES elective_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_elective_options_subject FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS elective_choices (
    id          CHAR(36)   NOT NULL PRIMARY KEY,
    group_id    CHAR(36)   NOT NULL,
    option_id   CHAR(36)   NOT NULL,
    student_id  CHAR(36)   NOT NULL,
    chosen_at   TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_elective_choices_student (group_id, student_id),
    CONSTRAINT fk_elective_choices_group FOREIGN KEY (group_id) REFERENCES elective_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_elective_choices_option FOREIGN KEY (option_id) REFERENCES elective_options (id) ON DELETE CASCADE,
    CONSTRAINT fk_elective_choices_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Faculty feedback: anonymous. A response stores a hash of (round, student,
-- subject) so a student answers once, but never the student's id.
CREATE TABLE IF NOT EXISTS feedback_rounds (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    title       VARCHAR(150) NOT NULL,
    is_open     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_feedback_rounds_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS feedback_responses (
    id            CHAR(36)   NOT NULL PRIMARY KEY,
    round_id      CHAR(36)   NOT NULL,
    class_id      CHAR(36)   NOT NULL,
    subject_id    CHAR(36)   NOT NULL,
    teacher_id    CHAR(36)   NOT NULL,
    student_hash  CHAR(64)   NOT NULL,
    ratings       VARCHAR(40) NOT NULL,
    comment       TEXT       NULL,
    created_at    TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_feedback_responses_once (round_id, student_hash),
    KEY idx_feedback_responses_teacher (teacher_id),
    CONSTRAINT fk_feedback_responses_round FOREIGN KEY (round_id) REFERENCES feedback_rounds (id) ON DELETE CASCADE,
    CONSTRAINT fk_feedback_responses_class FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE,
    CONSTRAINT fk_feedback_responses_subject FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
    CONSTRAINT fk_feedback_responses_teacher FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Semester promotion: a batch moves to its next semester in place.
CREATE TABLE IF NOT EXISTS semester_promotions (
    id             CHAR(36)   NOT NULL PRIMARY KEY,
    school_id      CHAR(36)   NOT NULL,
    class_id       CHAR(36)   NOT NULL,
    from_semester  TINYINT    NOT NULL,
    to_semester    TINYINT    NULL,
    summary        LONGTEXT   NOT NULL,
    run_by         CHAR(36)   NULL,
    created_at     TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_semester_promotions_once (class_id, from_semester),
    CONSTRAINT fk_semester_promotions_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_semester_promotions_class FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

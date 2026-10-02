-- Lesson plan: a subject's syllabus topics for a batch, ticked off as they are taught.
CREATE TABLE IF NOT EXISTS lesson_topics (
    id            CHAR(36)     NOT NULL PRIMARY KEY,
    school_id     CHAR(36)     NOT NULL,
    class_id      CHAR(36)     NOT NULL,
    subject_id    CHAR(36)     NOT NULL,
    unit          TINYINT      NOT NULL DEFAULT 1,
    title         VARCHAR(200) NOT NULL,
    planned_date  DATE         NULL,
    completed_on  DATE         NULL,
    completed_by  CHAR(36)     NULL,
    position      SMALLINT     NOT NULL DEFAULT 0,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_lesson_topics_class_subject (class_id, subject_id),
    CONSTRAINT fk_lesson_topics_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_lesson_topics_class FOREIGN KEY (class_id) REFERENCES classes (id) ON DELETE CASCADE,
    CONSTRAINT fk_lesson_topics_subject FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
    CONSTRAINT fk_lesson_topics_user FOREIGN KEY (completed_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Question bank: previous and model question papers per subject, shown to students in the app.
CREATE TABLE IF NOT EXISTS question_papers (
    id               CHAR(36)     NOT NULL PRIMARY KEY,
    school_id        CHAR(36)     NOT NULL,
    subject_id       CHAR(36)     NOT NULL,
    title            VARCHAR(150) NOT NULL,
    exam_year        VARCHAR(9)   NOT NULL DEFAULT '',
    regulation       VARCHAR(20)  NOT NULL DEFAULT '',
    attachment_path  VARCHAR(300) NOT NULL,
    attachment_name  VARCHAR(150) NOT NULL,
    attachment_type  VARCHAR(100) NOT NULL,
    uploaded_by      CHAR(36)     NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_question_papers_subject (subject_id),
    CONSTRAINT fk_question_papers_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_question_papers_subject FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
    CONSTRAINT fk_question_papers_user FOREIGN KEY (uploaded_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Alumni: passed-out students and where they are now (NAAC criterion 5.4).
CREATE TABLE IF NOT EXISTS alumni (
    id               CHAR(36)     NOT NULL PRIMARY KEY,
    school_id        CHAR(36)     NOT NULL,
    student_id       CHAR(36)     NULL,
    full_name        VARCHAR(200) NOT NULL,
    admission_number VARCHAR(50)  NOT NULL DEFAULT '',
    passing_year     VARCHAR(9)   NOT NULL,
    program          VARCHAR(100) NOT NULL DEFAULT '',
    email            VARCHAR(255) NOT NULL DEFAULT '',
    phone            VARCHAR(15)  NOT NULL DEFAULT '',
    status           VARCHAR(16)  NOT NULL DEFAULT 'unknown',
    organisation     VARCHAR(150) NOT NULL DEFAULT '',
    designation      VARCHAR(100) NOT NULL DEFAULT '',
    location         VARCHAR(100) NOT NULL DEFAULT '',
    notes            VARCHAR(300) NOT NULL DEFAULT '',
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_alumni_student (student_id),
    KEY idx_alumni_year (school_id, passing_year),
    CONSTRAINT fk_alumni_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_alumni_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

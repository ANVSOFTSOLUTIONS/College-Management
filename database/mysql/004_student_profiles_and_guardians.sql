-- 004: student profile details and parents/guardian contacts.
-- Applied automatically by the backend (see database/README.md).

ALTER TABLE students
    ADD COLUMN date_of_birth    DATE         NULL AFTER full_name,
    ADD COLUMN gender           VARCHAR(10)  NOT NULL DEFAULT '' AFTER date_of_birth,
    ADD COLUMN blood_group      VARCHAR(5)   NOT NULL DEFAULT '' AFTER gender,
    ADD COLUMN admission_date   DATE         NULL AFTER blood_group,
    ADD COLUMN address          VARCHAR(500) NOT NULL DEFAULT '' AFTER admission_date,
    ADD COLUMN primary_contact  VARCHAR(10)  NOT NULL DEFAULT '' AFTER parent_name,
    ADD COLUMN status           VARCHAR(10)  NOT NULL DEFAULT 'active' AFTER primary_contact;

-- One row per parent/guardian (relation father, mother, or guardian).
-- students.parent_name is kept, filled with the primary contact's name, for
-- older API responses.
CREATE TABLE IF NOT EXISTS student_guardians (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    school_id       CHAR(36)     NOT NULL,
    student_id      CHAR(36)     NOT NULL,
    relation        VARCHAR(10)  NOT NULL,
    relation_label  VARCHAR(50)  NOT NULL DEFAULT '',
    full_name       VARCHAR(200) NOT NULL,
    phone           VARCHAR(20)  NOT NULL DEFAULT '',
    email           VARCHAR(255) NOT NULL DEFAULT '',
    occupation      VARCHAR(100) NOT NULL DEFAULT '',
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_student_guardians_student_relation (student_id, relation),
    KEY idx_student_guardians_phone (school_id, phone),
    CONSTRAINT fk_student_guardians_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_guardians_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

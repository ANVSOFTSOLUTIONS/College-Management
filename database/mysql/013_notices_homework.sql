-- 013: in-app notice board and homework. Attachments live in private storage
-- and are streamed only to people who can see the notice/homework.
-- Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS notices (
    id               CHAR(36)     NOT NULL PRIMARY KEY,
    school_id        CHAR(36)     NOT NULL,
    title            VARCHAR(150) NOT NULL,
    body             TEXT         NOT NULL,
    for_staff        TINYINT(1)   NOT NULL DEFAULT 0,
    for_students     TINYINT(1)   NOT NULL DEFAULT 1,
    for_parents      TINYINT(1)   NOT NULL DEFAULT 1,
    is_pinned        TINYINT(1)   NOT NULL DEFAULT 0,
    expires_on       DATE         NULL,
    attachment_path  VARCHAR(255) NULL,
    attachment_name  VARCHAR(150) NULL,
    attachment_type  VARCHAR(50)  NULL,
    posted_by        CHAR(36)     NULL,
    created_at       TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_notices_school_created (school_id, created_at),
    CONSTRAINT fk_notices_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_notices_user FOREIGN KEY (posted_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A notice with no rows here is for the whole school.
CREATE TABLE IF NOT EXISTS notice_classes (
    notice_id  CHAR(36)  NOT NULL,
    class_id   CHAR(36)  NOT NULL,
    PRIMARY KEY (notice_id, class_id),
    KEY idx_notice_classes_class (class_id),
    CONSTRAINT fk_notice_classes_notice FOREIGN KEY (notice_id) REFERENCES notices(id) ON DELETE CASCADE,
    CONSTRAINT fk_notice_classes_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS homework (
    id               CHAR(36)     NOT NULL PRIMARY KEY,
    school_id        CHAR(36)     NOT NULL,
    class_id         CHAR(36)     NOT NULL,
    subject_id       CHAR(36)     NOT NULL,
    title            VARCHAR(150) NOT NULL,
    details          TEXT         NOT NULL,
    assigned_on      DATE         NOT NULL,
    due_on           DATE         NOT NULL,
    attachment_path  VARCHAR(255) NULL,
    attachment_name  VARCHAR(150) NULL,
    attachment_type  VARCHAR(50)  NULL,
    posted_by        CHAR(36)     NULL,
    created_at       TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_homework_class_due (class_id, due_on),
    KEY idx_homework_school (school_id),
    CONSTRAINT fk_homework_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_homework_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_homework_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_homework_user FOREIGN KEY (posted_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

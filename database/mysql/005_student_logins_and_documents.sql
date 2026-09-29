-- 005: student logins (admission number + school code), student photo, and
-- student documents with review status. Also allows the 'student' and
-- 'parent' roles. Applied automatically by the backend (see database/README.md).
-- One change per ALTER so each is skipped cleanly if it already exists.

-- Students log in with a login_id (school code + admission number), not an email.
ALTER TABLE users MODIFY email VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN login_id VARCHAR(120) NULL AFTER email;
ALTER TABLE users ADD UNIQUE KEY uq_users_login_id (login_id);
ALTER TABLE users ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0 AFTER password_hash;
ALTER TABLE users DROP CONSTRAINT chk_users_role;
ALTER TABLE users ADD CONSTRAINT chk_users_role CHECK (role IN ('super_admin', 'admin', 'teacher', 'student', 'parent'));

ALTER TABLE students ADD COLUMN user_id CHAR(36) NULL AFTER class_id;
ALTER TABLE students ADD UNIQUE KEY uq_students_user (user_id);
ALTER TABLE students ADD CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE students ADD COLUMN photo_path VARCHAR(300) NULL AFTER address;

-- Files live outside the public uploads folder and are served only to the
-- student, their class teacher, and admins.
CREATE TABLE IF NOT EXISTS student_documents (
    id             CHAR(36)     NOT NULL PRIMARY KEY,
    school_id      CHAR(36)     NOT NULL,
    student_id     CHAR(36)     NOT NULL,
    doc_type       VARCHAR(30)  NOT NULL,
    title          VARCHAR(200) NOT NULL DEFAULT '',
    file_path      VARCHAR(300) NOT NULL,
    content_type   VARCHAR(100) NOT NULL,
    size_bytes     INT          NOT NULL,
    original_name  VARCHAR(255) NOT NULL DEFAULT '',
    status         VARCHAR(10)  NOT NULL DEFAULT 'pending',
    review_note    VARCHAR(300) NOT NULL DEFAULT '',
    uploaded_by    CHAR(36)     NULL,
    reviewed_by    CHAR(36)     NULL,
    reviewed_at    TIMESTAMP    NULL,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_student_documents_student (student_id),
    KEY idx_student_documents_school_status (school_id, status),
    CONSTRAINT fk_student_documents_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_documents_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_documents_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_student_documents_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_student_documents_status CHECK (status IN ('pending', 'approved', 'rejected'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

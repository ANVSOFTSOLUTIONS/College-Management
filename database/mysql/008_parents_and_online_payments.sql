-- 008: parent accounts linked to their children, and per-school online
-- payment (Razorpay) settings — money goes to the school's own account.
-- Applied automatically by the backend (see database/README.md).

-- A parent signs in with their mobile number and sees every child linked here,
-- even across schools, so parent users have no school_id of their own.
CREATE TABLE IF NOT EXISTS parent_students (
    parent_user_id  CHAR(36)   NOT NULL,
    student_id      CHAR(36)   NOT NULL,
    school_id       CHAR(36)   NOT NULL,
    created_at      TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (parent_user_id, student_id),
    KEY idx_parent_students_student (student_id),
    CONSTRAINT fk_parent_students_parent FOREIGN KEY (parent_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_parent_students_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_parent_students_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Off until the school connects its own Razorpay account.
CREATE TABLE IF NOT EXISTS school_payment_settings (
    school_id    CHAR(36)     NOT NULL PRIMARY KEY,
    provider     VARCHAR(20)  NOT NULL DEFAULT 'razorpay',
    key_id       VARCHAR(100) NOT NULL DEFAULT '',
    key_secret   VARCHAR(200) NOT NULL DEFAULT '',
    enabled      TINYINT(1)   NOT NULL DEFAULT 0,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_school_payment_settings_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

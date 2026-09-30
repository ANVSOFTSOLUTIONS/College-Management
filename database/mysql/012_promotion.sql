-- 012: year-end promotion. Last year's classes are archived (kept for
-- history, hidden from daily lists) and each promotion run is recorded so a
-- year can't be promoted twice. Applied automatically by the backend.

ALTER TABLE classes ADD COLUMN is_archived TINYINT(1) NOT NULL DEFAULT 0 AFTER academic_year;

CREATE TABLE IF NOT EXISTS promotion_runs (
    id          CHAR(36)    NOT NULL PRIMARY KEY,
    school_id   CHAR(36)    NOT NULL,
    from_year   VARCHAR(9)  NOT NULL,
    to_year     VARCHAR(9)  NOT NULL,
    summary     JSON        NOT NULL,
    run_by      CHAR(36)    NULL,
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_promotion_runs_school_from (school_id, from_year),
    CONSTRAINT fk_promotion_runs_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_promotion_runs_user FOREIGN KEY (run_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 021: audit log. Who changed what, and when, for actions that matter when
-- there is a dispute: marks, fee payments, attendance edits, certificates,
-- salaries, admissions and school settings. Rows are only ever added.
-- Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS audit_log (
    id           CHAR(36)      NOT NULL PRIMARY KEY,
    school_id    CHAR(36)      NULL,
    user_id      CHAR(36)      NULL,
    user_name    VARCHAR(200)  NOT NULL DEFAULT '',
    user_role    VARCHAR(20)   NOT NULL DEFAULT '',
    action       VARCHAR(40)   NOT NULL,
    entity_type  VARCHAR(30)   NOT NULL DEFAULT '',
    entity_id    CHAR(36)      NULL,
    summary      VARCHAR(500)  NOT NULL,
    details      JSON          NULL,
    created_at   TIMESTAMP(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_audit_log_school_created (school_id, created_at),
    KEY idx_audit_log_entity (entity_type, entity_id),
    CONSTRAINT fk_audit_log_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_audit_log_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

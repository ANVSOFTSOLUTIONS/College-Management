-- 014: timetable (school-wide periods + a weekly grid per class) and the
-- holiday/event calendar. A timetable cell stores the subject; its teacher is
-- whoever teaches that subject in the class (class_subjects), so changing a
-- subject teacher updates every timetable. Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS school_periods (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    position    SMALLINT     NOT NULL,
    label       VARCHAR(30)  NOT NULL,
    start_time  TIME         NOT NULL,
    end_time    TIME         NOT NULL,
    is_break    TINYINT(1)   NOT NULL DEFAULT 0,
    KEY idx_school_periods_school (school_id, position),
    CONSTRAINT fk_school_periods_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS timetable_entries (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    class_id    CHAR(36)     NOT NULL,
    weekday     TINYINT      NOT NULL,   -- 0 Monday … 5 Saturday
    period_id   CHAR(36)     NOT NULL,
    subject_id  CHAR(36)     NOT NULL,
    UNIQUE KEY uq_timetable_class_slot (class_id, weekday, period_id),
    KEY idx_timetable_school_slot (school_id, weekday, period_id),
    CONSTRAINT fk_timetable_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_timetable_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_timetable_period FOREIGN KEY (period_id) REFERENCES school_periods(id) ON DELETE CASCADE,
    CONSTRAINT fk_timetable_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT chk_timetable_weekday CHECK (weekday BETWEEN 0 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS school_holidays (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    title       VARCHAR(120) NOT NULL,
    kind        VARCHAR(10)  NOT NULL DEFAULT 'holiday',
    start_date  DATE         NOT NULL,
    end_date    DATE         NOT NULL,
    notes       VARCHAR(300) NOT NULL DEFAULT '',
    created_by  CHAR(36)     NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_school_holidays_school_dates (school_id, start_date, end_date),
    CONSTRAINT fk_school_holidays_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_school_holidays_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_school_holidays_kind CHECK (kind IN ('holiday', 'event')),
    CONSTRAINT chk_school_holidays_dates CHECK (end_date >= start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

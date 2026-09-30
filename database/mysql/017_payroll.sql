-- 017: staff salaries and monthly payslips. A teacher's salary is set once, and
-- each month's payslip is generated from staff attendance and the holiday
-- calendar as a draft, then marked paid. Paid payslips never change.
-- Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS teacher_salaries (
    teacher_id   CHAR(36)       NOT NULL PRIMARY KEY,
    school_id    CHAR(36)       NOT NULL,
    basic        DECIMAL(10,2)  NOT NULL,
    allowances   DECIMAL(10,2)  NOT NULL DEFAULT 0,
    deductions   DECIMAL(10,2)  NOT NULL DEFAULT 0,  -- fixed monthly, e.g. PF
    updated_at   TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_teacher_salaries_school (school_id),
    CONSTRAINT fk_teacher_salaries_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    CONSTRAINT fk_teacher_salaries_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT chk_teacher_salaries_amounts CHECK (basic >= 0 AND allowances >= 0 AND deductions >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS salary_slips (
    id             CHAR(36)       NOT NULL PRIMARY KEY,
    school_id      CHAR(36)       NOT NULL,
    teacher_id     CHAR(36)       NOT NULL,
    month          DATE           NOT NULL,  -- first day of the month
    working_days   SMALLINT       NOT NULL,
    days_present   SMALLINT       NOT NULL,
    days_leave     SMALLINT       NOT NULL,
    days_absent    SMALLINT       NOT NULL,
    days_unmarked  SMALLINT       NOT NULL,
    lop_days       DECIMAL(4,1)   NOT NULL,  -- loss-of-pay days: defaults to days_absent, the admin can adjust
    basic          DECIMAL(10,2)  NOT NULL,
    allowances     DECIMAL(10,2)  NOT NULL,
    gross          DECIMAL(10,2)  NOT NULL,
    lop_amount     DECIMAL(10,2)  NOT NULL,
    deductions     DECIMAL(10,2)  NOT NULL,
    net            DECIMAL(10,2)  NOT NULL,
    status         VARCHAR(10)    NOT NULL DEFAULT 'draft',
    paid_on        DATE           NULL,
    payment_mode   VARCHAR(20)    NOT NULL DEFAULT '',
    note           VARCHAR(200)   NOT NULL DEFAULT '',
    created_at     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_salary_slips_teacher_month (teacher_id, month),
    KEY idx_salary_slips_school_month (school_id, month),
    CONSTRAINT fk_salary_slips_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    CONSTRAINT fk_salary_slips_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT chk_salary_slips_status CHECK (status IN ('draft', 'paid'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Payroll is a new module: switch it on for existing schools like the others.
UPDATE schools SET enabled_modules = JSON_ARRAY_APPEND(enabled_modules, '$', 'payroll')
WHERE NOT JSON_CONTAINS(enabled_modules, '"payroll"');

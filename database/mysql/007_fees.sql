-- 007: fees — fee items per class, each student's dues, payments with
-- numbered receipts, and fee reminders in the parent alert log.
-- Applied automatically by the backend (see database/README.md).

-- One fee for one class, e.g. "Term 1 tuition" for Grade 5, due 15 Jun.
-- The same name/term across classes is simply several rows.
CREATE TABLE IF NOT EXISTS fee_items (
    id             CHAR(36)      NOT NULL PRIMARY KEY,
    school_id      CHAR(36)      NOT NULL,
    class_id       CHAR(36)      NOT NULL,
    name           VARCHAR(150)  NOT NULL,
    term_label     VARCHAR(50)   NOT NULL DEFAULT '',
    academic_year  VARCHAR(9)    NOT NULL,
    amount         DECIMAL(10,2) NOT NULL,
    due_date       DATE          NOT NULL,
    created_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_fee_items_school_class (school_id, class_id),
    CONSTRAINT fk_fee_items_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_fee_items_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT chk_fee_items_amount CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- What one student owes for one fee item; discount is a concession.
CREATE TABLE IF NOT EXISTS student_fees (
    id              CHAR(36)      NOT NULL PRIMARY KEY,
    school_id       CHAR(36)      NOT NULL,
    student_id      CHAR(36)      NOT NULL,
    fee_item_id     CHAR(36)      NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    discount        DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_note   VARCHAR(200)  NOT NULL DEFAULT '',
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_student_fees_student_item (student_id, fee_item_id),
    KEY idx_student_fees_item (fee_item_id),
    CONSTRAINT fk_student_fees_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_fees_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_student_fees_item FOREIGN KEY (fee_item_id) REFERENCES fee_items(id) ON DELETE CASCADE,
    CONSTRAINT chk_student_fees_discount CHECK (discount >= 0 AND discount <= amount)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Money received against one student fee. Online payments start 'pending'
-- and become 'success' once the gateway confirms; a wrong entry is
-- 'cancelled' (with a reason), never deleted.
CREATE TABLE IF NOT EXISTS fee_payments (
    id                  CHAR(36)      NOT NULL PRIMARY KEY,
    school_id           CHAR(36)      NOT NULL,
    student_id          CHAR(36)      NOT NULL,
    student_fee_id      CHAR(36)      NOT NULL,
    amount              DECIMAL(10,2) NOT NULL,
    method              VARCHAR(20)   NOT NULL,
    reference           VARCHAR(100)  NOT NULL DEFAULT '',
    paid_on             DATE          NOT NULL,
    status              VARCHAR(10)   NOT NULL,
    receipt_number      VARCHAR(30)   NULL,
    notes               VARCHAR(300)  NOT NULL DEFAULT '',
    cancel_reason       VARCHAR(300)  NOT NULL DEFAULT '',
    gateway_order_id    VARCHAR(100)  NULL,
    gateway_payment_id  VARCHAR(100)  NULL,
    received_by         CHAR(36)      NULL,
    created_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_fee_payments_receipt (school_id, receipt_number),
    UNIQUE KEY uq_fee_payments_gateway_order (gateway_order_id),
    KEY idx_fee_payments_student_fee (student_fee_id),
    KEY idx_fee_payments_school_paid_on (school_id, paid_on),
    CONSTRAINT fk_fee_payments_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_fee_payments_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_fee_payments_student_fee FOREIGN KEY (student_fee_id) REFERENCES student_fees(id) ON DELETE CASCADE,
    CONSTRAINT fk_fee_payments_received_by FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_fee_payments_amount CHECK (amount > 0),
    CONSTRAINT chk_fee_payments_method CHECK (method IN ('cash', 'upi', 'cheque', 'bank_transfer', 'card', 'online')),
    CONSTRAINT chk_fee_payments_status CHECK (status IN ('success', 'pending', 'failed', 'cancelled'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Per-school receipt counter (RCPT numbers never repeat or skip backwards).
CREATE TABLE IF NOT EXISTS fee_receipt_counters (
    school_id    CHAR(36) NOT NULL PRIMARY KEY,
    last_number  INT      NOT NULL,
    CONSTRAINT fk_fee_receipt_counters_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Fee reminders share the parent alert log.
ALTER TABLE parent_alerts DROP CONSTRAINT chk_parent_alerts_kind;
ALTER TABLE parent_alerts ADD CONSTRAINT chk_parent_alerts_kind CHECK (kind IN ('absence', 'remark', 'fee'));

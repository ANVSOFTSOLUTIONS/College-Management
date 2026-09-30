-- 024: offline fee payments reported by parents. A parent who paid outside
-- the app (UPI to the school, bank transfer, cash, cheque) reports it with a
-- reference and an optional screenshot. The office checks it and approves
-- (which records the payment and issues a receipt) or rejects with a reason.
-- school_payment_settings.offline_instructions tells parents where to pay
-- (the school's UPI ID, bank account, office hours).
-- status: 'submitted', 'approved' or 'rejected'.
-- Applied automatically by the backend.

CREATE TABLE IF NOT EXISTS fee_payment_claims (
    id                  CHAR(36)      NOT NULL PRIMARY KEY,
    school_id           CHAR(36)      NOT NULL,
    student_id          CHAR(36)      NOT NULL,
    student_fee_id      CHAR(36)      NOT NULL,
    parent_user_id      CHAR(36)      NULL,
    amount              DECIMAL(10,2) NOT NULL,
    method              VARCHAR(20)   NOT NULL,
    reference           VARCHAR(100)  NOT NULL DEFAULT '',
    paid_on             DATE          NOT NULL,
    note                VARCHAR(300)  NOT NULL DEFAULT '',
    proof_path          VARCHAR(300)  NULL,
    proof_content_type  VARCHAR(100)  NULL,
    status              VARCHAR(10)   NOT NULL DEFAULT 'submitted',
    review_note         VARCHAR(300)  NOT NULL DEFAULT '',
    payment_id          CHAR(36)      NULL,
    reviewed_by         CHAR(36)      NULL,
    reviewed_at         TIMESTAMP     NULL,
    created_at          TIMESTAMP(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_fee_payment_claims_school_status (school_id, status),
    KEY idx_fee_payment_claims_student (student_id),
    CONSTRAINT fk_fee_payment_claims_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_fee_payment_claims_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_fee_payment_claims_student_fee FOREIGN KEY (student_fee_id) REFERENCES student_fees(id) ON DELETE CASCADE,
    CONSTRAINT fk_fee_payment_claims_parent FOREIGN KEY (parent_user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_fee_payment_claims_payment FOREIGN KEY (payment_id) REFERENCES fee_payments(id) ON DELETE SET NULL,
    CONSTRAINT fk_fee_payment_claims_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_fee_payment_claims_amount CHECK (amount > 0),
    CONSTRAINT chk_fee_payment_claims_status CHECK (status IN ('submitted', 'approved', 'rejected'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE school_payment_settings ADD COLUMN offline_instructions VARCHAR(500) NOT NULL DEFAULT '';

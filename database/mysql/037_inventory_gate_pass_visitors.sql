-- Inventory: lab equipment, furniture, sports goods and consumables, with stock movements.
CREATE TABLE IF NOT EXISTS inventory_items (
    id            CHAR(36)     NOT NULL PRIMARY KEY,
    school_id     CHAR(36)     NOT NULL,
    name          VARCHAR(150) NOT NULL,
    category      VARCHAR(60)  NOT NULL DEFAULT '',
    location      VARCHAR(100) NOT NULL DEFAULT '',
    unit          VARCHAR(20)  NOT NULL DEFAULT 'nos',
    quantity      INT          NOT NULL DEFAULT 0,
    issued        INT          NOT NULL DEFAULT 0,
    min_quantity  INT          NOT NULL DEFAULT 0,
    notes         VARCHAR(300) NOT NULL DEFAULT '',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_inventory_items_name (school_id, name, location),
    CONSTRAINT fk_inventory_items_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS inventory_movements (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    item_id     CHAR(36)     NOT NULL,
    kind        VARCHAR(10)  NOT NULL,
    quantity    INT          NOT NULL,
    person      VARCHAR(150) NOT NULL DEFAULT '',
    note        VARCHAR(300) NOT NULL DEFAULT '',
    created_by  CHAR(36)     NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_inventory_movements_item (item_id),
    CONSTRAINT fk_inventory_movements_item FOREIGN KEY (item_id) REFERENCES inventory_items (id) ON DELETE CASCADE,
    CONSTRAINT fk_inventory_movements_user FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Gate passes: a student asks to leave campus / hostel; the office approves; the gate marks out and back.
CREATE TABLE IF NOT EXISTS gate_passes (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    school_id       CHAR(36)     NOT NULL,
    student_id      CHAR(36)     NOT NULL,
    requested_by    CHAR(36)     NOT NULL,
    reason          VARCHAR(300) NOT NULL,
    leave_at        DATETIME     NOT NULL,
    return_by       DATETIME     NOT NULL,
    status          VARCHAR(10)  NOT NULL DEFAULT 'pending',
    note            VARCHAR(300) NOT NULL DEFAULT '',
    decided_by      CHAR(36)     NULL,
    went_out_at     DATETIME     NULL,
    returned_at     DATETIME     NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_gate_passes_school_status (school_id, status),
    KEY idx_gate_passes_student (student_id),
    CONSTRAINT fk_gate_passes_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_gate_passes_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
    CONSTRAINT fk_gate_passes_requester FOREIGN KEY (requested_by) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_gate_passes_decider FOREIGN KEY (decided_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Visitor register at the gate.
CREATE TABLE IF NOT EXISTS visitors (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    name        VARCHAR(150) NOT NULL,
    phone       VARCHAR(15)  NOT NULL DEFAULT '',
    purpose     VARCHAR(200) NOT NULL,
    to_meet     VARCHAR(150) NOT NULL DEFAULT '',
    id_proof    VARCHAR(60)  NOT NULL DEFAULT '',
    vehicle_no  VARCHAR(20)  NOT NULL DEFAULT '',
    in_at       DATETIME     NOT NULL,
    out_at      DATETIME     NULL,
    created_by  CHAR(36)     NULL,
    KEY idx_visitors_school_in (school_id, in_at),
    CONSTRAINT fk_visitors_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_visitors_user FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

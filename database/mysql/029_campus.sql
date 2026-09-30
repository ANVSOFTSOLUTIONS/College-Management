-- 029: campus modules for colleges: library, hostel, transport and placements.
-- Each is an optional module the super admin switches on per college.
-- Colleges that already use every optional module get the four new ones too.
-- Applied automatically by the backend.

-- Library: books (with copies), loans to students or faculty, fines for late returns.
CREATE TABLE IF NOT EXISTS library_settings (
    school_id     CHAR(36)     NOT NULL PRIMARY KEY,
    loan_days     SMALLINT     NOT NULL DEFAULT 14,
    fine_per_day  DECIMAL(8,2) NOT NULL DEFAULT 2.00,
    max_books     SMALLINT     NOT NULL DEFAULT 3,
    CONSTRAINT fk_library_settings_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS library_books (
    id            CHAR(36)     NOT NULL PRIMARY KEY,
    school_id     CHAR(36)     NOT NULL,
    title         VARCHAR(250) NOT NULL,
    author        VARCHAR(200) NOT NULL DEFAULT '',
    isbn          VARCHAR(20)  NOT NULL DEFAULT '',
    category      VARCHAR(100) NOT NULL DEFAULT '',
    shelf         VARCHAR(50)  NOT NULL DEFAULT '',
    total_copies  SMALLINT     NOT NULL DEFAULT 1,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_library_books_school (school_id, title),
    CONSTRAINT fk_library_books_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS library_loans (
    id           CHAR(36)     NOT NULL PRIMARY KEY,
    school_id    CHAR(36)     NOT NULL,
    book_id      CHAR(36)     NOT NULL,
    student_id   CHAR(36)     NULL,
    teacher_id   CHAR(36)     NULL,
    issued_on    DATE         NOT NULL,
    due_on       DATE         NOT NULL,
    returned_on  DATE         NULL,
    fine         DECIMAL(8,2) NOT NULL DEFAULT 0,
    fine_paid    TINYINT(1)   NOT NULL DEFAULT 0,
    issued_by    CHAR(36)     NULL,
    KEY ix_library_loans_open (school_id, returned_on),
    CONSTRAINT fk_library_loans_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_library_loans_book FOREIGN KEY (book_id) REFERENCES library_books (id) ON DELETE CASCADE,
    CONSTRAINT fk_library_loans_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
    CONSTRAINT fk_library_loans_teacher FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Hostel: hostels, rooms with a capacity, and which student stays where.
CREATE TABLE IF NOT EXISTS hostels (
    id            CHAR(36)     NOT NULL PRIMARY KEY,
    school_id     CHAR(36)     NOT NULL,
    name          VARCHAR(150) NOT NULL,
    gender        VARCHAR(10)  NOT NULL DEFAULT 'mixed',
    warden_name   VARCHAR(150) NOT NULL DEFAULT '',
    warden_phone  VARCHAR(20)  NOT NULL DEFAULT '',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_hostels_name (school_id, name),
    CONSTRAINT fk_hostels_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hostel_rooms (
    id           CHAR(36)    NOT NULL PRIMARY KEY,
    school_id    CHAR(36)    NOT NULL,
    hostel_id    CHAR(36)    NOT NULL,
    room_number  VARCHAR(20) NOT NULL,
    capacity     TINYINT     NOT NULL DEFAULT 2,
    room_type    VARCHAR(20) NOT NULL DEFAULT 'non-ac',
    UNIQUE KEY uq_hostel_rooms (hostel_id, room_number),
    CONSTRAINT fk_hostel_rooms_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_hostel_rooms_hostel FOREIGN KEY (hostel_id) REFERENCES hostels (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hostel_allocations (
    id            CHAR(36)  NOT NULL PRIMARY KEY,
    school_id     CHAR(36)  NOT NULL,
    room_id       CHAR(36)  NOT NULL,
    student_id    CHAR(36)  NOT NULL,
    allocated_on  DATE      NOT NULL,
    vacated_on    DATE      NULL,
    KEY ix_hostel_allocations_active (school_id, vacated_on),
    CONSTRAINT fk_hostel_alloc_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_hostel_alloc_room FOREIGN KEY (room_id) REFERENCES hostel_rooms (id) ON DELETE CASCADE,
    CONSTRAINT fk_hostel_alloc_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Transport: bus routes with stops, and which student rides which route.
CREATE TABLE IF NOT EXISTS transport_routes (
    id              CHAR(36)      NOT NULL PRIMARY KEY,
    school_id       CHAR(36)      NOT NULL,
    name            VARCHAR(150)  NOT NULL,
    vehicle_number  VARCHAR(20)   NOT NULL DEFAULT '',
    driver_name     VARCHAR(150)  NOT NULL DEFAULT '',
    driver_phone    VARCHAR(20)   NOT NULL DEFAULT '',
    seats           SMALLINT      NOT NULL DEFAULT 50,
    annual_fare     DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_transport_routes_name (school_id, name),
    CONSTRAINT fk_transport_routes_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS transport_stops (
    id           CHAR(36)     NOT NULL PRIMARY KEY,
    route_id     CHAR(36)     NOT NULL,
    name         VARCHAR(150) NOT NULL,
    pickup_time  VARCHAR(10)  NOT NULL DEFAULT '',
    sort_order   SMALLINT     NOT NULL DEFAULT 0,
    CONSTRAINT fk_transport_stops_route FOREIGN KEY (route_id) REFERENCES transport_routes (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS transport_assignments (
    student_id  CHAR(36)  NOT NULL PRIMARY KEY,
    school_id   CHAR(36)  NOT NULL,
    route_id    CHAR(36)  NOT NULL,
    stop_id     CHAR(36)  NULL,
    assigned_on DATE      NOT NULL,
    CONSTRAINT fk_transport_assign_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
    CONSTRAINT fk_transport_assign_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_transport_assign_route FOREIGN KEY (route_id) REFERENCES transport_routes (id) ON DELETE CASCADE,
    CONSTRAINT fk_transport_assign_stop FOREIGN KEY (stop_id) REFERENCES transport_stops (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Placements: companies, recruitment drives with eligibility, and students' applications.
-- eligible_departments: JSON list of department ids (empty: every department).
-- drive status: 'open', 'closed' or 'completed'. application status: 'applied', 'shortlisted', 'selected' or 'rejected'.
CREATE TABLE IF NOT EXISTS placement_companies (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    name        VARCHAR(150) NOT NULL,
    industry    VARCHAR(100) NOT NULL DEFAULT '',
    website     VARCHAR(200) NOT NULL DEFAULT '',
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_placement_companies_name (school_id, name),
    CONSTRAINT fk_placement_companies_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS placement_drives (
    id                    CHAR(36)      NOT NULL PRIMARY KEY,
    school_id             CHAR(36)      NOT NULL,
    company_id            CHAR(36)      NOT NULL,
    role_title            VARCHAR(150)  NOT NULL,
    package_lpa           DECIMAL(6,2)  NULL,
    location              VARCHAR(150)  NOT NULL DEFAULT '',
    drive_date            DATE          NULL,
    last_date             DATE          NULL,
    min_cgpa              DECIMAL(4,2)  NULL,
    eligible_departments  LONGTEXT      NULL,
    description           TEXT          NULL,
    status                VARCHAR(10)   NOT NULL DEFAULT 'open',
    created_at            TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_placement_drives_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_placement_drives_company FOREIGN KEY (company_id) REFERENCES placement_companies (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS placement_applications (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    drive_id    CHAR(36)     NOT NULL,
    student_id  CHAR(36)     NOT NULL,
    status      VARCHAR(12)  NOT NULL DEFAULT 'applied',
    applied_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_placement_applications (drive_id, student_id),
    CONSTRAINT fk_placement_apps_school FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
    CONSTRAINT fk_placement_apps_drive FOREIGN KEY (drive_id) REFERENCES placement_drives (id) ON DELETE CASCADE,
    CONSTRAINT fk_placement_apps_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

UPDATE schools SET enabled_modules = JSON_MERGE_PRESERVE(enabled_modules, '["library", "hostel", "transport", "placements"]')
WHERE JSON_VALID(enabled_modules) AND JSON_CONTAINS(enabled_modules, '"payroll"') AND JSON_CONTAINS(enabled_modules, '"certificates"')
  AND NOT JSON_CONTAINS(enabled_modules, '"library"');

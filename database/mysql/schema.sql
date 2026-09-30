-- School Management System — MySQL/MariaDB schema (replaces the MongoDB collections).
-- Safe to run more than once: every statement uses IF NOT EXISTS.
--
-- cPanel-style hosting: create the database via cPanel's "MySQL Databases"
-- tool first (it will prefix the name, e.g. youruser_school_management),
-- select that database in phpMyAdmin, then import this file into it — a
-- phpMyAdmin session user normally can't CREATE DATABASE itself.
--
-- Self-managed MySQL server (local dev, your own VPS): uncomment the two
-- lines below to create and select the database in one step.
--
-- CREATE DATABASE IF NOT EXISTS school_management
--   CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE school_management;

-- ---------------------------------------------------------------------------
-- schools: the tenant boundary. Every other table is scoped to school_id.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schools (
    id              CHAR(36)      NOT NULL PRIMARY KEY,
    name            VARCHAR(200)  NOT NULL,
    code            VARCHAR(30)   NOT NULL,
    subdomain       VARCHAR(40)   NOT NULL,
    template        VARCHAR(20)   NOT NULL DEFAULT 'classic',
    enabled_modules JSON          NOT NULL,
    monthly_fee     DECIMAL(10,2) NOT NULL DEFAULT 600.00,
    billing_status  VARCHAR(20)   NOT NULL DEFAULT 'trial',
    status          VARCHAR(20)   NOT NULL DEFAULT 'active',
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_schools_code (code),
    UNIQUE KEY uq_schools_subdomain (subdomain),
    CONSTRAINT chk_schools_template CHECK (template IN ('classic', 'modern', 'vibrant')),
    CONSTRAINT chk_schools_billing_status CHECK (billing_status IN ('trial', 'active', 'suspended')),
    CONSTRAINT chk_schools_status CHECK (status IN ('active', 'inactive'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- users: login accounts. school_id is NULL only for role = 'super_admin',
-- which is a platform-level account not tied to any school.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            CHAR(36)     NOT NULL PRIMARY KEY,
    school_id     CHAR(36)     NULL,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL,
    full_name     VARCHAR(200) NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_school_role (school_id, role),
    CONSTRAINT fk_users_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT chk_users_role CHECK (role IN ('super_admin', 'admin', 'teacher')),
    CONSTRAINT chk_users_status CHECK (status IN ('active', 'inactive'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- teachers: staff profile, linked to a login account via user_id.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teachers (
    id          CHAR(36)     NOT NULL PRIMARY KEY,
    school_id   CHAR(36)     NOT NULL,
    user_id     CHAR(36)     NOT NULL,
    department  VARCHAR(100) NOT NULL DEFAULT 'General',
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_teachers_school_user (school_id, user_id),
    CONSTRAINT fk_teachers_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_teachers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- classes: one teacher per class/section/academic year.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS classes (
    id             CHAR(36)    NOT NULL PRIMARY KEY,
    school_id      CHAR(36)    NOT NULL,
    teacher_id     CHAR(36)    NOT NULL,
    name           VARCHAR(100) NOT NULL,
    section        VARCHAR(20)  NOT NULL,
    academic_year  VARCHAR(9)   NOT NULL,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_classes_school_name_section_year (school_id, name, section, academic_year),
    KEY idx_classes_teacher (teacher_id),
    CONSTRAINT fk_classes_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_classes_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- students
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id                CHAR(36)     NOT NULL PRIMARY KEY,
    school_id         CHAR(36)     NOT NULL,
    class_id          CHAR(36)     NOT NULL,
    admission_number  VARCHAR(50)  NOT NULL,
    full_name         VARCHAR(200) NOT NULL,
    parent_name       VARCHAR(200) NOT NULL DEFAULT '',
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_students_school_admission (school_id, admission_number),
    KEY idx_students_class (class_id),
    CONSTRAINT fk_students_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_students_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- attendance: one row per student per date.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance (
    id               CHAR(36)    NOT NULL PRIMARY KEY,
    school_id        CHAR(36)    NOT NULL,
    class_id         CHAR(36)    NOT NULL,
    student_id       CHAR(36)    NOT NULL,
    attendance_date  DATE        NOT NULL,
    status           VARCHAR(10) NOT NULL,
    marked_by        CHAR(36)    NOT NULL,
    marked_at        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_attendance_student_date (student_id, attendance_date),
    KEY idx_attendance_class_date (class_id, attendance_date),
    CONSTRAINT fk_attendance_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_marked_by FOREIGN KEY (marked_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_attendance_status CHECK (status IN ('present', 'absent', 'late'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- school_sites: the public landing page content, one row per school.
-- Banners/gallery/activities/notices are child tables (were embedded arrays
-- in MongoDB; here each becomes its own row with a real primary key).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS school_sites (
    id               CHAR(36)     NOT NULL PRIMARY KEY,
    school_id        CHAR(36)     NOT NULL,
    logo_url         VARCHAR(500) NULL,
    about            TEXT         NOT NULL,
    contact_address  VARCHAR(300) NOT NULL DEFAULT '',
    contact_phone    VARCHAR(50)  NOT NULL DEFAULT '',
    contact_email    VARCHAR(255) NOT NULL DEFAULT '',
    contact_map_url  VARCHAR(500) NOT NULL DEFAULT '',
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_school_sites_school (school_id),
    CONSTRAINT fk_school_sites_school FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS school_site_banners (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    school_site_id  CHAR(36)     NOT NULL,
    url             VARCHAR(500) NOT NULL,
    caption         VARCHAR(300) NOT NULL DEFAULT '',
    sort_order      INT          NOT NULL DEFAULT 0,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_banners_site (school_site_id),
    CONSTRAINT fk_banners_site FOREIGN KEY (school_site_id) REFERENCES school_sites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS school_site_gallery (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    school_site_id  CHAR(36)     NOT NULL,
    url             VARCHAR(500) NOT NULL,
    caption         VARCHAR(300) NOT NULL DEFAULT '',
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_gallery_site (school_site_id),
    CONSTRAINT fk_gallery_site FOREIGN KEY (school_site_id) REFERENCES school_sites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS school_site_activities (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    school_site_id  CHAR(36)     NOT NULL,
    title           VARCHAR(200) NOT NULL,
    activity_date   DATE         NOT NULL,
    description     TEXT         NOT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_activities_site (school_site_id),
    CONSTRAINT fk_activities_site FOREIGN KEY (school_site_id) REFERENCES school_sites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Not managed by any endpoint yet (the notice board module hasn't been built),
-- but the public site response already has a notices list, so the table
-- exists ready for that module.
CREATE TABLE IF NOT EXISTS school_site_notices (
    id              CHAR(36)     NOT NULL PRIMARY KEY,
    school_site_id  CHAR(36)     NOT NULL,
    title           VARCHAR(300) NOT NULL,
    notice_date     DATE         NOT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_notices_site (school_site_id),
    CONSTRAINT fk_notices_site FOREIGN KEY (school_site_id) REFERENCES school_sites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

# Database

MySQL/MariaDB, accessed from the FastAPI backend through `aiomysql` (see
`backend/app/db/`). Originally built on MongoDB; converted to MySQL on
2026-09-23 for hosting-cost reasons (see `docs/PROJECT_PLAN.md`) — the old
MongoDB migration scripts were removed since they no longer apply.

- `mysql/schema.sql`: the full schema — every table, foreign key, and
  `CHECK`/`UNIQUE` constraint, in one importable file. Every statement uses
  `IF NOT EXISTS`, safe to run more than once. Future schema changes should
  be added as new, separate versioned `.sql` files here (project rule:
  never edit an already-applied migration).
- Numbered migrations (`mysql/NNN_*.sql`) are applied **automatically** by
  the backend when it connects (`backend/app/db/migrations.py`), in order,
  and recorded in `schema_migrations`. No manual import is needed after
  `schema.sql`; on cPanel `.cpanel.yml` copies them next to the app. A change
  that is already present (e.g. imported by hand) is accepted as applied.
  Don't put `;` inside string literals or comments in these files.
  - `002_staff_attendance.sql`: teacher attendance (`staff_attendance`),
    separate from student `attendance`.
  - `003_teacher_profiles_and_subjects.sql`: teacher profile columns,
    `subjects`, and `class_subjects` (subject teacher per class).
  - `004_student_profiles_and_guardians.sql`: student profile columns and
    `student_guardians` (father/mother/guardian contacts).
  - `005_student_logins_and_documents.sql`: student logins (`users.login_id`,
    `must_change_password`, nullable email, `student`/`parent` roles),
    student photo, and `student_documents`.
  - `006_remarks_and_parent_alerts.sql`: `student_remarks` and the
    `parent_alerts` log.
  - `007_fees.sql`: fee items, student fees, payments, receipt counters;
    fee reminders in `parent_alerts`.
  - `008_parents_and_online_payments.sql`: `parent_students` links and
    per-school online payment settings (now Cashfree, see 019).
  - `009_exams.sql`: exams, exam papers (class x subject), and marks.
  - `010_punch_leave_notifications.sql`: school timings, staff punches,
    leave requests, and in-app notifications.
  - `011_site_templates_and_marketing.sql`: ten site templates, platform
    contact settings, and demo requests.
  - `012_promotion.sql`: archived classes and year-end promotion runs.
  - `013_notices_homework.sql`: notice board (with target classes) and homework.
  - `014_timetable_calendar.sql`: school periods, class timetables and the holiday/event calendar.
  - `015_certificates.sql`: TC and bonafide certificates with per-year serial numbers.
  - `016_new_modules.sql`: switches the homework and certificates modules on for existing schools.
  - `017_payroll.sql`: teacher salaries and monthly payslips (and the payroll module).
  - `018_admissions.sql`: admission applications, their documents, and the open/close switch.
  - `019_cashfree.sql`: online payments move to Cashfree (Live/Test mode); saved Razorpay keys are cleared and switched off.
  - `020_pro_earnings_customize_push.sql`: Pro templates flag, platform payments, website customisation, push subscriptions and VAPID keys.
  - `021_audit_log.sql`: the audit log of sensitive changes.
- Demo data for showing the product runs via `../backend/scripts/demo_seed.py`
  (`python -m scripts.demo_seed` from `backend/`): one demo school with
  classes, teachers, students, and 30 school days of student and teacher
  attendance. It prompts for the demo login password.
- Local/dev-only sample data (not for production) is seeded via
  `../backend/scripts/dev_seed.py`, run with the backend's own virtualenv
  (`./.venv/Scripts/python -m scripts.dev_seed` from `backend/`). It creates
  a super admin plus two sample schools (admin, teacher, a class, a few
  students each), to exercise multi-tenant isolation locally. It's a no-op
  for schools if any already exist.

Keep table references and indexes aligned with `../docs/PROJECT_PLAN.md`, in
particular that every table except `schools` is scoped by `school_id`
(`users.school_id` is the one exception, nullable for `role = 'super_admin'`).

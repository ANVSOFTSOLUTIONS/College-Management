# School Management System Project Plan

## Objective

Deliver a role-based school management platform for administrators, teachers, students, and parents. The first release covers the modules shown in the architecture: dashboard, students, teachers, attendance, exams and marks, timetable, fees, notice board, reports, and performance.

The platform is multi-tenant: one deployment serves multiple schools, each with its own users, students, classes, and data, fully isolated from every other school. Each school can also customize its own public-facing branding (logo, banners, about/contact info) — see "Public school site & branding" under Phase 6.

## Target architecture

### Frontend

React.js with Tailwind CSS. The frontend provides role-aware navigation, forms, tables, dashboards, reports, and responsive layouts. It communicates with the backend only through the versioned REST API.

### Backend

FastAPI with Python. The API gateway handles JWT authentication, authorization dependencies, Pydantic request validation, rate limiting, consistent errors, and module routers. Supporting integrations include PDF generation, SMS/WhatsApp, email alerts, and biometric-device synchronization.

### Database

MySQL/MariaDB, accessed from FastAPI through `aiomysql` — raw parameterized
SQL, no ORM (kept consistent with the rest of the codebase: thin, direct
data access rather than a heavier abstraction). **Originally built on
MongoDB; converted to MySQL on 2026-09-23** because the target hosting
(cPanel shared hosting) only supports MySQL. Core tables are `schools`,
`users`, `teachers`, `classes`, `students`, `attendance`, `school_sites`
(+ its child tables `school_site_banners`/`gallery`/`activities`/`notices`).
The full schema lives in one file, `database/mysql/schema.sql` — see
`database/README.md`.

Every table except `schools` carries a `school_id`. Every query and
authorization check must be scoped by `school_id` — a user from one school
must never be able to read or write another school's data, and lookups by
ID alone (without also checking `school_id`) are a bug. A user account
(`users`) belongs to exactly one school, **except** the `super_admin` role,
whose `school_id` is `NULL` — it is a platform-level account, not tied to
any single school. Primary keys are UUID strings (`CHAR(36)`), generated in
application code via `uuid.uuid4()`, not auto-increment integers.

### Platform administration & billing

This is a SaaS product: the platform operator hosts the software centrally, each school is a paying tenant with its own login, and access can be revoked per school. **Done**: a `super_admin` role (seeded manually, see `backend/scripts/dev_seed.py` — no self-signup) can create schools and their first admin account in one call, choose which feature modules a school has access to (`enabled_modules`, validated against a fixed list), assign a public site `template`, and set `billing_status` (`trial`/`active`/`suspended`). Login is blocked with `403 school_suspended` for any user whose school has `billing_status: "suspended"` or `status: "inactive"` — this is the actual access-control lever behind "pay monthly or lose access." `monthly_fee` (default 600) is currently just a stored number for the super admin's own record-keeping — there is no payment gateway integration, invoicing, or automated billing yet; suspension is a manual action the super admin takes via `PATCH /api/v1/super-admin/schools/{id}`. See `backend/app/modules/super_admin/`.

## Delivery phases

### Phase 1: Foundation

- Initialize the React/Vite frontend and FastAPI backend packages.
- Add environment configuration and `.env.example` files.
- Set up linting, formatting, testing, and a shared API error shape.
- Configure the MySQL connection pool, schema, and seed data.
- Establish JWT login, password hashing, role checks, and rate limiting. **Done** for admin and teacher roles: `POST /api/v1/auth/login` issues a school-scoped JWT (`sub`, `school_id`, `role`); students sign in with school code + admission number and parents with their mobile (see Phase B/D below).

### Phase 2: Core people and organization

- Implement users, students, teachers, classes, and role-aware profiles.
- Add CRUD APIs with validation and authorization.
- Build dashboard shell, navigation, tables, search, pagination, and profile screens.
- **Partially done (Phase A of the 2026-09-27 teacher/class/student/parent plan)**: admin-only teacher management (`/api/v1/teachers`: create with login, edit profile/password, `DELETE` deactivates — blocked while the teacher is a class teacher, and clears their subject assignments), subjects (`/api/v1/subjects`), and class sections (`POST/GET/PATCH/DELETE /api/v1/classes/{id}`, class teacher on `classes.teacher_id`, subject teachers via `PUT/DELETE /api/v1/classes/{id}/subjects/{subject_id}`). Schema in `database/mysql/003_teacher_profiles_and_subjects.sql`. Frontend: "Teachers" and "Classes & Subjects" admin pages.
- **Phase B1 done**: `/api/v1/students` (list with class filter/search, create, detail, update, `DELETE` marks as left) with student profile (DOB, gender, blood group, admission date, address) and father/mother/guardian contacts plus a primary contact (`student_guardians`, migration 004). Admins manage every class; a teacher manages only classes they are class teacher of. Left students drop out of rosters. Frontend "Students" page for admin and class teachers.
- **Phase B2 done**: students sign in with school code + admission number (`POST /api/v1/auth/login` accepts `email` or `school_code`+`admission_number`); admins/class teachers create logins one at a time or per class (`POST /api/v1/students/{id}/login`, `POST /api/v1/students/bulk-logins`) with generated passwords shown once, and every first sign-in forces a password change (`POST /api/v1/auth/change-password`). Students upload their photo and documents (`/api/v1/me/student/...`); documents wait for admin/class-teacher approval or rejection with a reason. Files are stored in `backend/private_uploads/` and only streamed to the student, their class teacher, and admins. Migration 005 also allows the `student` and `parent` roles.
- **Phase C done**: teachers see the classes they teach (`/api/v1/teaching/classes`, class or subject teacher) and their roster; they record remarks (`/api/v1/remarks`: missed exam, absent from class, homework, behaviour, appreciation, other), optionally alerting the parent. Marking a student absent for today alerts the parent once. Every alert is logged in `parent_alerts` (`/api/v1/parent-alerts`, admin or class teacher). SMS is built (`backend/app/integrations/sms.py`, MSG91 flow templates) but **off** (`SMS_ENABLED=false`) until a provider account exists; alerts are then recorded as `not_sent`. The MSG91 sender is unit-tested only, not yet against a live account. Migration 006.
- **Phase D done**: fees (`/api/v1/fees/...`, admin only): fee items per class with a term, amount, due date (creating one bills every active student; "sync" bills late joiners); per-student accounts with concessions; office payments (cash/UPI/cheque/bank transfer/card) with sequential per-school receipt numbers (`RCPT-<year>-<n>`), cancellation with a reason (never deletion); dues report; fee reminders to parents through the alert log (SMS still off). Parents sign in with their mobile (`/auth/login` `phone`); staff create/link parent logins from the primary contact's mobile, per student or per class, and siblings (even across schools) share one login. Parent portal (`/api/v1/me/parent/...`): children, 30-day attendance, remarks meant for parents, alerts, fees, receipts. Online payment via each school's own Cashfree account (replaced Razorpay on 2026-09-28, migration 019) is built (`backend/app/integrations/cashfree.py`: the server creates the order, and counts a payment only after asking Cashfree that the order is PAID for the right amount; a signed webhook at `/api/v1/public/payments/cashfree/webhook` covers closed tabs) but off until a school saves its App ID and secret key and turns it on (Fees page, or `/api/v1/fees/payment-settings`, with Live/Test mode). Secret keys are stored encrypted with `DATA_ENCRYPTION_KEY` (`app/core/secrets.py`). Not yet run against a live Cashfree account. Migrations 007–008.
- **Phase E done**: exams (`/api/v1/exams`, admin): creating one adds a paper for every subject taught in each chosen class (max/pass marks editable per paper); subject teachers enter marks for their papers and class teachers for every paper of their class (`/api/v1/exam-papers/mine`, `/{id}/marks`), with absent marks alerting the parent once; class results (`/exams/{id}/classes/{class_id}/results`, admin or class teacher) with totals, percentage, CBSE nine-point grades, pass/fail, competition ranking, and subject stats; printable report cards. Publishing shows results to students (`/me/student/results`) and parents (`/me/parent/children/{id}/results`) and locks marks. Migration 009.
- **Phase F done**: the frontend is an installable PWA (`frontend/public/manifest.webmanifest`, icons, `sw.js`: network-first pages, cache-first hashed assets, API never cached; registered in production builds only). Sign-in shows an Install button (Android/Chrome) or Add to Home Screen steps (iPhone). Admin "App & QR codes" page gives QR codes and links per audience (`/?as=student&school=CODE`, `/?as=parent`, `/?as=staff`) with copy, WhatsApp share, download, and printable posters; the link's sign-in tab and school code are remembered for the installed app. `GET /api/v1/auth/me` returns the user and their school.
- **Staff punch & leave done (2026-09-27)**: teachers punch in/out from their login (`/api/v1/staff-punch/in|out|me`); a punch-in marks staff attendance present, or late after the school's start time plus grace (`/api/v1/school-settings`); admins see the day's punch log (`GET /api/v1/staff-punch?date=`). Leave (`/api/v1/leave`): teachers apply to admins, students to their class teacher; approval notifies the applicant, marks an approved teacher's weekdays as leave, and tells a class teacher's own students; approved student leave shows on the attendance sheet and suppresses the parent absence alert. In-app notifications with a bell (`/api/v1/notifications`, polled every minute). Migration 010. Punch has no location check yet.
- **Website templates & marketing done (2026-09-27)**: the public school site is wired to the backend (the old in-memory mock is gone) and renders one of ten templates (`frontend/src/siteTemplates/`: themes + one renderer; ids match `TEMPLATE_IDS` in `backend/app/modules/super_admin/schemas.py`). New schools get a template picked from their code; school admins switch templates and manage logo, banners, about/contact, gallery, events and notices on the School Site page (`PUT /api/v1/school-site/template`, notices endpoints). Public site at `/site/:code`; template previews at `/templates/:id` (sample content, or `?school=CODE`). `/` is now the ANV School ERP marketing page for visitors (the app is at `/login`; `?as=`/`?source=` links still open the app), with a demo-request form (`POST /api/v1/public/demo-requests`, rate-limited, honeypot) and contact details the super admin sets; the super admin console has Demo requests and Landing page tabs. Sample template photos are hot-linked from Unsplash. Migration 011.
- **School-only focus (2026-09-27)**: the product is for schools only; a College mode is not planned (decided 2026-09-28). School pending list, in order: (1) Excel import + year-end promotion — done; (2) dashboard — done; (3) notice board + homework — done; (4) timetable + holiday calendar — done; (5) reports + performance — done; (6) ID card/TC, Staff & Biometric cleanup — done.
- **Bulk import & promotion done**: `/api/v1/students/import/template` (xlsx with the school's classes) and `/api/v1/students/import` (xlsx/csv, dry run by default, row-by-row errors, all-or-nothing unless `skip_invalid`); `openpyxl` added. `/api/v1/promotion/plan` suggests each class's next class (LKG→UKG→1, numbered classes +1, the last class passes out) and `/api/v1/promotion` moves students (keep-back per student), creates next-year classes copying class/subject teachers, graduates the final class (login off), archives last year's classes (`classes.is_archived`), and runs once per year (`promotion_runs`). Exam results and report cards now follow the class a student sat the exam in, so history survives promotion. Migration 012.
- **Dashboard done**: `/api/v1/dashboard/admin` (today's student attendance and unmarked classes with their class teacher, a 7-school-day attendance trend with Sundays skipped, teachers punched in/late/on leave, fees collected today/this month, outstanding and overdue, pending staff leave and documents, marks-entry progress of unpublished exams) and `/api/v1/dashboard/teacher` (own punch, own class's attendance today, pending student leave and documents, papers with marks still to enter). Archived classes are excluded. Admins now land on the dashboard; teachers still land on Punch In / Out.
- **Notice board & homework done**: `/api/v1/notices` (admin: whole school or chosen classes, for teachers/students/parents, pin, show-until date; teachers: classes they teach, for students/parents; PDF/image attachment in private storage) and `/api/v1/homework` (subject teacher for their subjects, class teacher for any subject of their class, admin any; students see their class, parents pick a child; default window: due in the last two weeks onward). `/api/v1/homework/options` lists the classes and subjects a user can post to. Everyone targeted gets a bell notification (SMS stays off). Parents have no school of their own, so their visibility follows their children's classes and schools. Migration 013.
- **Timetable & holiday calendar done**: `/api/v1/timetable/periods` (the school's bell schedule, breaks included; removing a period or making it a break clears it from every grid), `/api/v1/timetable/classes/{id}` (Monday–Saturday grid of the class's subjects; the teacher comes from the class's subject teacher, and a grid that puts a teacher in two classes at once is refused with 409), `/api/v1/timetable/mine` (teacher's week, student's class, parent's child). `/api/v1/calendar` holds holidays (school closed) and events, with an optional bell notification to everyone. Dashboards skip holidays in the attendance trend, stop chasing attendance on a holiday, and show a teacher's periods today. Migration 014.
- **Reports & performance done**: `/api/v1/reports/student-attendance` (per student present/late/absent and %, for any date range; admins all classes, class teachers their own; a student's attendance counts even if taken in last year's class), `/api/v1/reports/staff-attendance` (per teacher per month), `/api/v1/reports/fee-dues.xlsx`; each report downloads as Excel with `format=xlsx`. `/api/v1/reports/exam-performance/{exam_id}` gives class and subject averages, pass rates, the grade spread, the top 10 and students who failed or missed a paper with their 90-day attendance (admins every class, class teachers their own). No migration.
- **ID cards, certificates & cleanup done**: `/api/v1/id-cards?class_id=` (card data; the page prints 85.6 × 54 mm cards, 8 per A4, with photo and a QR of `SCHOOLCODE:ADMISSION`), `/api/v1/students/{id}/certificates` (TC or bonafide; each keeps a snapshot of what was printed and gets a serial like `TC/2026/0001`; a TC marks the student as left; one live TC per student; cancelling keeps the serial used), `/api/v1/certificates` (recent) and `/certificates/{id}/cancel`. The mock Staff & Biometric page and its fake data are removed; staff attendance is Punch In/Out, and the `staff-biometric` module id is still accepted for schools saved with it. Biometric-device sync stays future work. Migration 015.
- **Module switches enforced (2026-09-28)**: the super admin's per-school modules (`app/core/modules.py`: dashboard, exams, homework, notices, timetable (with calendar), fees, reports, performance, certificates, payroll, school-site) are now checked on the API (403 `module_disabled`) and hide their menu items; `/auth/login` and `/auth/me` return `enabled_modules`, and the app refreshes them on load. Students, teachers, classes, attendance, leave and punch in/out are always on; the old `students`/`attendance`/`staff-biometric` ids are still accepted. Migrations 016/017 switch the new modules on for existing schools.
- **Payroll done**: `/api/v1/payroll/salaries` (basic, allowances, fixed deductions per teacher), `/api/v1/payroll/months/{month}/generate` (draft payslips from staff attendance and holidays: Mon–Sat minus holidays are working days, present/late/approved leave are paid, days marked absent are loss of pay at gross/working days, unmarked days are shown), `PATCH /payroll/slips/{id}` (adjust LOP days on a draft), `/pay` and `/revert`, and `/payroll/mine` for teachers (paid payslips only, printable, with net pay in words). Migration 017.
- **Payment secret encryption done**: `app/core/secrets.py` stores the school's key secret encrypted with `DATA_ENCRYPTION_KEY` (Fernet); older plain-text rows still work and are encrypted on the next save. Online payment itself stays on hold.
- **Admissions done**: public form `/apply/{CODE}` (no login) backed by `/api/v1/public/schools/{code}/admissions` (form data, apply, and document upload with a two-hour upload token; rate-limited per IP with a hidden bot-trap field; only while the school's admissions are open and the module is on). Admin `/api/v1/admissions`: list, walk-in enquiries, documents, open/close, suggested admission number, approve (creates the student with parents in the chosen class, moves documents into verified student documents and the photo onto the student) and reject with a reason. Admins get a bell notification and a dashboard count; school websites show an "Apply for admission" button while admissions are open. Migration 018.
- **Pro templates, platform earnings, site customisation, push notifications (2026-09-28)**: two website templates are free (`FREE_TEMPLATES`: classic, modern) and the other eight need `schools.pro_templates`, switched on by the super admin once the school pays (a school keeps a Pro template it already uses; new schools get a free one). `/api/v1/super-admin/analytics` (schools by status, students, teachers, monthly recurring, money received this month/year/all time, last 12 months, per school) and `/api/v1/super-admin/payments` (money schools paid the platform, recorded by the super admin). `PUT /api/v1/school-site/customize`: tagline, own main/highlight colour over the template, and hiding About/Events/Gallery/Notices. Web Push (`app/core/webpush.py`, RFC 8291 + VAPID with a key pair kept in platform_settings; `/api/v1/push/*`): every bell notification also goes to the user's devices that turned on phone notifications (switch in the bell panel; iPhone needs the app on the Home Screen). Migration 020.
- **Backups & audit log done**: the API backs up the database daily and uploaded files weekly to `~/school_backups` (kept 14/4), triggered by a cron call to `/api/v1/internal/backups/run` with `BACKUP_TOKEN`, or by the super admin (Backups tab: status, back up now, download); setup and restore in `docs/BACKUPS.md`. `/api/v1/audit-log` records changed marks, publishing, attendance edits, fee payments/cancellations/concessions/fee changes, student status/class/login changes, certificates, salaries and payslips, admissions decisions, payment settings and super admin school changes (Activity log page for admins; the super admin sees all schools). Migration 021.

### Phase 3: Academic operations

- Add timetable and class scheduling.
- Add attendance capture, biometric sync boundary, daily summaries, and reports. **Partially done**: `GET/POST /api/v1/classes/{class_id}/attendance` and `GET /api/v1/classes/{class_id}/students` let a class's assigned teacher (or an admin in the same school) mark and view daily attendance. Teacher attendance is separate: `GET/POST /api/v1/staff-attendance?date=` (admin only; statuses present/absent/late/leave; table from `database/mysql/002_staff_attendance.sql`), with a "Teacher Attendance" page in the admin nav. Daily summaries (dashboard) and reports are built; staff attendance comes from Punch In/Out. Biometric-device sync is not built.
- Add exams, marks entry, grading rules, result views, and performance summaries.

### Phase 4: Finance and communication

- Add fees, payment recording, receipts, and outstanding-balance views.
- Add salary records and payroll reports.
- Add notice board posts, email alerts, and SMS/WhatsApp integration adapters.

### Phase 5: Reporting and release hardening

- Add PDF exports and role-specific report downloads.
- Add audit logging, backup verification, security review, and accessibility checks.
- Add end-to-end coverage for login, attendance, marks, fees, and reports.
- Deploy frontend to Vercel and backend/database using the selected Railway setup.

### Phase 6: Public school site & branding

- Let a school admin upload and update their own school's logo and banner/slider images.
- Add an editable "About" and "Contact" profile per school (address, phone, email, map, etc.).
- Add a gallery module and an activities/events list per school.
- Build a public-facing landing page (no login required) per school that renders: banners/sliders, notices pulled from the notice board, about, contact, gallery, and activities.
- Uploaded images (logos, banners, gallery) are stored on a local disk volume for now (`backend/uploads/{school_id}/...`, served at `/uploads/...`, gitignored). Revisit as object storage (S3-compatible) if the app moves to a host where local disk doesn't persist across deploys, or once there is more than one backend instance.
- Each school maps to its own subdomain (e.g. `greenwood.yourapp.com`) rather than a full custom domain — set via `subdomain` on the school (super admin, or defaults to the lowercased `code`), enforced unique at the DB level (`database/mysql/schema.sql`). True custom-domain support (DNS verification, SSL) is out of scope for now; revisit once the app is actually deployed. There is no real subdomain-based HTTP routing yet (dev runs on `localhost`) — `GET /api/v1/public/schools/{identifier}/site` currently resolves by either `code` or `subdomain`, and the frontend route `/site/:slug` treats `:slug` as that identifier.
- Each school has a `template`: ten real layouts are built (`frontend/src/siteTemplates/`), a new school gets one automatically and the admin can switch in School Site (see "Website templates & marketing done" above).
- **Backend done** (32 pytest tests): a `school_sites` table (one row per `school_id`, with child tables `school_site_banners`/`gallery`/`activities`/`notices` for the list-shaped content) backs `GET/PUT /api/v1/school-site`, `POST /api/v1/school-site/logo`, `POST/DELETE /api/v1/school-site/banners[/{id}]`, `POST/DELETE /api/v1/school-site/gallery[/{id}]`, `POST/DELETE /api/v1/school-site/activities[/{id}]` (all admin-only, scoped to the caller's own school — see `backend/app/modules/school_site/`), plus a public, unauthenticated `GET /api/v1/public/schools/{code_or_subdomain}/site`. Image uploads are validated by content type (JPEG/PNG/WEBP/GIF) and a 5MB limit (`backend/app/modules/school_site/storage.py`); removing a banner or gallery image also deletes its file from disk.
- The admin School Site page and the public site `/site/:code` use this backend (the old in-memory mock is gone).
- The super admin has screens to create schools, switch modules (enforced on the API and in the app's menu), set billing status, and manage the marketing page and demo leads.

## Initial data model

- `schools`: name, unique code, unique subdomain, public site template, enabled feature modules (JSON), billing status, monthly fee, status — the tenant boundary every other table is scoped to via `school_id`
- `users`: identity, role (`super_admin`/`admin`/`teacher`), password hash, account status, and `school_id` (`NULL` for `super_admin`)
- `students`: student identity, class, and parent relationship, scoped to `school_id`
- `teachers`: staff identity, subjects, and class assignments, scoped to `school_id`; links to a `users` row via `user_id`
- `classes`: sections, academic year, and teacher assignment, scoped to `school_id`
- `attendance`: student, class, date, status, and who marked it, scoped to `school_id`
- `school_sites` (+ `school_site_banners`/`gallery`/`activities`/`notices`): the public landing page's content, one `school_sites` row per school, with the list-shaped content (banners, gallery photos, activities, notices) as proper child tables with foreign keys, rather than embedded arrays
- `exams`: subject, schedule, and academic term
- `marks`: student, exam, score, and grade
- `fees`: student, term, amount, payment status, and receipt reference
- `salary`: teacher, month, net amount, and payment status
- `performance`: teacher, period, score, and grade

All of these are built and scoped by `school_id` (performance is computed from exam marks rather than stored).

## Long-term roadmap

A broader SaaS vision was proposed on 2026-09-23 (Next.js/NestJS/PostgreSQL/Prisma/Turborepo, RLS, offline PWA, QR install system, Razorpay billing, 20+ operational modules). Decision: **keep this project's existing stack** (React+Vite, FastAPI, MySQL — per the architecture above, which everything built so far already follows and which the project rules mandate) rather than rewrite it, and **not** adopt Next.js, NestJS, PostgreSQL, Prisma, or Turborepo specifically — our multi-tenant isolation instead relies on the `school_id`-scoping rule stated above, enforced in application code and tests (see the cross-school isolation tests in `backend/tests/`), the SQL equivalent of what that vision called Postgres Row-Level Security. The module list and UX ideas from that vision are folded in below as a long-term roadmap, adapted to our stack; nothing here is scheduled or started yet. Phases 7+ continue the numbering from "Delivery phases" above.

### Phase 7: Admissions & student lifecycle (done, except an application fee)
- Public enquiry/application form feeding into an `enquiries`/`applications` collection, document upload, application fee, admin review/approve/reject, auto-generated admission number, convert to `students`.
- Promotion/transfer between classes and academic years; TC/bonafide/study-certificate PDF generation; ID cards with a QR code per student.

### Phase 8: Installable app & QR-based onboarding
- Make the frontend an installable PWA (manifest, service worker, icons) per school, using a Vite PWA plugin rather than Next.js's app-router-specific tooling.
- An `/install` landing page (branded per school) that detects platform/browser and shows the right install flow (Android `beforeinstallprompt`, iOS "Add to Home Screen" guide, in-app-browser "open in real browser" guide).
- Generate a per-school install QR (general + role-specific), downloadable as a poster PDF; print it on fee receipts and ID cards. Track scan/install funnel events.

### Phase 9: Offline-first operations & QR scanning
- Offline attendance/homework/marks entry (e.g. IndexedDB outbox with client-generated IDs, synced when back online); idempotent sync endpoints.
- A reusable in-app QR/barcode scanner (camera-based) for: student attendance via ID card, staff attendance via a rotating office QR, library issue/return, gate pass/visitor pickup verification, fee-receipt verification.

### Phase 10: Communication & engagement
- Notices/circulars, SMS/WhatsApp/email adapters (provider-agnostic), push notifications (Web Push/VAPID), moderated parent-teacher chat.
- Homework & assignments, study material and class links, simple auto-graded online tests (LMS-lite).

### Phase 11: Operations modules
- Library (catalogue, issue/return via scanner, fines), transport (routes, vehicles, live location, boarding scan, parent alerts), hostel (rooms, allocation, mess), inventory, accounts/ledgers, visitor & gate management, payroll/HR (leave, staff attendance, salary slips).

### Phase 12: Real subscription billing
- Replace the current manual `monthly_fee`/`billing_status` fields with real plans (student/staff limits, feature flags per plan, trial days), a payment gateway integration (e.g. Cashfree) for recurring billing, auto-generated invoices, payment reminders, and grace-period auto-suspend (building on the suspension mechanism already in place).

### Phase 13: Public website builder
- Let a school pick from several real page templates (not just palette variants — see the note on `template` under Phase 6) and edit sections (hero, about, principal's message, faculty, gallery, events, testimonials, contact) without code changes.

### Phase 14: Internationalization, security hardening, and scale
- English/Telugu/Hindi UI translations.
- Security/compliance: stronger audit logging for sensitive actions (marks changes, fee edits, impersonation), India DPDP Act 2023 readiness (consent records, per-tenant data export/delete), encrypted daily backups.
- Observability: structured logging, error tracking, health checks, pagination and performance budgets on all list endpoints.

Explicitly out of scope unless priorities change: native mobile apps (TWA/Play Store packaging), biometric-device hardware integration beyond a webhook boundary, and full ERP breadth (this stays a school management platform, not a generic multi-tenant SaaS framework).

## Definition of done

A feature is complete when its API contract, authorization rules, migration, validation, UI states, tests, and documentation are present. It must work for the intended roles and fail safely for unauthorized requests.

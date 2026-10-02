# ANV College ERP

A multi-college management system by **ANV Soft Solutions**, built on the ANV
School ERP. One platform runs many colleges; each college gets its own admin
console, faculty app, student app, parent app and public website.

In the code and database a college is still called a "school" and a batch a
"class" (tables `schools`, `classes`), so the school and college products share
one codebase; the app shows college terms.

- **Live app:** https://school.anvsoftsolutions.com
- **Super admin (platform owner):** https://school.anvsoftsolutions.com/superadmin
- **API:** https://schoolapi.anvsoftsolutions.com/api/v1 (health check at `/health`)

## Who uses it

| Role | Signs in with | What they do |
|---|---|---|
| **Super admin** (ANV Soft Solutions) | Email, on `/superadmin` only | Creates colleges, switches modules on/off, sets billing, Pro website templates and which payment gateways a college may use, backups, platform earnings |
| **College admin** | Email ("Faculty / Admin" tab) | Everything for their college: departments, faculty, batches, subjects, students, attendance, fees, exams, admissions, payroll, website, payment integration |
| **Faculty / HOD** | Email (mobile app) | Punch in/out, attendance, marks, assignments, remarks, leave, payslips; a HOD also sees their department's day and approves its faculty's leave |
| **Student** | College code + roll number ("Student" tab) | Their own attendance, results with SGPA / CGPA, fees (pay online), assignments, timetable, notices, documents, leave |
| **Parent** | Mobile number ("Parent" tab) | One login for all their children: attendance, results, assignments, notices, fees (pay online or report an offline payment), documents, leave |

Student and parent logins are created from the student's page (or for a whole
batch at once) and print as login slips; the first password must be changed at
first sign-in.

## Features

### College-specific

- **Departments** with a head of department (HOD); faculty, batches and subjects belong to a department
- **Batches:** program (B.Tech, MBA …), semester, section, regulation (R23 …) and a class teacher / mentor
- **Subjects** with credits and type (theory, lab, project, elective), per department and semester
- **Grading:** 10-point scale (O 10, A+ 9, A 8, B+ 7, B 6, C 5, F 0, AB absent); below the pass mark is F.
  **SGPA** per exam (credit-weighted), **CGPA** over published semester-end exams; internal / mid exams don't count towards CGPA.
  Grade sheets show credits, grade points, SGPA, CGPA and credits earned.
- **Student logins** (college code + roll number) with the same portal parents have, limited to their own record
- **Internal + external marks:** a semester-end exam can include internal exams (e.g. mid exams 30 + semester 70 = 100); grade sheets show internal, external and total
- **Backlogs & supplementary exams:** failed / absent subjects are tracked per student and per batch; a supplementary exam lists only students with that backlog, and a pass replaces the F in CGPA
- **Subject-wise attendance:** marked per subject and period by the subject's faculty (web and app); percentages per subject with the 75% rule flagged for students, parents and faculty
- **Faculty** designations (Professor, Assistant Professor …); student email, mobile and admission quota (Convener, Management …)
- **Library:** catalogue with copies, issue / renew / return to students and faculty, loan limit, overdue list and per-day fines
- **Hostel:** hostels (boys / girls), rooms with beds, allocate / move / vacate students; students and parents see the room, roommates and warden
- **Transport:** bus routes with ordered stops and pickup times, seats, drivers; students and parents see their bus and stop
- **Placements:** companies, drives with package, last date, minimum CGPA and eligible departments; students see why they are or aren't eligible and apply; the placement cell shortlists / selects; placed-student stats
- Hostel and transport fees are charged from Fees (types "Hostel", "Transport"); library, hostel, transport and placements are optional modules the super admin switches on per college

### Shared with the school product

- **Students & parents:** records with father/mother/guardian contacts, photos and documents, promotion to the next class
- **Admissions:** public apply page per school (`/apply/<SCHOOL_CODE>`), optional application fee, approve to create the student and parent login
- **Attendance:** students (with parent alerts) and teachers (punch in/out with late marking)
- **Exams & report cards:** subject teachers enter marks; grades, ranks and printable report cards
- **Fees:** fee types, fees for whole classes or chosen students, concessions, receipts, dues
- **Online payments:** each school connects **its own** Razorpay, Cashfree or PhonePe account (money goes straight to the school). A demo gateway is available for demos only.
- **Offline payments:** parents report cash/UPI/bank payments with a screenshot; the school confirms and a receipt is issued
- **Homework, notice board, timetable, holiday calendar, leave, payroll, reports, performance, ID cards & certificates**
- **College website:** 15 college templates (3 free, 12 Pro) with programs, departments, live placements, principal's message and online admissions, edited from the admin console
- **Installable app (PWA):** staff and parents install from a QR code; push notifications
- **Activity log, daily backups, login rate limiting, encrypted gateway secrets**

## Project structure

```
school_management/
├── backend/                     FastAPI REST API (Python 3.11)
│   ├── app/
│   │   ├── main.py              app setup, routers, CORS, migrations on start
│   │   ├── api/                 sign-in (routes/auth.py) and shared dependencies (deps.py)
│   │   ├── core/                config, errors, security (JWT, passwords), rate limit,
│   │   │                        encryption of stored secrets, enabled modules, web push
│   │   ├── db/                  MySQL connection pool, query helpers, migration runner
│   │   ├── integrations/        outside services
│   │   │   ├── gateways.py      one interface for all payment gateways (+ demo gateway)
│   │   │   ├── razorpay.py      Razorpay orders and payment checks
│   │   │   ├── cashfree.py      Cashfree orders, payment checks, webhook signature
│   │   │   ├── phonepe.py       PhonePe Standard Checkout v2
│   │   │   └── sms.py           parent SMS alerts (MSG91, off until configured)
│   │   └── modules/             one folder per feature: router.py (endpoints) + service.py (rules)
│   │       ├── super_admin/     schools, billing, allowed gateways, platform earnings
│   │       ├── students/        student records, guardians, photos, documents
│   │       ├── parents/         parent logins, parent portal, online payments, webhooks
│   │       ├── admissions/      public applications, application fee, approval
│   │       ├── fees/            fee types, student fees, receipts, offline payment claims
│   │       ├── attendance/  staff_attendance/  leave/  exams/  timetable/
│   │       ├── academics/  teaching/  board/ (notices, homework)  certificates/
│   │       ├── payroll/  promotion/  reports/  dashboard/  alerts/
│   │       ├── notifications/  push/  audit/ (activity log)  backups/
│   │       └── school_site/  marketing/ (public school website, landing page)
│   ├── scripts/                 create_super_admin.py, dev_seed.py, demo_seed.py
│   ├── tests/                   pytest suite (one file per feature)
│   ├── passenger_wsgi.py        cPanel entry point
│   ├── requirements.txt         runtime packages (requirements-dev.txt adds test tools)
│   └── .env.example             every setting, documented
│
├── mobile/                      React Native (Expo) app for students, parents and faculty (see mobile/README.md)
├── frontend/                    React + Vite + Tailwind CSS, installable PWA
│   ├── public/                  icons, manifest, service worker
│   └── src/
│       ├── main.jsx, App.jsx    start-up, routes, side menu per role
│       ├── pages/               one screen per menu item (FeesPage, PaymentIntegrationPage,
│       │                        ParentPortalPage, SuperAdminSchoolsPage, LoginPage, …)
│       ├── components/          shared UI (AppShell, Receipt, FeeAccount, StudentFiles, …)
│       ├── api/                 one file per backend area (feesApi.js, parentApi.js, …)
│       ├── lib/                 apiClient.js, payments.js (gateway checkouts), push, install prompt
│       ├── context/             signed-in user (AuthContext)
│       └── siteTemplates/       the 10 public school website designs
│
├── database/
│   ├── mysql/schema.sql         baseline schema (imported once)
│   └── mysql/NNN_*.sql          numbered migrations, applied automatically in order
│
├── docs/
│   ├── PROJECT_PLAN.md          architecture and delivery plan
│   ├── DEPLOYMENT.md            cPanel deployment
│   ├── BACKUPS.md               daily backups and restore
│   └── DEMO_LOGINS.md           demo school accounts
│
├── docker-compose.yml           local MariaDB on port 3307
└── README.md
```

## Running locally

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- MySQL/MariaDB 10.4+, or Docker

### 1. Database

With Docker (MariaDB on port `3307`, schema imported on first start):

```
docker compose up -d mysql
```

Without Docker: create a `school_management` database and import
`database/mysql/schema.sql`. The numbered migrations after it are applied
**automatically** when the backend starts. See [database/README.md](database/README.md).

### 2. Backend

```
cd backend
python -m venv .venv
.\.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
```

In `backend/.env` set at least:

| Setting | Value |
|---|---|
| `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` | your database (defaults match Docker) |
| `JWT_SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATA_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` (needed before a school saves gateway keys) |
| `CORS_ORIGINS` | the frontend URL, e.g. `http://localhost:5173` |

Optional sample data, then start the API:

```
python -m scripts.dev_seed        # a super admin and two sample schools
uvicorn app.main:app --reload
```

- API: http://localhost:8000/api/v1
- Interactive docs: http://localhost:8000/docs

### 3. Frontend

```
cd frontend
npm install
copy .env.example .env            # VITE_API_URL=http://localhost:8000/api/v1
npm run dev
```

Open http://localhost:5173.

### Sample college (local only)

```
cd backend
python -m scripts.college_seed
```

creates **ANV College of Engineering, Kavali** (college code `ANVCOL`): CSE, ECE and MBA departments with HODs,
faculty, three batches, credit subjects, six students with student and parent logins, a published Sem 3 exam
(so SGPA / CGPA show), fees, library books and loans, two hostels, a bus route and placement drives. It prints every login; the main ones:

| Role | Sign in with | Password |
|---|---|---|
| Super admin (at `/superadmin`) | `superadmin@anvcollege.in` | `Super@12345` |
| College admin | `admin@anvcollege.in` | `Admin@12345` |
| Faculty / HOD | `hod.cse@anvcollege.in`, `faculty1@anvcollege.in` … | `Faculty@12345` |
| Student | College code `ANVCOL`, roll number `24A91A0501` | `Student@123` |
| Parent | Mobile `9848000101` | `Parent@123` |

Students and parents are asked to choose a new password at first sign-in.

The older `python -m scripts.dev_seed` (a super admin and two sample schools) still works.

Demo accounts on the live site are listed in [docs/DEMO_LOGINS.md](docs/DEMO_LOGINS.md).

## Mobile app (students, parents, faculty, HODs)

Students, parents, faculty and HODs use one React Native (Expo) app in
[`mobile/`](mobile/), on the same API. The sign-in screen has **Student**, **Parent** and
**Faculty** tabs; the app then shows that role's screens. Admins and office staff
use the website.

| Role | Signs in with | In the app |
|---|---|---|
| Student | College code + roll number | Attendance %, fees due, results with SGPA / CGPA, assignments, notices, timetable, leave, hostel room, bus route, library books, placement drives (apply / withdraw) |
| Parent | Mobile number | The same for each child (switch between children), without placements |
| Faculty | College email | Punch in / out, mark attendance, enter marks, post assignments, approve students' leave, remarks, payslips, timetable, notices, leave |
| HOD | College email | Faculty features plus the department view: faculty present today, batch attendance, students below 75%, approving department faculty's leave |

Run it on a phone (same Wi-Fi as your PC):

```
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

cd mobile
copy .env.example .env        # set EXPO_PUBLIC_API_URL=http://<your-PC-IP>:8000/api/v1
npm install
npx expo start                # scan the QR code with the Expo Go app
```

Play Store builds use EAS (`npx eas-cli@latest build --platform android --profile production`)
and need the live **https** API in `EXPO_PUBLIC_API_URL`. Details, demo logins and
build profiles: [mobile/README.md](mobile/README.md).

## Online payments

1. **Super admin** → Colleges → Edit → tick the gateways the college may use (Razorpay, Cashfree, PhonePe; Demo only for demo colleges).
2. **College admin** → **Payment integration** → choose one gateway, enter the college's own keys, tick "Let parents pay online", Save.
3. Add the webhook URL shown on that page in the gateway's dashboard, so payments are recorded even if the parent closes the page.

A payment is recorded only after the backend asks the gateway itself and it
confirms the right amount. Secret keys are stored encrypted and never sent
back to the browser.

## Tests and build

```
cd backend
pytest                  # uses a separate school_management_test database

cd frontend
npm run build

cd mobile
npx expo export --platform android   # checks the app bundles
```

## Deployment

The cPanel workflow (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)) is manual-only until it is pointed at the college hosting: set `VITE_API_URL` in `.github/workflows/deploy-cpanel.yml` and the `CPANEL_*` secrets, then turn the push trigger back on.
Work happens on `dev`; merge to `main` to release. Backups: [docs/BACKUPS.md](docs/BACKUPS.md).

## 🤝 Contributing

This is a private project of ANV Soft Solutions. Only authorised team members may contribute.

1. Branch from `dev`; never commit straight to `main` (pushing to `main` deploys to the live site).
2. Keep changes small and focused; follow the existing folder and naming style.
3. Add or update tests for business rules, permissions and data changes.
4. Before opening a pull request into `dev`, run `pytest` in `backend/` and `npm run build` in `frontend/`; both must pass.
5. Never commit secrets. Configuration goes in `.env`, documented in `.env.example`.
6. Schema changes are new numbered files in `database/mysql/`. Never edit an applied migration, and never put `;` inside comments there.
7. The server runs Python 3.11: don't reuse the outer quote inside an f-string's `{…}` (checked by `tests/test_python311_syntax.py`).
8. Keep API responses backwards compatible; the installed apps may be on an older version.

See [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for the architecture and delivery plan.

## 📄 License

Proprietary. Copyright © 2026 ANV Soft Solutions. All rights reserved.

This software and its source code may not be copied, modified, distributed or used without written permission from ANV Soft Solutions. See [LICENSE](LICENSE).

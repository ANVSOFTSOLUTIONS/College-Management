# Demo logins (ANV School ERP)

For showing the product to schools. These accounts belong to the **ANV Demo
School** (school code `ANVDEMO`), which holds sample data only. Checked on
the live site on 2026-09-28.

**App:** https://school.anvsoftsolutions.com/login

The login page has two tabs: **Parent** and **Staff / Admin**. Students don't
sign in: parents see everything for their children (attendance, marks, fees,
homework, notices), pay fees, upload documents and apply for leave.
Admins, teachers and staff all use the **Staff / Admin** tab with their email.

| Role | Link | Tab | Login | Password |
|---|---|---|---|---|
| Super admin | https://school.anvsoftsolutions.com/superadmin (its own page; the school sign-in refuses it) | — | `admin@anvsoftsolutions.com` | *not stored in git* (see below) |
| School admin | https://school.anvsoftsolutions.com/login?as=admin | Staff / Admin | `demo-admin@example.com` | `Demo@2026` |
| Teacher (Lakshmi Narayana, Grade 1 class teacher) | https://school.anvsoftsolutions.com/login?as=staff | Staff / Admin | `demo-teacher1@example.com` | `Demo@2026` |
| Staff (Priya Sharma) | https://school.anvsoftsolutions.com/login?as=staff | Staff / Admin | `demo-teacher2@example.com` | `Demo@2026` |
| Parent (Ramesh Rao, father of Ananya Rao, Grade 1) | https://school.anvsoftsolutions.com/login?as=parent | Parent | mobile `9800010011` | *reset before a demo* (see below) |

More demo teachers: `demo-teacher3@example.com` to `demo-teacher6@example.com`, password `Demo@2026`.

## Notes

- **Super admin password** is deliberately left out of git: that account
  controls every school on the platform, and anything committed stays in the
  repository's history. The owner keeps it privately.
- **Staff** is not a separate role: teachers are the staff (Punch In/Out,
  Leave, My payslips), so the staff demo is another teacher account.
- **Parent:** the password is random and the first sign-in asks for a new
  one. Before a demo, sign in as the school admin → Students → Ananya Rao →
  Parent login → reset; the new password is shown once.
- **Admissions:** parents apply without a login at
  https://school.anvsoftsolutions.com/apply/ANVDEMO. Approving an application
  makes the parent's login.
- These are demo accounts: don't enter real student or parent data in the
  demo school.

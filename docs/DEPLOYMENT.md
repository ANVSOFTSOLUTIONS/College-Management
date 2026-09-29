# Deploying to cPanel via Git Version Control

cPanel clones this repo directly on its own server (cPanel → **Git™ Version
Control**). Deploying runs `.cpanel.yml` at the repo root, which builds the
files into place. On every push to `main`, the GitHub Action
(`.github/workflows/deploy-cpanel.yml`) builds the frontend on GitHub —
shared hosting's memory limit kills `npm run build` on the server — commits
the result with `backend/` to the `deploy` branch, then tells cPanel to pull
`deploy` and run `.cpanel.yml`. The cPanel repository must track `deploy`,
never `main` (`.cpanel.yml` refuses to run without `frontend/dist`).

The backend now runs on MySQL end-to-end (converted from MongoDB on
2026-09-23 — see `docs/PROJECT_PLAN.md`), matching what cPanel/phpMyAdmin
actually supports. `database/mysql/schema.sql` is the full schema, tested
against both a throwaway MariaDB instance and the real app (32 passing
tests, plus live curl/browser smoke tests). What's still missing before a
real deploy: your actual server credentials filled into `.cpanel.yml` and
the Python App's environment variables (steps below) — none of that can be
done for you.

## 1. cPanel setup (one-time)

### Backend — Setup Python App
1. cPanel → **Setup Python App** → Create Application.
   - Python version: 3.11+.
   - Application root: a fresh directory outside `public_html`, e.g. `school_backend`.
   - Application URL: e.g. `api.yourdomain.com`.
   - Application startup file: `passenger_wsgi.py`
   - Application Entry point: `application`
2. Note the **activation command** cPanel shows you — it contains a path like
   `/home/youruser/virtualenv/school_backend/3.11/bin`. You'll need it for `.cpanel.yml`.
3. In the app's **Configuration files / Environment variables** section, add
   every variable from `backend/.env.example`, with your real MySQL
   credentials (see step 3 below) and a freshly generated `JWT_SECRET_KEY`
   (`python -c "import secrets; print(secrets.token_hex(32))"` — never reuse
   the local dev one). Before any school turns on Cashfree online payments, also add a
   `DATA_ENCRYPTION_KEY` (see `.env.example` for the one-line generator); it
   encrypts the school's Cashfree secret key in the database. Keep it
   unchanged afterwards, or saved secrets have to be entered again.

### Frontend — static files
Decide where the built frontend serves from: `public_html` (main domain) or
a subdomain's document root (cPanel → **Subdomains**). Note that path.

### Database
1. cPanel → **MySQL® Databases** → create a database and a user, add the
   user to the database with all privileges. cPanel prefixes both names with
   your account username (e.g. `youruser_school_management`) — that's normal.
2. phpMyAdmin → select that database → **Import** → `database/mysql/schema.sql`.
   That's the only manual import: later numbered migrations (`database/mysql/NNN_*.sql`)
   are applied automatically by the backend on its first request after a deploy.

## 2. Connect the repo

1. If this repo is **private**: generate a deploy key
   (`ssh-keygen -t ed25519 -C "cpanel-deploy" -f cpanel_deploy_key`), add the
   `.pub` half to GitHub (repo → **Settings → Deploy keys**), and import the
   private half into cPanel → **SSH Access → Manage SSH Keys**.
2. cPanel → **Git™ Version Control** → **Create**:
   - Clone URL: `git@github.com:yourname/yourrepo.git`
   - Repository Path: a fresh folder outside `public_html`, e.g. `/home/youruser/repositories/school_management`
3. Open `.cpanel.yml` in this repo and replace `CPANEL_USERNAME` (3 places)
   and double-check the two paths match what you used in **Setup Python App**
   and for the frontend's document root. Set `VITE_API_URL` in
   `.github/workflows/deploy-cpanel.yml` to the live API URL — it is baked into the
   frontend at build time. Commit and push.
4. Add the frontend domain to the backend's `CORS_ORIGINS` environment
   variable in **Setup Python App**, or the browser will block API calls.

## 3. Deploying

### Automatic (push to `main`)
One-time setup:
1. cPanel → **Security → Manage API Tokens** → Create a token (e.g. `github-deploy`).
   Copy it — cPanel shows it only once.
2. GitHub repo → **Settings → Secrets and variables → Actions** → add:

   | Secret | Example |
   |---|---|
   | `CPANEL_HOST` | `yourdomain.com` (the host you open cPanel on, without `:2083`) |
   | `CPANEL_USER` | your cPanel username |
   | `CPANEL_API_TOKEN` | the token from step 1 |
   | `CPANEL_REPO_ROOT` | `/home/youruser/repositories/school_management` |

After that, every push/merge to `main` pulls the new commit on cPanel and runs
`.cpanel.yml`. Check the run under the repo's **Actions** tab; the build log
on the server is under `~/.cpanel/logs/` (path is printed in the Action output).
You can also re-run it manually from **Actions → Deploy to cPanel → Run workflow**.

### Manual fallback
cPanel → **Git™ Version Control** → your repo → **Manage** → **Pull or Deploy**:
**Update from Remote**, then **Deploy HEAD Commit**. This only works with the
`deploy` branch checked out, after the GitHub Action has built it at least once.

### Frontend API URL
`VITE_API_URL` is set in `.github/workflows/deploy-cpanel.yml` and baked into
the frontend bundle at build time. Change it there if the API domain changes.

## 4. Uploaded files

`backend/uploads/` (school logos/banners/gallery) and `backend/private_uploads/`
(student photos and documents) are excluded from the deploy's rsync on purpose — a deploy must never wipe files real schools have
uploaded. Back both directories up separately; they are not in version control.

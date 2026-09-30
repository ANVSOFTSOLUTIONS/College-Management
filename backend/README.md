# Backend

FastAPI REST API with asynchronous MySQL/MariaDB access through `aiomysql`
(raw parameterized SQL, no ORM — kept consistent with the rest of the
codebase's style).

- `app/core/`: environment/service configuration, password hashing + JWT, the shared error response shape, and the login rate limiter
- `app/api/`: routers, auth dependencies (`deps.py`), and the `auth` login route
- `app/modules/`: domain routers, services, and schemas (`attendance`, `school_site`, `super_admin`)
- `app/integrations/`: PDF, messaging, email, and biometric adapters (not yet implemented)
- `app/db/`: MySQL connection pool (`database.py`) and small query helpers (`helpers.py`: `fetch_one`/`fetch_all`/`execute`)
- `tests/`: pytest suite against a real MySQL/MariaDB, using a separate `school_management_test` database
- `uploads/`: local-disk storage for uploaded images (gitignored), served at `/uploads/...`
- `passenger_wsgi.py`: entry point for cPanel's "Setup Python App" (Passenger) — bridges FastAPI (ASGI) to WSGI via `a2wsgi`. See `../docs/DEPLOYMENT.md`.

## Setup

```
python -m venv .venv
./.venv/Scripts/pip install -r requirements-dev.txt   # or requirements.txt for runtime only
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into .env as JWT_SECRET_KEY
```

Requires a running MySQL/MariaDB server — fill in `MYSQL_HOST`/`PORT`/`USER`/`PASSWORD`/`DATABASE`
in `.env` to match it. Then import `../database/mysql/schema.sql` into that
database (see `../database/README.md`).

Optionally seed local dev data (a super admin, plus two sample schools each with an admin + teacher + class + students; no-op if a school already exists):

```
./.venv/Scripts/python -m scripts.dev_seed
```

## Run

```
uvicorn app.main:app --reload
```

## Test

```
pytest
```

Tests use their own `school_management_test` database (set via `MYSQL_DATABASE`
in `tests/conftest.py`, same server/credentials as dev otherwise) and never
touch dev data — table contents are cleared between tests, not the schema
itself, so import `schema.sql` into the test database once too.

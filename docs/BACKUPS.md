# Backups

What gets backed up, how to switch on the daily schedule, and how to restore.

## What is backed up

| Backup | When | Kept | File |
|---|---|---|---|
| Database (all schools: students, marks, fees, attendance…) | daily | last 14 | `db-YYYYMMDD-HHMMSS.sql.gz` |
| Uploaded files (logos, banners, photos, documents, attachments) | weekly | last 4 | `files-YYYYMMDD-HHMMSS.tar.gz` |

They are written to `~/school_backups` on the server (outside the website
folders, so they can't be downloaded from the web). The super admin sees them
under **Backups**, can run one with **Back up now**, and can download them.

Backups on the same server don't survive losing the server. **Download the
latest database backup at least once a week** and keep it somewhere else
(Google Drive, a USB drive), or also switch on cPanel's own backups.

## Switch on the daily schedule (one time)

The backup runs inside the API, which already has the database login; a cron
job only calls it with a secret token.

1. Make a token (any long random text), for example with
   `python -c "import secrets; print(secrets.token_hex(24))"`.
2. cPanel → **Setup Python App** → the school backend → **Environment
   variables** → add `BACKUP_TOKEN` = that token → Save → **Restart**.
3. cPanel → **Cron Jobs** → Add New Cron Job: once per day at a quiet hour
   (e.g. minute `30`, hour `2`), command:

   ```
   curl -fsS -X POST -H "X-Backup-Token: YOUR_TOKEN" "https://schoolapi.anvsoftsolutions.com/api/v1/internal/backups/run?kind=auto" > /dev/null
   ```

   `kind=auto` backs up the database every day and the files once a week.
4. Check it the next day: super admin → **Backups** shows a backup less than a
   day old. The page turns red if the newest database backup is over 36 hours old.

If a backup fails with "mysqldump" not found, add the environment variable
`MYSQLDUMP_PATH=/usr/bin/mysqldump` (the usual cPanel location) and restart.

## Restore

Restoring replaces the current data with the backup's. Take a fresh backup
first, and put the school apps in maintenance (or do it at night).

**Database** (cPanel → Terminal):

```
cd ~/school_backups
gunzip -c db-20260928-023000.sql.gz | mysql -u DB_USER -p DB_NAME
```

(or cPanel → phpMyAdmin → the database → Import, after unzipping the `.gz`).

**Uploaded files** (cPanel → Terminal):

```
cd ~/school_backend
tar -xzf ~/school_backups/files-20260928-023000.tar.gz
```

This restores the `uploads/` and `private_uploads/` folders. Then restart the
Python app.

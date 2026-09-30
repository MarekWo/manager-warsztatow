# Configuration

Two layers configure an installation:

1. **Environment variables** (`.env` next to the Compose files, or the container environment) —
   what the operator sets once per server: secrets, the public address, the fallback mail
   transport. Values already present in the environment win over `.env`.
2. **Settings in the panel** (**Panel → Ustawienia**) — what the organiser changes: organisation
   details, logo, bank account, consent texts, outgoing SMTP, e-mail templates, workshop types
   and form templates. They live in the database and are covered by backups.

`.env.example` lists every variable with a comment; this page explains them in groups.

## Core

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | — (required on servers) | Signs sessions, CSRF tokens, sign-in links and the withdrawal and unsubscribe links in e-mails. Changing it signs everybody out and invalidates links already sent. |
| `FIELD_ENCRYPTION_KEY` | derived from `SECRET_KEY` | Fernet key for secrets stored in the database (the SMTP password). Changing the key in use makes the stored password unreadable — re-enter it in Settings. |
| `SITE_URL` | `http://localhost:8000` | The public address without a trailing slash. Used for absolute links in e-mails and Open Graph tags; its host is always allowed. |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | empty | Extra names only (e.g. an internal address used by monitoring). |
| `SITE_NOINDEX` | `false` | `true` on TEST: every response says `X-Robots-Tag: noindex, nofollow`. |
| `TIME_ZONE` | `Europe/Warsaw` | Dates on pages, in e-mails and the cron times of periodic jobs. |
| `DEBUG` | `false` | Never on a server. |

## First administrator

`ADMIN_EMAIL` — created on every start if missing (`ensure_admin`), with no password: the
administrator signs in with a code sent to this address. Make sure mail works before the first
sign-in. Further administrators are created by the operator in the technical admin
(`/django-admin/`, *Użytkownicy*: tick *Status administratora*); they sign in with a code too.

## Data

| Variable | Default | Notes |
|---|---|---|
| `DATA_DIR` | `./data` (`/data` in containers) | The SQLite database, `media/` (public uploads: logo, workshop photos) and `private/` (message attachments, never served by the edge). |
| `DATABASE_URL` | `sqlite:///$DATA_DIR/db.sqlite3` | SQLite is the supported database (ADR-0002). |
| `MEDIA_ROOT`, `STATIC_ROOT` | under `DATA_DIR` / the image | Rarely changed. |
| `CACHE_URL` | `dbcache://django_cache` | A table shared by all processes, so rate limits count across gunicorn workers. |

## E-mail

| Variable | Default | Notes |
|---|---|---|
| `EMAIL_URL` | `consolemail://` | The fallback transport, e.g. `smtp+tls://user:password@smtp.example.com:587`. Used when SMTP in the panel is switched off, and for sign-in codes before anything is configured. |
| `DEFAULT_FROM_EMAIL` | `Manager Warsztatów <noreply@localhost>` | Sender for the fallback transport. |

SMTP entered in **Ustawienia → Poczta wychodząca** takes precedence when switched on. The
password is encrypted in the database; the sender name, address and Reply-To are set there too.
All e-mails except sign-in codes go through a queue in the database and are sent by the worker
with retries (1, 5, 15, 60, 180 and 360 minutes after failures).

## Sessions

| Variable | Default | Notes |
|---|---|---|
| `SESSION_REMEMBER_DAYS` | `180` | "Zapamiętaj mnie" for participants — days since the last visit. |
| `STAFF_SESSION_REMEMBER_DAYS` | `30` | The same for administrators. |

Without "Zapamiętaj mnie" the session ends with the browser.

## Reverse proxy and security

Set by `compose.prod.yaml`; change them only when the proxy setup differs.

| Variable | Default on servers | Notes |
|---|---|---|
| `TRUST_PROXY_HEADERS` | `true` | Read the scheme and the visitor's address from the proxy's headers. |
| `CLIENT_IP_HEADER` | `X-Real-IP` | The header the edge sets. Never `X-Forwarded-For`, which a client can prepend to. |
| `CSP_ENFORCE` | `true` | `false` is the break-glass switch back to report-only Content Security Policy. |
| `SECURE_HSTS_SECONDS` | `3600` | Raise once PROD has run on its final domain for a while. |
| `SECURE_COOKIES` | `true` | Cookies only over HTTPS. |
| `SECURE_SSL_REDIRECT` | `false` | The proxy redirects HTTP to HTTPS. |

## Background tasks and logging

| Variable | Default | Notes |
|---|---|---|
| `TASK_WORKERS` | `1` | Worker processes in the `worker` container; one is plenty. |
| `TASK_SYNC` | `false` | Run tasks inline (tests only). |
| `LOG_LEVEL` | `INFO` | Logs go to stdout: `docker compose logs web worker`. |

Periodic jobs (created by `ensure_schedules` on every start, cron in `TIME_ZONE`): a heartbeat and
the e-mail queue every minute, the organiser's daily digest at 19:00, clearing expired sessions
at 3:10 and pruning task results at 3:20.

## Compose and servers

| Variable | Notes |
|---|---|
| `COMPOSE_FILE` | TEST `compose.yaml:compose.prod.yaml`; PROD adds `:compose.npm.yaml`. On Windows the separator is `;`. |
| `APP_TAG` | Image tag: `dev` on TEST, `X.Y.Z` on PROD (written by `scripts/update.sh`). |
| `EDGE_BIND`, `EDGE_PORT` | Where the Caddy edge listens (`127.0.0.1:8080` by default; TEST `0.0.0.0:80` for the tunnel). |
| `PROXY_NETWORK` | PROD: Nginx Proxy Manager's Docker network. |
| `BACKUP_KEEP_DAYS`, `BACKUP_RSYNC_TARGET`, `BACKUP_RCLONE_REMOTE`, `BACKUP_PING_URL` | Read by `scripts/backup.sh` — see [deploy.md](deploy.md#backups). |

## Start-up commands

The `web` container runs, on every start: migrations, `createcachetable`, `ensure_admin`,
`seed_defaults` (workshop types, the default location, form templates, e-mail templates — only
what is missing, never overwriting edits) and `ensure_schedules`. All are idempotent.

`seed_demo` adds three demonstration workshops with made-up people (`@example.com`). It is for
DEV and screenshots only — never run it on a server with real data.

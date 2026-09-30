# Architecture

Manager Warsztatów is a server-rendered Django application for one organiser: a public site with
workshops and application forms, participant pages, and an administrator's panel. It is sized
for about ten workshops a year with up to thirty people each, and for a small server (≈ 200 MB of
RAM for the whole stack).

```
                ┌──────────────────────────────── one image ───────────────────────────────┐
Internet ─► proxy (TLS) ─► edge (Caddy) ─► web (gunicorn + Django) ─┐                         │
                          │  /media/ from the volume                ├─► SQLite (WAL) in /data │
                          │                  worker (django-q2) ────┘   media/ · private/     │
                └──────────────────────────────────────────────────────────────────────────┘
```

## Processes

- **web** — gunicorn with Django. On start it runs migrations and the idempotent start-up
  commands (`ensure_admin`, `seed_defaults`, `ensure_schedules`).
- **worker** — `manage.py qcluster` (django-q2 with the ORM broker, so no Redis). It sends the
  e-mail queue every minute, the organiser's daily digest, and nightly clean-ups. Code enqueues
  work only through `workshop_manager.core.tasks` (`enqueue`, `enqueue_on_commit`, `schedule`).
- **edge** — Caddy: serves `/media/` straight from the volume and proxies the rest to `web`,
  passing the visitor's address in `X-Real-IP`. TLS ends earlier (Nginx Proxy Manager on PROD,
  a Cloudflare tunnel on TEST).

## Data

SQLite in WAL mode with `IMMEDIATE` transactions (ADR-0002): readers never wait for the writer,
and two writers queue at `BEGIN` instead of failing halfway. Everything the application writes
is under `DATA_DIR`: `db.sqlite3`, `media/` (public uploads) and `private/` (message attachments,
outside the edge's reach). Backups take SQLite's online backup plus both directories.

## Packages

| Package | Responsibility |
|---|---|
| `core` | Site settings (singleton), consents text, the event log (`AuditEvent`, `audit.record`), rate limits, middleware, tasks, error pages, `/healthz`. |
| `accounts` | E-mail user model, sign-in by one-time code and one-click link (django-allauth, ADR-0001), "remember me", linking accounts to past applications. |
| `workshops` | Types, locations, workshops, sessions and levels. Publication and registration state are computed from dates on every request — no job publishes anything. |
| `forms_builder` | Questions of a workshop's form and reusable templates (copied into a workshop, never linked). |
| `applications` | Participants, applications with a snapshot of contact data and answers, the status machine (`decisions.py`: transitions, waiting list, history), tokens for e-mail links, GDPR (`gdpr.py`: consent register, data copy, anonymisation). |
| `communications` | E-mail templates, the queue/log (`EmailMessage`) with retries, rendering (plain text → placeholders → escaped HTML), notifications, messages to participants. |
| `exports` | Excel export, printouts and PDF (WeasyPrint), materials summary. |
| `public` | The public site and the participant's pages. |
| `panel` | The administrator's panel. |
| `help` | The in-app help (chapters as templates) and the participants' "Jak to działa" page. |

## Design choices

- **State from dates.** A workshop is a draft, scheduled, published or finished according to its
  dates at the time of the request, so "publish at 9:00" needs no scheduler and cannot be missed.
- **Snapshots.** An application keeps the name, address and answers — with each question's wording
  — as sent. Later edits of a form or a person's details never rewrite what was submitted.
- **One way to change an application.** Every status change goes through
  `applications.decisions`, which checks the transition, keeps the waiting list numbered, writes
  the history and the event log, and queues the decision e-mail in the same transaction.
- **E-mail never blocks.** Messages are rows written in the transaction that caused them; the
  worker sends them after the commit and retries failures. Sign-in codes are the only e-mails
  sent synchronously and not stored.
- **Deletion is anonymisation.** Removing a person clears every personal field (applications,
  answers, notes, e-mails, event log) but keeps anonymous applications, so a workshop's numbers
  stay right.
- **No build step.** Django templates, HTMX and Bootstrap served from `static/vendor/`; no CDN,
  no Node, no third-party requests (PRD §8). A strict Content Security Policy is enforced on
  servers; inline scripts and styles carry the request's nonce.
- **Polish in the UI, English in the code** (ADR-0003): UI strings are written in Polish
  directly; there is no gettext catalogue.

## Security

Sign-in without passwords (codes and single-use links, rate-limited per address and IP, no
account enumeration), HTTPS with HSTS, secure cookies, CSRF, CSP, `X-Frame-Options: DENY`, a
Permissions-Policy, the SMTP password encrypted at rest, uploads of attachments kept private,
formula escaping in Excel exports, and the event log of every change in the panel.

## Tests

pytest with factory-boy and time-machine. Browser tests (Playwright + axe, `-m browser`) cover
the main flows on a phone-sized screen and sweep every page for accessibility and sideways
scrolling. CI runs lint, formatting, migrations check, mypy, unit and browser tests, and
`pip-audit`, then publishes the image to GHCR.

# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Each release lists what an operator must do in an
**Upgrading** section.

## [Unreleased]

### Changed

- Question lists in the form editor and in form templates show their buttons in a row under the
  question and its badges, all as icons (move up/down, edit, hide/show, delete) with tooltips and
  screen-reader labels. The reserve list's buttons also moved under the person's name.

## [1.0.0-rc1] - 2026-09-30

Release candidate for acceptance tests on TEST.

### Added

- Project foundation: Django 6.1 on Python 3.13 managed by uv, SQLite in WAL mode, settings
  split into `base`/`dev`/`prod`/`test` with fail-fast environment parsing.
- Email-based user model; sign-in with a six-digit one-time code (django-allauth), "remember me
  on this device" (180 days for participants, 30 for administrators), no passwords.
- `ensure_admin`, `seed_defaults` and `ensure_schedules` start-up commands.
- Background worker (django-q2, ORM broker) with a heartbeat reported by `/healthz`.
- Public home page with the "no workshops are planned" notice; administrator panel placeholder.
- Docker image (multi-stage, non-root), Compose files for DEV (with Mailpit), TEST and PROD
  (Caddy edge, optional Nginx Proxy Manager network).
- CI (lint, format, migrations, types, tests, dependency audit) and GHCR image publishing.
- Workshops: types, reusable locations, sessions (dates and hours), levels with their own
  capacity and price, optional sections (organisational notes, programme, what to bring,
  accommodation, photo), cancellation.
- Publication and registration window computed from dates at request time: a workshop scheduled
  for 9:00 is public at 9:00 with no background job; manual "close registration now".
- Application form configuration: default templates (the questions of the former Word form,
  with board orders bound to the beginners' and advanced levels), per-workshop questions (text,
  yes/no, single/multiple choice, material order), ordering, hiding, standard fields
  (phone, adult confirmation, remarks) required/optional/hidden.
- Administrator panel: dashboard, workshop list by state, create from a type, edit with
  sessions and levels added in place (HTMX), duplicate with dates moved to a new first session,
  delete drafts, archive, locations.
- Public home page listing current workshops; workshop page with sessions in Polish, levels and
  prices, location and sections; staff preview of drafts.
- Public application form built from the workshop's configuration: level choice (with a notice
  when a level already has more applications than places), contact details, the workshop's
  questions (those bound to another level are hidden and ignored), remarks, adult confirmation,
  privacy consent (stored with its version) and an optional consent to news about workshops.
- Spam protection without a CAPTCHA: a honeypot field, a signed minimum fill-in time and a limit
  of applications per hour from one address; one live application per person and workshop.
- Thank-you page with a summary of what was sent; details pre-filled for signed-in users.
- Levels, questions and draft workshops that already have applications cannot be deleted.
- Browser tests (Playwright) with automated accessibility checks (axe) on public and panel
  pages, run in CI with the Content Security Policy enforced.
- Settings page in the panel: organisation details and logo (shown in the header and in
  e-mails), bank account, consent texts (a changed wording becomes a new version), outgoing
  SMTP server with the password stored encrypted, sender and Reply-To, administrator
  notifications, and a test e-mail that reports the server's answer.
- E-mail queue and log: every e-mail is written together with the change that caused it and
  sent by the worker; failures are retried with a growing delay (about ten hours in all), shown
  with the server's error in the panel's e-mail log and can be sent again. Saving corrected SMTP
  settings retries waiting e-mails at once. An SMTP outage never blocks an application.
- Editable e-mail templates (plain text with placeholders such as `{imie}`, `{warsztat}`,
  `{terminy}`, `{odpowiedzi}`), a preview with example data and "restore default"; HTML e-mails
  with a simple layout and a plain-text part.
- Confirmation e-mail to the applicant with a copy of the application, and a notification to
  the organiser — immediately or as a daily summary at 19:00.
- Dictionaries in Settings: workshop types (default levels and questions, switching off) and
  form templates with their questions.
- Reviewing applications: a list for all workshops and one per workshop (filters by status and
  level, search by name or e-mail, "not yet seen"), application details with the answers,
  consents, the person's other workshops, the history of changes and private notes.
- Decisions — accept, waiting list, reject, cancel, record a withdrawal — checked against the
  allowed transitions, each with a window showing the participant's e-mail, editable before
  sending, and the option not to send it; bulk decisions with the template e-mail.
- Waiting list per level, numbered and reorderable; when an accepted person leaves, the first
  person waiting on that level is suggested (never promoted automatically).
- Applications added by the administrator (made by phone), with or without a confirmation
  e-mail; correcting contact details and changing the level, both recorded in the history.
- Dashboard counters per level against the limit (with a warning above it), unseen
  applications, failed e-mails, missing mail configuration and workshops about to be published.
- Event log in the panel: who changed what and when (decisions, workshops, settings,
  templates, dictionaries).
- New e-mail templates: acceptance, waiting list (with the place on the list), rejection,
  cancellation and withdrawal confirmation. The organiser's notification now links to the
  application in the panel.
- `seed_demo` command with demonstration workshops and applications for DEV and TEST.
- Server scripts: `backup.sh` (consistent SQLite online backup, uploads, manifest and
  checksums, retention, optional rsync/rclone copy and monitor ping), `restore.sh` (a drill
  that changes nothing, or a full restore) and `update.sh` (backup, pull, healthy start, the
  way back on failure); daily systemd timer documented in `docs/deploy.md`.
- Participant accounts: anyone who has applied signs in with a code (the account is created at
  the code request, and every application from that address becomes theirs); an unknown address
  gets no account and the page does not reveal which is which. Codes are limited to one a
  minute and five an hour per address.
- One-click sign-in link next to the code, valid 15 minutes and only once, signing in on a
  button press so mail programs that check links cannot use it up.
- Sign-in e-mails in Polish with the code in the subject, signed with the organisation's name.
- "Moje warsztaty": current and past applications with statuses as participants read them,
  details, and withdrawing with an optional reason; "Moje dane" with the consent to news about
  workshops. The thank-you page offers to remember the details (sends a code).
- Withdrawal link in e-mails, for guests too (`{link_rezygnacji}`, also `{link_do_konta}`);
  a withdrawal confirms to the participant, notifies the organiser at once with the first person
  waiting on that level, and marks the application unseen.
- Messages to a workshop's participants: accepted, waiting list, everyone active, the accepted
  on one level, or people ticked on the application list; placeholders per person, an optional
  attachment (up to 5 MB, kept in private storage, never public), a preview with the recipient
  list before anything is sent, one e-mail per person in the e-mail log.
- Excel export of a workshop's applications (accepted, active or all), one column per question;
  cells that could run as formulas are kept as text.
- Printouts as a page to print and as PDF (WeasyPrint): attendance list (accepted per level,
  a signature column per session, A4 landscape), contact list, materials summary (accepted and
  waiting counted apart, with names); filter by material order on the application list.
- Error pages in Polish (404, 403, 400, 500 and an expired-form page instead of Django's CSRF
  failure page), a favicon and home-screen icon, page descriptions and Open Graph tags (the
  workshop's subtitle and photo when shared).
- GDPR (PRD §8): a consent register (privacy and marketing consents with their wording,
  version, channel and time; existing applications backfilled); the participant downloads a copy
  of their data (JSON), withdraws the marketing consent in "Moje dane" or with the one-click
  unsubscribe link (`{link_wypisu}` placeholder), and deletes their account ("Usuń moje konto").
  Panel "Uczestnicy": people register with search, a person's card (applications from every
  workshop, consent history), a full data copy for the organiser, and anonymisation — names,
  addresses, phone, remarks, answers, notes, comments, e-mails and log entries are removed while
  the anonymous applications keep the numbers; blocked while the person still holds or waits for
  a place in a workshop that has not ended.
- In-app help in Polish (PRD §7.10): eleven chapters for administrators (first steps, workshops,
  the form, reviewing applications, participants, messages, printouts, mail, settings, GDPR,
  FAQ) with screenshots from the demo data, a "?" next to harder sections of the panel that opens
  the right place in a new tab, and a "Jak to działa" page for participants linked in the footer.
  `uv run pytest -m screenshots` retakes the screenshots.
- Documentation: `docs/configuration.md`, `docs/architecture.md`, `docs/admin-guide.md`.

### Fixed

- The workshop's own questions in the application form had no Bootstrap styling; on a phone a
  long-answer field was wider than the screen.
- Heading order on the workshop list, keyboard access to the scrolling e-mail and event log
  tables, long addresses widening the printouts on a phone.

- A mail server that refuses connections no longer turns "Wyślij mi kod" into a server error:
  the sign-in page says to try again later (and shows form-wide errors at all).

### Tests

- Accessibility and phone-width sweep over every public, participant and panel page with the
  demo data (axe without serious findings, no sideways scrolling at 360 px; `AUDIT_ALL=1` also
  fails on moderate and minor findings) and a keyboard check that every control shows focus.

### Upgrading

- Backups now archive `/data/media` and `/data/private` (message attachments) together;
  `restore.sh` expects that layout — take a fresh backup after updating.

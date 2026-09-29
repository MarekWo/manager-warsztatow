# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Each release lists what an operator must do in an
**Upgrading** section.

## [Unreleased]

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

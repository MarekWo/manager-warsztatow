# Manager Warsztatów

A web application for signing up to art workshops (such as icon-painting retreats) and managing
the applications. Built for the Christian Association of Sacred Art Creators "Ecclesia" in
Kraków; open source under the MIT licence.

The user interface is in Polish. Code, comments and technical documentation are in English.

## What it does

- **Participants** browse current workshops and apply from any device — without an account, or
  signed in with a six-digit code sent by email (no passwords). Signed-in participants get their
  details pre-filled and see the history and status of their applications.
- **Administrators** create workshops (dates, levels with their own capacity and price, optional
  sections, a configurable application form), schedule their publication, review applications
  (accept, wait-list, reject — with an email to the applicant), message participants, and print
  or export lists.
- **Personal data** is handled as GDPR asks: consents are recorded with their wording and
  version, people download a copy of their data or delete their account (anonymisation), and
  the news consent is withdrawn with one click. Built-in help in Polish guides the organiser.

The project is under active development; see [CHANGELOG.md](CHANGELOG.md).

## Stack

Django 6.1 · Python 3.13 (managed by [uv](https://docs.astral.sh/uv/)) · SQLite (WAL) ·
django-allauth (email code sign-in) · django-q2 (background worker, ORM broker) · HTMX ·
Bootstrap 5 (bundled, no Node build) · WeasyPrint · Docker.

## Development

Requirements: [uv](https://docs.astral.sh/uv/) and, for the container stack, Docker.

```bash
uv sync                                   # Python 3.13 and all dependencies into .venv
cp .env.example .env                      # then set ADMIN_EMAIL to your address
uv run python manage.py migrate
uv run python manage.py createcachetable
uv run python manage.py ensure_admin
uv run python manage.py runserver
```

Emails (including sign-in codes) are printed to the console by default
(`EMAIL_URL=consolemail://`).

The Docker DEV stack runs the same code with autoreload, a worker and
[Mailpit](https://mailpit.axllent.org/) at <http://localhost:8025> to read the emails:

```bash
docker compose up --build
```

### Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
uv run mypy workshop_manager
uv run pytest
uv run playwright install chromium    # once
uv run pytest -m browser              # browser and accessibility tests
```

Install the git hooks once with `uv run pre-commit install`.

## Deployment

Servers pull the image `ghcr.io/marekwo/manager-warsztatow` (`:dev` for TEST, `:X.Y.Z` for
production) and run it with `compose.yaml` + `compose.prod.yaml` (a Caddy edge in front of
gunicorn), adding `compose.npm.yaml` behind Nginx Proxy Manager. See [docs/deploy.md](docs/deploy.md).

## Documentation

- [docs/deploy.md](docs/deploy.md) — servers, updates, backups and restore
- [docs/configuration.md](docs/configuration.md) — environment variables and panel settings
- [docs/architecture.md](docs/architecture.md) — processes, data, packages and design choices
- [docs/admin-guide.md](docs/admin-guide.md) — the operator's tasks; the organiser's guide is
  the in-app help (in Polish) at `/panel/pomoc/`

## Licence

[MIT](LICENSE). Bundled third-party assets are listed in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

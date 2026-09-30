# Deployment

Manager Warsztatów runs as three containers from one Compose project:

| Service | What it does |
|---|---|
| `web` | gunicorn serving Django; runs migrations and start-up commands (`RUN_MIGRATIONS=true`) |
| `worker` | `manage.py qcluster` — emails and periodic jobs (django-q2, ORM broker) |
| `edge` | Caddy: serves `/media/` from the data volume, proxies everything else to `web` |

All state lives in the `data` volume: the SQLite database (`/data/db.sqlite3`) and uploads
(`/data/media`).

```
PROD: Internet ─► Nginx Proxy Manager (TLS) ─► edge ─► web ─► SQLite (/data)
TEST: Cloudflare tunnel (cloudflared)        ─► edge ─► web      worker ─┘
```

## Server layout

```
/opt/manager-warsztatow/
├── compose.yaml
├── compose.prod.yaml
├── compose.npm.yaml          # PROD only
├── docker/Caddyfile
└── .env                      # secrets and COMPOSE_FILE; never committed
```

Copy the files from the repository (or `git clone` and keep only these) and create `.env` from
`.env.example`. The essentials:

```bash
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(50))">
SITE_URL=https://warsztaty.example.org
ADMIN_EMAIL=admin@example.org
APP_TAG=dev                     # TEST follows :dev, PROD pins X.Y.Z
COMPOSE_FILE=compose.yaml:compose.prod.yaml
```

### TEST (LAN + Cloudflare tunnel)

```bash
EDGE_BIND=0.0.0.0
EDGE_PORT=80
SITE_NOINDEX=true
```

Point the tunnel's public hostname at `http://<vm-address>:80`.

### PROD (behind Nginx Proxy Manager)

```bash
COMPOSE_FILE=compose.yaml:compose.prod.yaml:compose.npm.yaml
PROXY_NETWORK=nginx_proxy_network
```

The edge joins NPM's Docker network as `manager-warsztatow-edge`. In NPM, add a Proxy Host for
the public name forwarding to `manager-warsztatow-edge`, port `80`, with a Let's Encrypt
certificate, *Force SSL* and *HTTP/2*. NPM sets `X-Real-IP` and `X-Forwarded-Proto`, which the
edge passes on.

## Start and update

```bash
docker compose pull
docker compose up -d --wait
curl -s http://127.0.0.1:${EDGE_PORT:-8080}/healthz   # TEST; on PROD: docker compose exec web …
```

`/healthz` answers `{"status": "ok", "db": "ok", "worker": "ok", …}`. The worker reports `ok`
within a minute of starting (it records a heartbeat every minute).

The first administrator (`ADMIN_EMAIL`) is created on start and signs in at `/konto/login/`
with a code sent by email — make sure email works first (Settings, or `EMAIL_URL`).

## Email

Outgoing mail uses the SMTP server entered in the panel (**Ustawienia → Poczta wychodząca**)
when "wysyłaj przez poniższy serwer SMTP" is switched on; otherwise `EMAIL_URL` with
`DEFAULT_FROM_EMAIL` as the sender. Keep `EMAIL_URL` working either way: it is the fallback,
and it lets the first administrator sign in before anything is configured.

The SMTP password is stored encrypted with `FIELD_ENCRYPTION_KEY`, or with a key derived from
`SECRET_KEY` when that is empty. Changing the key in use makes the stored password unreadable —
re-enter it in Settings afterwards.

E-mails are queued and sent by the `worker` container; with the worker stopped they wait in the
panel's e-mail log (**E-maile**) and go out when it is back.

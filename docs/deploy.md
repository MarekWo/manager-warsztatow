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
├── scripts/                  # _common.sh, backup.sh, restore.sh, update.sh
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

- When the DNS record is not in a zone NPM can reach through an API, the certificate uses the
  HTTP-01 challenge: port 80 must stay open to everyone, not only while the certificate is
  issued. Let's Encrypt's lifetimes shrink (64 days from February 2027, 45 from February 2028,
  with domain validation reused for only hours), so every renewal validates again.
- NPM 2.13 dropped *Force SSL* and *HTTP/2* when they were set in the same save that requested
  the certificate. Open the host again afterwards and check them; `http://` must answer 301.
- Leave *HSTS* off in NPM: the application sends `Strict-Transport-Security` itself
  (`SECURE_HSTS_SECONDS`), and two different headers would contradict each other.

Until outgoing mail works, `EMAIL_URL=consolemail://` lets the first administrator sign in
without sending anything: the code is in `docker compose logs web worker`.

## Start and update

```bash
scripts/update.sh dev          # TEST; PROD: scripts/update.sh X.Y.Z
```

`update.sh` takes a backup, pulls the images, starts the stack and waits for it to be healthy
(the `web` entrypoint runs migrations), records the tag in `.env` and prints `/healthz`. If the
stack does not come up it prints the previous tag to go back to. By hand:

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

## Backups

`scripts/backup.sh` writes `backups/<UTC timestamp>/` with `db.sqlite3` (SQLite's online backup,
checked with `PRAGMA integrity_check` — consistent while the site runs), `media.tar.gz`
(`/data/media`, public uploads, and `/data/private`, message attachments the edge never serves),
`MANIFEST` (counts of workshops, applications and files) and `SHA256SUMS`. Backups older than
`BACKUP_KEEP_DAYS` (30) are removed; `BACKUP_RSYNC_TARGET`, `BACKUP_RCLONE_REMOTE` and
`BACKUP_PING_URL` in `.env` copy them elsewhere and report to a monitor.

Run it daily with a systemd timer (as the user that owns `/opt/manager-warsztatow`):

```ini
# /etc/systemd/system/manager-warsztatow-backup.service
[Unit]
Description=Manager Warsztatow backup (database and uploads)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=marek
WorkingDirectory=/opt/manager-warsztatow
ExecStart=/opt/manager-warsztatow/scripts/backup.sh

# /etc/systemd/system/manager-warsztatow-backup.timer
[Unit]
Description=Daily Manager Warsztatow backup

[Timer]
OnCalendar=*-*-* 02:30
RandomizedDelaySec=10m
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now manager-warsztatow-backup.timer
```

Restoring:

```bash
scripts/restore.sh backups/20261013T023000Z --check   # drill: integrity and counts, changes nothing
scripts/restore.sh backups/20261013T023000Z           # replaces the live data (asks first)
```

Run the drill after setting up a server and now and then afterwards — a backup that was never
restored is only a hope.

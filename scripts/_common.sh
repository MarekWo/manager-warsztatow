# Shared by the server scripts (update, backup, restore). Sourced, never run.
# shellcheck shell=bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

info()    { printf '\033[0;34m[*]\033[0m %s\n' "$*"; }
success() { printf '\033[0;32m[+]\033[0m %s\n' "$*"; }
warn()    { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()     { printf '\033[0;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# env_value NAME [DEFAULT] → the value from the process environment, else from .env, else DEFAULT.
# .env is read as data, never sourced: it holds passwords that may contain shell characters.
env_value() {
    local name="$1" default="${2:-}" value
    if [ -n "${!name:-}" ]; then
        printf '%s' "${!name}"
        return
    fi
    if [ -f .env ]; then
        value="$(grep -E "^${name}=" .env | tail -n 1 | cut -d= -f2- | tr -d '\r')"
        value="${value%\"}"; value="${value#\"}"
        if [ -n "$value" ]; then
            printf '%s' "$value"
            return
        fi
    fi
    printf '%s' "$default"
}

# Refuse to act on the DEV stack: server scripts need the production overlay selected in .env.
require_server_stack() {
    case "$(env_value COMPOSE_FILE)" in
        *compose.prod.yaml*) ;;
        *) die "COMPOSE_FILE in .env does not include compose.prod.yaml — is this a server install? (docs/deploy.md)" ;;
    esac
}

# The database inside the containers (the `data` volume).
DB_PATH=/data/db.sqlite3

# db_counts FILE → "workshops=N applications=N" read from an SQLite file inside the web image.
# With no running web container (restore), a throwaway one is used.
db_counts() {
    local file="${1:-$DB_PATH}"
    local code='import sqlite3, sys
db = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
q = lambda t: db.execute("SELECT count(*) FROM " + t).fetchone()[0]
print("workshops=%d applications=%d" % (q("workshops_workshop"), q("applications_application")))'
    if [ -n "$(docker compose ps -q --status running web 2>/dev/null)" ]; then
        docker compose exec -T web python -c "$code" "$file"
    else
        docker compose run --rm --no-deps -T --entrypoint python web -c "$code" "$file"
    fi
}

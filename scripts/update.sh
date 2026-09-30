#!/usr/bin/env bash
# Update a Manager Warsztatów server to an image tag.
#
#   scripts/update.sh            # the tag already in .env (APP_TAG, default dev)
#   scripts/update.sh dev        # TEST follows the dev branch image
#   scripts/update.sh 1.0.0      # PROD runs released versions
#
#   --no-backup   skip the backup taken before anything changes
#
# Steps: backup → pull images → up -d --wait (web runs migrations in its entrypoint) → record
# the tag in .env → print /healthz. On failure it prints how to go back.
# The compose files, Caddyfile and scripts are copied from the repository by hand
# (docs/deploy.md) — a server has no checkout.
set -euo pipefail
# shellcheck source=scripts/_common.sh
. "$(dirname "$0")/_common.sh"

TAG=""
BACKUP=true
for arg in "$@"; do
    case "$arg" in
        --no-backup) BACKUP=false ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        -*) die "Unknown option: $arg" ;;
        *) TAG="$arg" ;;
    esac
done

require_server_stack

PREVIOUS_TAG="$(env_value APP_TAG dev)"
TAG="${TAG:-$PREVIOUS_TAG}"
[[ "$TAG" =~ ^[A-Za-z0-9_.-]+$ ]] || die "Not an image tag: $TAG"
export APP_TAG="$TAG"

if $BACKUP && [ -n "$(docker compose ps -q --status running web 2>/dev/null)" ]; then
    info "Backing up before the update"
    bash "$ROOT/scripts/backup.sh"
fi

PREVIOUS_IMAGE="$(docker compose images -q web 2>/dev/null | head -n 1 || true)"

info "Pulling images for tag $TAG"
docker compose pull --quiet || die "Pulling failed: does tag '$TAG' exist?"

info "Starting the stack (migrations run in the web entrypoint)"
if ! docker compose up -d --remove-orphans --wait --wait-timeout 300; then
    docker compose ps
    docker compose logs --tail 60 web worker
    warn "The stack did not become healthy on tag $TAG."
    warn "Previous tag: $PREVIOUS_TAG, previous web image: ${PREVIOUS_IMAGE:-unknown}."
    warn "Go back with: scripts/update.sh $PREVIOUS_TAG --no-backup  (after a migration: scripts/restore.sh)"
    exit 1
fi

if grep -qE '^APP_TAG=' .env; then
    sed -i "s/^APP_TAG=.*/APP_TAG=$TAG/" .env
else
    printf '\nAPP_TAG=%s\n' "$TAG" >>.env
fi

docker compose ps
HEALTH="$(docker compose exec -T web python -c \
    "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/healthz', timeout=5).read().decode())")"
success "Updated to $TAG: $HEALTH"

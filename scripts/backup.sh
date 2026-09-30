#!/usr/bin/env bash
# Back up a Manager Warsztatów server: the SQLite database and the uploaded files.
#
#   scripts/backup.sh            # run from /opt/manager-warsztatow (systemd timer: docs/deploy.md)
#
# Each run writes BACKUP_DIR/<UTC timestamp>/ with db.sqlite3, media.tar.gz, MANIFEST and
# SHA256SUMS. The database is copied with SQLite's online backup API, so the copy is consistent
# while the site and the worker keep running. Settings come from the environment or .env:
#   BACKUP_DIR           where backups go                      (default: ./backups)
#   BACKUP_KEEP_DAYS     delete local backups older than this  (default: 30)
#   BACKUP_RSYNC_TARGET  optional rsync destination, e.g. nas:/volume1/backup/warsztaty
#   BACKUP_RCLONE_REMOTE optional rclone destination, e.g. gdrive:warsztaty
#   BACKUP_PING_URL      optional healthchecks-style URL: pinged on success, <url>/fail on failure
set -euo pipefail
# shellcheck source=scripts/_common.sh
. "$(dirname "$0")/_common.sh"

require_server_stack

BACKUP_DIR="$(env_value BACKUP_DIR "$ROOT/backups")"
KEEP_DAYS="$(env_value BACKUP_KEEP_DAYS 30)"
RSYNC_TARGET="$(env_value BACKUP_RSYNC_TARGET)"
RCLONE_REMOTE="$(env_value BACKUP_RCLONE_REMOTE)"
PING_URL="$(env_value BACKUP_PING_URL)"

ping_url() {
    [ -n "$PING_URL" ] && curl -fsS -m 10 --retry 3 -o /dev/null "$1" || true
}
trap 'ping_url "${PING_URL%/}/fail"; die "Backup failed"' ERR

[ -n "$(docker compose ps -q --status running web 2>/dev/null)" ] || die "The web container is not running"

mkdir -p "$BACKUP_DIR"
exec 9>"$BACKUP_DIR/.lock"
if command -v flock >/dev/null; then
    flock -n 9 || die "Another backup is running"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$BACKUP_DIR/$STAMP.partial"
mkdir -p "$WORK"
info "Backing up to $BACKUP_DIR/$STAMP"

# Online backup into the container's /tmp, checked, then streamed out and removed.
docker compose exec -T web python - "$DB_PATH" <<'PY'
import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect("/tmp/backup.sqlite3")
source.backup(target)
check = target.execute("PRAGMA integrity_check").fetchone()[0]
target.close()
if check != "ok":
    sys.exit(f"integrity_check: {check}")
PY
docker compose exec -T web sh -c 'cat /tmp/backup.sqlite3 && rm -f /tmp/backup.sqlite3' >"$WORK/db.sqlite3"
success "Database: $(du -h "$WORK/db.sqlite3" | cut -f1)"

# Through the web container, so it works whatever the volume driver is.
docker compose exec -T web sh -c 'mkdir -p /data/media && tar -C /data/media -czf - .' >"$WORK/media.tar.gz"
MEDIA_FILES="$(tar -tzf "$WORK/media.tar.gz" | grep -vc '/$' || true)"
success "Media: $MEDIA_FILES files, $(du -h "$WORK/media.tar.gz" | cut -f1)"

{
    echo "created=$STAMP"
    echo "image_tag=$(env_value APP_TAG dev)"
    db_counts | tr ' ' '\n'
    echo "media_files=$MEDIA_FILES"
} >"$WORK/MANIFEST"
(cd "$WORK" && sha256sum db.sqlite3 media.tar.gz MANIFEST >SHA256SUMS)
mv "$WORK" "$BACKUP_DIR/$STAMP"
success "Backup complete: $(tr '\n' ' ' < "$BACKUP_DIR/$STAMP/MANIFEST")"

find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$KEEP_DAYS" -print \
    -exec rm -rf {} + | sed 's/^/    removed old backup: /'
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '*.partial' -mmin +720 -exec rm -rf {} +

if [ -n "$RSYNC_TARGET" ]; then
    info "Copying to $RSYNC_TARGET"
    rsync -a --delete "$BACKUP_DIR/" "$RSYNC_TARGET/" --exclude '*.partial' --exclude .lock
fi
if [ -n "$RCLONE_REMOTE" ]; then
    info "Copying to $RCLONE_REMOTE"
    rclone copy "$BACKUP_DIR/$STAMP" "$RCLONE_REMOTE/$STAMP"
fi

trap - ERR
ping_url "$PING_URL"

#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh.
#
#   scripts/restore.sh backups/20261013T020000Z --check
#       Restore drill: open the backed-up database in a throwaway container, run SQLite's
#       integrity check and compare the counts with the MANIFEST. Changes nothing live.
#
#   scripts/restore.sh backups/20261013T020000Z --yes
#       Replace the live database and uploaded files with the backup (the site is stopped
#       meanwhile). Without --yes it asks first.
set -euo pipefail
# shellcheck source=scripts/_common.sh
. "$(dirname "$0")/_common.sh"

usage() { sed -n '2,11p' "$0"; exit 2; }

SOURCE=""
CHECK=false
ASSUME_YES=false
while [ $# -gt 0 ]; do
    case "$1" in
        --check) CHECK=true ;;
        --yes) ASSUME_YES=true ;;
        -h|--help) usage ;;
        -*) usage ;;
        *) SOURCE="$1" ;;
    esac
    shift
done
[ -n "$SOURCE" ] && [ -d "$SOURCE" ] || usage
SOURCE="$(cd "$SOURCE" && pwd)"

require_server_stack

manifest() { grep -E "^$1=" "$SOURCE/MANIFEST" | cut -d= -f2-; }
EXPECTED="workshops=$(manifest workshops) applications=$(manifest applications)"

info "Verifying checksums in $SOURCE"
(cd "$SOURCE" && sha256sum --quiet -c SHA256SUMS) || die "Checksum mismatch — the backup is damaged"
success "Checksums OK ($(tr '\n' ' ' < "$SOURCE/MANIFEST"))"

if $CHECK; then
    # The file goes into the throwaway container's /tmp; the live volume is not touched.
    FOUND="$(docker compose run --rm --no-deps -T --entrypoint sh web -c '
        cat >/tmp/check.sqlite3 &&
        python - <<"PY"
import sqlite3
db = sqlite3.connect("/tmp/check.sqlite3")
check = db.execute("PRAGMA integrity_check").fetchone()[0]
q = lambda t: db.execute("SELECT count(*) FROM " + t).fetchone()[0]
print("%s workshops=%d applications=%d" % (check, q("workshops_workshop"), q("applications_application")))
PY' <"$SOURCE/db.sqlite3")"
    MEDIA="$(tar -tzf "$SOURCE/media.tar.gz" | grep -vc '/$' || true)"
    FAILED=0
    if [ "$FOUND" = "ok $EXPECTED" ]; then
        success "Database: integrity ok, $EXPECTED (live: $(db_counts))"
    else
        warn "Database: found '$FOUND', manifest says '$EXPECTED'"; FAILED=1
    fi
    if [ "$MEDIA" = "$(manifest media_files)" ]; then
        success "Uploaded files in the archive: $MEDIA"
    else
        warn "Uploaded files: archive has $MEDIA, manifest says $(manifest media_files)"; FAILED=1
    fi
    [ "$FAILED" -eq 0 ] && success "Restore drill passed" || die "Restore drill failed"
    exit 0
fi

if ! $ASSUME_YES; then
    printf 'This REPLACES the live database and all uploaded files with the backup. Type "restore": '
    read -r answer
    [ "$answer" = "restore" ] || die "Aborted"
fi

info "Stopping edge, web and worker"
docker compose stop edge web worker

info "Restoring the database"
docker compose run --rm --no-deps -T --entrypoint sh web -c "
    cat >$DB_PATH.restore &&
    rm -f $DB_PATH-wal $DB_PATH-shm &&
    mv $DB_PATH.restore $DB_PATH" <"$SOURCE/db.sqlite3"

info "Restoring uploaded files"
docker compose run --rm --no-deps -T --entrypoint sh web \
    -c 'mkdir -p /data/media /data/private && find /data/media /data/private -mindepth 1 -delete && tar -xzf - -C /data' \
    <"$SOURCE/media.tar.gz"

info "Starting the stack"
docker compose up -d --wait
FOUND="$(db_counts)"
[ "$FOUND" = "$EXPECTED" ] || die "After restore: $FOUND, manifest says $EXPECTED"
success "Restored: $FOUND, $(manifest media_files) uploaded files"

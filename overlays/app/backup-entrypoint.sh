#!/bin/sh
set -eu

DB_PATH="\${DATABASE_PATH:-/data/guardian.sqlite3}"
DB_DIR="$(dirname "$DB_PATH")"

mkdir -p "$DB_DIR" /data
chown appuser:appuser "$DB_DIR" /data

for candidate in \
    "$DB_PATH" \
    "$DB_PATH-wal" \
    "$DB_PATH-shm" \
    "$DB_PATH-journal" \
    /data/.asg_backup_state.json \
    /data/.asg_backup_state.json.tmp
do
    if [ -e "$candidate" ]; then
        chown appuser:appuser "$candidate"
    fi
done

exec gosu appuser "$@"

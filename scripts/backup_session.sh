#!/usr/bin/env bash
# Daily backup of critical state to offsite storage.
# Reads BACKUP_DEST from .env (e.g., user@backup.example:/backups/ig-qt or rclone:remote:bucket/ig-qt).
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found"
  exit 1
fi

# shellcheck disable=SC1091
source .env

if [[ -z "${BACKUP_DEST:-}" ]]; then
  echo "ERROR: BACKUP_DEST not set in .env"
  exit 1
fi

DATE=$(date -u +"%Y%m%dT%H%M%SZ")
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

# Snapshot SQLite to avoid copying mid-write file
docker compose exec -T ig-qt sqlite3 /app/data/ig_qt.db ".backup '/app/data/ig_qt.snapshot.db'"
cp data/ig_qt.snapshot.db "$TMP_DIR/ig_qt-${DATE}.db"
rm data/ig_qt.snapshot.db

# Copy session files
[[ -f data/ig_session.json ]] && cp data/ig_session.json "$TMP_DIR/ig_session-${DATE}.json"

# Push to destination
case "$BACKUP_DEST" in
  rclone:*)
    REMOTE="${BACKUP_DEST#rclone:}"
    rclone copy "$TMP_DIR/" "$REMOTE/" --transfers=4 --quiet
    ;;
  *:*)
    rsync -avz --quiet "$TMP_DIR/" "$BACKUP_DEST/"
    ;;
  *)
    mkdir -p "$BACKUP_DEST"
    cp "$TMP_DIR"/* "$BACKUP_DEST/"
    ;;
esac

echo "Backup complete: $DATE"

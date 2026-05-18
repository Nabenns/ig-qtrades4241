#!/usr/bin/env bash
# Restore latest session.json + ig_qt.db from backup destination.
# Usage: ./scripts/restore_session.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source .env

if [[ -z "${BACKUP_DEST:-}" ]]; then
  echo "ERROR: BACKUP_DEST not set"
  exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

case "$BACKUP_DEST" in
  rclone:*)
    REMOTE="${BACKUP_DEST#rclone:}"
    rclone copy "$REMOTE/" "$TMP_DIR/" --include "ig_*"
    ;;
  *:*)
    rsync -avz "$BACKUP_DEST/" "$TMP_DIR/"
    ;;
  *)
    cp -r "$BACKUP_DEST"/* "$TMP_DIR/"
    ;;
esac

LATEST_DB=$(ls -1 "$TMP_DIR"/ig_qt-*.db 2>/dev/null | sort | tail -1 || true)
LATEST_SESSION=$(ls -1 "$TMP_DIR"/ig_session-*.json 2>/dev/null | sort | tail -1 || true)

if [[ -z "$LATEST_DB" ]]; then
  echo "ERROR: no ig_qt-*.db found in backup"
  exit 1
fi

echo "Restoring DB from $LATEST_DB"
echo "WARNING: this will overwrite data/ig_qt.db. Stop the service first."
read -r -p "Continue? [y/N]: " CONFIRM
[[ "$CONFIRM" == "y" ]] || exit 0

docker compose down || true
mkdir -p data
cp "$LATEST_DB" data/ig_qt.db
[[ -n "$LATEST_SESSION" ]] && cp "$LATEST_SESSION" data/ig_session.json

echo "Restored. Start service with: docker compose up -d"

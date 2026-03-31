#!/usr/bin/env bash
# OpenMind V3 KB Backup to Google Workspace
# Backs up the SQLite databases from the KB to Google Drive via rclone.
# Designed to be run periodically via cron.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$HOME/.openmind/runtime.env"

# Load environment variables if they exist
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

KB_DIR="$PROJECT_ROOT/chatgptrest/kb"
# Try looking for advisor root where db might live
ADVISOR_STATE_ROOT="${CHATGPTREST_ADVISOR_STATE_ROOT:-$PROJECT_ROOT/advisor_state}"
DB_PATH="${CHATGPTREST_KB_DB_PATH:-$ADVISOR_STATE_ROOT/kb.db}"
VERSION_DB_PATH="${DB_PATH%.db}_versions.db"

GDRIVE_REMOTE="${CHATGPTREST_GDRIVE_RCLONE_REMOTE:-gdrive}"
# Ensure remote has trailing colon
[[ "$GDRIVE_REMOTE" != *":" ]] && GDRIVE_REMOTE="${GDRIVE_REMOTE}:"

UPLOAD_SUBDIR="${CHATGPTREST_GDRIVE_UPLOAD_SUBDIR:-chatgptrest_uploads}"
BACKUP_DEST="${GDRIVE_REMOTE}${UPLOAD_SUBDIR}/kb_backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "╔══════════════════════════════════════════════════╗"
echo "║  OpenMind V3 — KB Backup                         ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Time: $(date)"
echo "DB Path: $DB_PATH"
echo "Dest: $BACKUP_DEST"
echo "---------------------------------------------------"

# Check dependencies
if ! command -v rclone &>/dev/null; then
    echo "❌ Error: rclone not found in PATH."
    exit 1
fi

if ! command -v sqlite3 &>/dev/null; then
    echo "❌ Error: sqlite3 not found in PATH."
    exit 1
fi

if [ ! -f "$DB_PATH" ]; then
    echo "⚠️  $DB_PATH does not exist. The KB might not have been initialized yet."
    exit 0
fi

# Ensure backup tmp dir exists
TMP_BACKUP_DIR="/tmp/openmind_kb_backup_$TIMESTAMP"
mkdir -p "$TMP_BACKUP_DIR"
trap 'rm -rf "$TMP_BACKUP_DIR"' EXIT

# Safely back up SQLite using .backup command (avoids locking issues)
echo "📦 Creating consistent snapshot of $DB_PATH..."
sqlite3 "$DB_PATH" ".backup '$TMP_BACKUP_DIR/kb_${TIMESTAMP}.db'"

if [ -f "$VERSION_DB_PATH" ]; then
    echo "📦 Creating consistent snapshot of $VERSION_DB_PATH..."
    sqlite3 "$VERSION_DB_PATH" ".backup '$TMP_BACKUP_DIR/kb_versions_${TIMESTAMP}.db'"
fi

# Sync to Google Drive
echo "☁️  Uploading to Google Drive ($BACKUP_DEST)..."
if rclone copy "$TMP_BACKUP_DIR" "$BACKUP_DEST" --stats 0 --timeout 5m; then
    echo "✅ Backup successfully copied to Google Drive."
else
    echo "❌ Backup upload to Google Drive failed."
    exit 1
fi

# Prune old backups on Drive (keep last 7 days)
echo "🧹 Pruning old backups on Drive (older than 7 days)..."
rclone delete "$BACKUP_DEST" --min-age 7d --rmdirs 2>/dev/null || true

echo "---------------------------------------------------"
echo "✅ Backup process complete."

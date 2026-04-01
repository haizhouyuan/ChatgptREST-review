#!/usr/bin/env bash
# rclone bisync: Google Drive ↔ Local Vault (two-way sync)
#
# Syncs gdrive:ObsidianVault ↔ /vol1/1000/data/obsidian-vault
# On first run, use --resync to establish baseline.
#
# Usage:
#   ./scripts/sync_vault_gdrive.sh           # normal incremental
#   ./scripts/sync_vault_gdrive.sh --resync  # first run / force re-baseline
#
# Cron / systemd timer recommended: every 5 minutes
set -euo pipefail

REMOTE="gdrive:ObsidianVault"
LOCAL="/vol1/1000/data/obsidian-vault"
LOG="/tmp/rclone_obsidian_bisync.log"

mkdir -p "$LOCAL"

EXTRA_FLAGS=""
if [[ "${1:-}" == "--resync" ]]; then
    EXTRA_FLAGS="--resync"
    echo "$(date -Iseconds) [RESYNC] Establishing baseline..." | tee -a "$LOG"
fi

rclone bisync "$REMOTE" "$LOCAL" \
    --exclude ".obsidian/**" \
    --exclude ".trash/**" \
    --exclude ".git/**" \
    $EXTRA_FLAGS \
    --verbose \
    --log-file "$LOG" \
    2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date -Iseconds) [OK] Bisync completed." >> "$LOG"
else
    echo "$(date -Iseconds) [ERROR] Bisync failed (exit $EXIT_CODE)." >> "$LOG"
fi

# After Drive sync, trigger KB indexing if available
KB_SYNC="/vol1/1000/projects/ChatgptREST/scripts/sync_obsidian_to_kb.py"
if [ -f "$KB_SYNC" ]; then
    echo "$(date -Iseconds) [KB] Running KB indexing..." >> "$LOG"
    cd /vol1/1000/projects/ChatgptREST
    export OPENMIND_OBSIDIAN_VAULT_PATH="$LOCAL"
    PYTHONPATH=. .venv/bin/python "$KB_SYNC" >> "$LOG" 2>&1 || true
fi

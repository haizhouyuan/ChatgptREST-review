#!/usr/bin/env bash
# Google Workspace Setup for OpenMind V3
# Run this script to configure Google Workspace integration.
#
# Prerequisites:
#   1. Google Cloud Project created at https://console.cloud.google.com
#   2. APIs enabled: Drive, Calendar, Sheets, Docs, Gmail, Tasks
#   3. OAuth 2.0 Desktop App credentials downloaded as credentials.json
#
# Usage:
#   bash scripts/setup_google_workspace.sh [path/to/credentials.json]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OPENMIND_DIR="$HOME/.openmind"
CREDENTIALS_DEST="$OPENMIND_DIR/google_credentials.json"
TOKEN_PATH="$OPENMIND_DIR/google_token.json"

echo "╔══════════════════════════════════════════════════╗"
echo "║  OpenMind V3 — Google Workspace Setup            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Check prerequisites ──────────────────────────────────

echo "🔍 Checking prerequisites..."

# rclone
if command -v rclone &>/dev/null; then
    RCLONE_VER=$(rclone version 2>/dev/null | head -1 || echo "unknown")
    echo "  ✅ rclone: $RCLONE_VER"
else
    echo "  ❌ rclone not found. Install: curl https://rclone.org/install.sh | sudo bash"
    exit 1
fi

# Python SDK
if "$PROJECT_ROOT/.venv/bin/python" -c "import googleapiclient" 2>/dev/null; then
    echo "  ✅ google-api-python-client installed"
else
    echo "  ⚠️  Installing Google API Python SDK..."
    "$PROJECT_ROOT/.venv/bin/pip" install -q google-api-python-client google-auth-httplib2 google-auth-oauthlib
    echo "  ✅ Google API Python SDK installed"
fi

echo ""

# ── Step 2: Copy credentials ────────────────────────────────────

mkdir -p "$OPENMIND_DIR"

CREDS_SRC="${1:-}"
if [ -n "$CREDS_SRC" ] && [ -f "$CREDS_SRC" ]; then
    if [ "$CREDS_SRC" != "$CREDENTIALS_DEST" ]; then
        cp "$CREDS_SRC" "$CREDENTIALS_DEST"
        chmod 600 "$CREDENTIALS_DEST"
        echo "✅ Credentials copied to $CREDENTIALS_DEST"
    else
        echo "✅ Credentials already at $CREDENTIALS_DEST"
    fi
elif [ -f "$CREDENTIALS_DEST" ]; then
    echo "✅ Credentials already exist at $CREDENTIALS_DEST"
else
    echo "⚠️  No credentials.json found."
    echo "   Download from: Google Cloud Console → APIs & Services → Credentials"
    echo "   Then re-run:   bash $0 /path/to/credentials.json"
    echo ""
    echo "   Or place manually at: $CREDENTIALS_DEST"
    echo ""
fi

# ── Step 3: Configure rclone GDrive remote ──────────────────────

echo ""
echo "🔍 Checking rclone remotes..."

if rclone listremotes 2>/dev/null | grep -q "^gdrive:"; then
    echo "  ✅ rclone remote 'gdrive' already configured"
    echo "  Verifying connectivity..."
    if rclone lsd gdrive: --max-depth 0 2>/dev/null | head -3; then
        echo "  ✅ GDrive connection verified"
    else
        echo "  ⚠️  GDrive connection failed. Run: rclone config reconnect gdrive:"
    fi
else
    echo "  ❌ rclone remote 'gdrive' not configured"
    echo ""
    echo "  To configure, run:"
    echo "    rclone config"
    echo ""
    echo "  Steps:"
    echo "    1. Choose 'n' (new remote)"
    echo "    2. Name: gdrive"
    echo "    3. Storage: drive"
    echo "    4. client_id: (paste your OAuth client ID, or leave blank for rclone's built-in)"
    echo "    5. client_secret: (paste, or leave blank)"
    echo "    6. scope: 1 (Full access)"
    echo "    7. root_folder_id: (leave blank)"
    echo "    8. service_account_file: (leave blank)"
    echo "    9. Follow the auth URL instructions"
    echo ""
    echo "  For headless servers (no browser):"
    echo "    rclone authorize \"drive\" --auth-no-open-browser"
    echo "    (Copy the URL to a machine with a browser, authorize, paste token back)"
fi

# ── Step 4: OAuth Token (Python API) ────────────────────────────

echo ""
if [ -f "$TOKEN_PATH" ]; then
    echo "✅ Google OAuth token exists at $TOKEN_PATH"
else
    echo "⚠️  No OAuth token yet."
    if [ -f "$CREDENTIALS_DEST" ]; then
        echo "  Generating token now."
        echo "  ⚠️  Because this is a remote server, Google's auth flow requires port forwarding."
        echo "      1. The script will print: 'Please visit this URL: ...'"
        echo "      2. Open that URL in your local browser and authorize."
        echo "      3. Your browser will redirect to a URL like: http://localhost:PORT/..."
        echo "      4. It will fail to load. Look at the PORT number in the URL."
        echo "      5. Open a NEW terminal locally and run:"
        echo "         ssh -L PORT:localhost:PORT yuanhaizhou@<server-ip>"
        echo "      6. Refresh the failed page in your browser. It will complete."
        echo ""
    else
        echo "  (Needs credentials.json first — see Step 2)"
    fi
fi

# ── Step 5: Create upload directory ─────────────────────────────

echo ""
if rclone listremotes 2>/dev/null | grep -q "^gdrive:"; then
    echo "🔍 Checking chatgptrest_uploads folder..."
    if rclone lsd gdrive:chatgptrest_uploads 2>/dev/null; then
        echo "  ✅ chatgptrest_uploads folder exists"
    else
        echo "  Creating chatgptrest_uploads folder..."
        rclone mkdir gdrive:chatgptrest_uploads 2>/dev/null && \
            echo "  ✅ Created chatgptrest_uploads" || \
            echo "  ⚠️  Could not create folder (rclone not configured?)"
    fi
fi

# ── Summary ─────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Setup Summary"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Credentials:  $CREDENTIALS_DEST"
echo "  Token:        $TOKEN_PATH"
echo "  rclone conf:  $(rclone config file 2>/dev/null | tail -1 || echo 'N/A')"
echo ""

# Show env vars to configure
echo "  Environment variables (add to ~/.openmind/runtime.env):"
echo ""
echo "    OPENMIND_GOOGLE_CREDENTIALS_PATH=$CREDENTIALS_DEST"
echo "    OPENMIND_GOOGLE_TOKEN_PATH=$TOKEN_PATH"
echo "    OPENMIND_GOOGLE_SERVICES=drive,calendar,sheets,docs,gmail,tasks"
echo ""
echo "═══════════════════════════════════════════════════"

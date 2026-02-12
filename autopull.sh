#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  autopull.sh — Auto-pull from origin & restart the bot
#
#  Usage:  ./autopull.sh
#
#  What it does:
#    1. Starts main.py in the background
#    2. Every POLL_INTERVAL seconds, checks origin for new commits
#    3. If new commits exist → git pull, reinstall deps if needed,
#       kill old process, restart main.py
#    4. Ctrl-C stops everything cleanly
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ───────────────────────────────────────────────────
POLL_INTERVAL="${POLL_INTERVAL:-30}"        # seconds between checks
BRANCH="${BRANCH:-main}"                    # branch to track
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
VENV_DIR="$SCRIPT_DIR/venv"

# ── Colours ──────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${CYAN}[autopull $(date +%H:%M:%S)]${NC} $*"; }
warn() { echo -e "${YELLOW}[autopull $(date +%H:%M:%S)]${NC} $*"; }
err()  { echo -e "${RED}[autopull $(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}[autopull $(date +%H:%M:%S)]${NC} $*"; }

# ── Activate venv if present ─────────────────────────────────
if [[ -d "$VENV_DIR" ]]; then
    source "$VENV_DIR/bin/activate"
    log "Activated venv at $VENV_DIR"
fi

# ── State ────────────────────────────────────────────────────
BOT_PID=""

start_bot() {
    log "Starting bot..."
    cd "$SCRIPT_DIR"
    $PYTHON main.py &
    BOT_PID=$!
    ok "Bot started (PID $BOT_PID)"
}

stop_bot() {
    if [[ -n "$BOT_PID" ]] && kill -0 "$BOT_PID" 2>/dev/null; then
        warn "Stopping bot (PID $BOT_PID)..."
        kill "$BOT_PID" 2>/dev/null || true
        # Give it a moment to shut down gracefully
        for i in {1..5}; do
            kill -0 "$BOT_PID" 2>/dev/null || break
            sleep 1
        done
        # Force kill if still alive
        if kill -0 "$BOT_PID" 2>/dev/null; then
            warn "Force-killing bot..."
            kill -9 "$BOT_PID" 2>/dev/null || true
        fi
        ok "Bot stopped"
    fi
    BOT_PID=""
}

cleanup() {
    echo ""
    warn "Shutting down..."
    stop_bot
    ok "Goodbye!"
    exit 0
}

trap cleanup SIGINT SIGTERM

check_for_updates() {
    cd "$SCRIPT_DIR"

    # Fetch latest from origin (quietly)
    if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
        warn "git fetch failed (network issue?), will retry next cycle"
        return 1
    fi

    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse "origin/$BRANCH")

    if [[ "$LOCAL" == "$REMOTE" ]]; then
        return 1  # No changes
    fi

    return 0  # Changes detected
}

pull_and_restart() {
    cd "$SCRIPT_DIR"

    log "New commits detected on origin/$BRANCH!"

    # Record pyproject.toml hash before pull
    local old_deps_hash=""
    if [[ -f pyproject.toml ]]; then
        old_deps_hash=$(md5 -q pyproject.toml 2>/dev/null || md5sum pyproject.toml 2>/dev/null | awk '{print $1}')
    fi

    # Pull changes
    log "Pulling latest changes..."
    if ! git pull origin "$BRANCH"; then
        err "git pull failed! Skipping restart."
        return
    fi
    ok "Pull successful"

    # Check if dependencies changed
    local new_deps_hash=""
    if [[ -f pyproject.toml ]]; then
        new_deps_hash=$(md5 -q pyproject.toml 2>/dev/null || md5sum pyproject.toml 2>/dev/null | awk '{print $1}')
    fi

    if [[ "$old_deps_hash" != "$new_deps_hash" ]]; then
        log "pyproject.toml changed — reinstalling dependencies..."
        pip install -e . --quiet 2>/dev/null || pip install -e . || true
        ok "Dependencies updated"
    fi

    # Restart bot
    stop_bot
    start_bot
}

# ── Main Loop ────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        🔄  Auto-Pull & Restart Watcher          ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  Branch:    ${CYAN}$BRANCH${NC}"
echo -e "${GREEN}║${NC}  Interval:  ${CYAN}${POLL_INTERVAL}s${NC}"
echo -e "${GREEN}║${NC}  Project:   ${CYAN}$SCRIPT_DIR${NC}"
echo -e "${GREEN}║${NC}  Press ${RED}Ctrl-C${NC} to stop"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Initial start
start_bot

# Poll loop
while true; do
    sleep "$POLL_INTERVAL"

    # Make sure bot is still alive (crash recovery)
    if [[ -n "$BOT_PID" ]] && ! kill -0 "$BOT_PID" 2>/dev/null; then
        warn "Bot process died! Restarting..."
        start_bot
    fi

    # Check for remote changes
    if check_for_updates; then
        pull_and_restart
    fi
done

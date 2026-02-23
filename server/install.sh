#!/usr/bin/env bash
# install.sh — Set up and start the Vibedroid server on WSL/Ubuntu
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Checking dependencies..."
command -v python3 >/dev/null || { echo "ERROR: python3 not found"; exit 1; }
command -v tmux    >/dev/null || { echo "ERROR: tmux not found. Run: sudo apt install tmux"; exit 1; }

echo "==> Installing Python packages..."
pip3 install --quiet --upgrade pip
pip3 install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo "==> Finding Tailscale IP..."
TAILSCALE_IP=""
if command -v tailscale >/dev/null 2>&1; then
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1 || true)
fi
if [ -z "$TAILSCALE_IP" ]; then
    # Fallback: look for 100.x Tailscale range
    TAILSCALE_IP=$(ip addr show 2>/dev/null | grep -oP '100\.\d+\.\d+\.\d+' | head -1 || true)
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Vibedroid server ready"
if [ -n "$TAILSCALE_IP" ]; then
    echo "  Your Tailscale IP: $TAILSCALE_IP"
    echo "  Android URL:       http://$TAILSCALE_IP:7681"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Starting server (Ctrl+C to stop)..."
exec python3 "$SCRIPT_DIR/vibedroid_server.py" "$@"

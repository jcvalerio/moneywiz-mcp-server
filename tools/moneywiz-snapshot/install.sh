#!/bin/bash
# Build and install the MoneyWiz snapshot helper as a per-user launchd agent.
#
# Usage: install.sh /absolute/path/to/MoneyWiz.sqlite [interval-seconds]
#   interval-seconds: 60 to 86400, default 900
#
# After installing, grant Full Disk Access to the installed helper only (the
# script prints its path). Neither Claude Desktop nor your terminal needs it.

set -euo pipefail

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/Library/Application Support/moneywiz-mcp"
BIN_DIR="$APP_DIR/bin"
INSTALLED="$BIN_DIR/moneywiz-snapshot"
LABEL="com.moneywiz-mcp.snapshot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/moneywiz-snapshot.log"
DOMAIN="gui/$(id -u)"

die() { echo "error: $*" >&2; exit 1; }

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || die "usage: $0 /absolute/path/to/MoneyWiz.sqlite [interval-seconds]"
INTERVAL="${2:-900}"
case "$INTERVAL" in
  '' | *[!0-9]*) die "interval must be a whole number of seconds" ;;
esac
[ "$INTERVAL" -ge 60 ] || die "interval must be at least 60 seconds"
[ "$INTERVAL" -le 86400 ] || die "interval must be at most 86400 seconds (one day)"

"$TOOL_DIR/build.sh" "$1"

mkdir -p "$BIN_DIR"
chmod 700 "$APP_DIR" "$BIN_DIR"
install -m 0755 "$TOOL_DIR/build/moneywiz-snapshot" "$INSTALLED"

# Generate the agent with plutil so no path needs XML escaping. launchd runs
# the helper directly (Program, no shell), which is what makes macOS attribute
# the privileged read to the helper rather than to /bin/sh or a terminal.
mkdir -p "$(dirname "$PLIST")"
tmp_plist="$(mktemp)"
trap 'rm -f "$tmp_plist"' EXIT
plutil -create xml1 "$tmp_plist"
plutil -insert Label -string "$LABEL" "$tmp_plist"
plutil -insert Program -string "$INSTALLED" "$tmp_plist"
plutil -insert StartInterval -integer "$INTERVAL" "$tmp_plist"
plutil -insert RunAtLoad -bool true "$tmp_plist"
plutil -insert Umask -integer 63 "$tmp_plist"   # 077: new files owner-only
plutil -insert ProcessType -string Background "$tmp_plist"
plutil -insert LowPriorityIO -bool true "$tmp_plist"
plutil -insert Nice -integer 10 "$tmp_plist"
plutil -insert StandardOutPath -string "$LOG" "$tmp_plist"
plutil -insert StandardErrorPath -string "$LOG" "$tmp_plist"
plutil -lint "$tmp_plist" >/dev/null
install -m 0644 "$tmp_plist" "$PLIST"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"

cat <<EOF

Installed. One manual step remains:

  1. Open System Settings > Privacy & Security > Full Disk Access
  2. Click +, press Cmd+Shift+G, and add exactly:
       $INSTALLED
  3. Run the first snapshot now:
       launchctl kickstart -k $DOMAIN/$LABEL
  4. Check the log for "snapshot updated":
       tail -n 5 "$LOG"

Then point the MCP server at the snapshot, e.g. in .env or the Claude Desktop
config "env" block:

  MONEYWIZ_DB_PATH=$APP_DIR/snapshot.sqlite

The snapshot refreshes every $INTERVAL seconds. Runs fail (and are logged)
until step 2 is done.
EOF

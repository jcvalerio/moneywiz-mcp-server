#!/bin/bash
# Remove the MoneyWiz snapshot helper, its launchd agent, and the snapshot.
#
# The snapshot is a full copy of your financial data, so it is deleted too.

set -euo pipefail

APP_DIR="$HOME/Library/Application Support/moneywiz-mcp"
LABEL="com.moneywiz-mcp.snapshot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/moneywiz-snapshot.log"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST" "$LOG"
rm -f "$APP_DIR/bin/moneywiz-snapshot" "$APP_DIR/snapshot.sqlite"
rmdir "$APP_DIR/bin" "$APP_DIR" 2>/dev/null || true

cat <<EOF
Removed the agent, helper, snapshot, and log.

Also remove the helper from System Settings > Privacy & Security >
Full Disk Access (select it and click -). macOS does not remove that entry
automatically.

If the MCP server was pointed at the snapshot, update MONEYWIZ_DB_PATH.
EOF

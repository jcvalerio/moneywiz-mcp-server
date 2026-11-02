# moneywiz-snapshot: least-privilege database access on macOS

macOS privacy controls block other apps from reading MoneyWiz's data folder
(`~/Library/Containers/com.moneywiz.*`). The common workaround, giving Claude
Desktop or your terminal **Full Disk Access**, lets that app and every MCP
server it runs read your Mail, Messages, browser history, and every other
app's data.

This tool avoids that. A small helper binary is the only thing that gets Full
Disk Access, and it can do exactly one thing: copy your MoneyWiz database to
a private snapshot file. The MCP server reads the snapshot and needs no special
permissions.

```
MoneyWiz container (protected)
      │  launchd runs the helper every 15 minutes  ← only this binary has Full Disk Access
      ▼
~/Library/Application Support/moneywiz-mcp/snapshot.sqlite   (owner-only)
      │
      ▼
Claude Desktop → MCP server (MONEYWIZ_DB_PATH = snapshot)  ← no extra permissions
```

## Why the grant cannot be misused

- **Paths are compiled in.** The helper takes no arguments and reads no
  configuration or environment variables. `build.sh` only accepts known
  MoneyWiz locations.
- **No symlinks.** The source is opened read-only, and SQLite refuses a
  symlink anywhere in its path. SQLite does not apply that check to the
  `-wal`, `-shm`, and `-journal` files it opens alongside the database, so the
  helper refuses symlinks there itself. A link planted in place of any of
  these files cannot redirect the copy to another app's data. The snapshot
  folder must be a real, owner-only directory.
- **launchd runs the binary directly.** There is no shell script in between,
  so macOS attributes the read to the helper and not to `/bin/bash` (which
  would otherwise need Full Disk Access for every script it runs).
- **Signed with the hardened runtime.** macOS ties the privacy grant to this
  exact binary. A modified or rebuilt binary does not inherit it and must be
  granted again.

## What it copies

The copy uses SQLite's online backup API, so it is consistent even while
MoneyWiz is writing, and it includes changes not yet merged from MoneyWiz's
`-wal` file. When MoneyWiz is closed, the database is read in SQLite's
immutable mode and the copy is discarded if the file changed during the read.
The snapshot is checked with `PRAGMA quick_check` and replaced atomically, so
the MCP server never sees a partial file. Data is at most one interval old
(15 minutes by default).

## Install

1. Find your database path (see "Finding Your MoneyWiz Database" in the main
   README). It must be the real path, without symlinks.

2. Build and install the agent:

   ```bash
   tools/moneywiz-snapshot/install.sh \
     "$HOME/Library/Containers/com.moneywiz.personalfinance-setapp/Data/Documents/.AppData/ipadMoneyWiz.sqlite"
   ```

   An optional second argument sets the interval in seconds (default 900,
   60 to 86400).

3. Grant Full Disk Access to **the installed helper only**: System Settings >
   Privacy & Security > Full Disk Access, click **+**, press **Cmd+Shift+G**,
   and enter the path the installer printed:

   ```
   ~/Library/Application Support/moneywiz-mcp/bin/moneywiz-snapshot
   ```

4. Run the first snapshot and check the log:

   ```bash
   launchctl kickstart -k "gui/$(id -u)/com.moneywiz-mcp.snapshot"
   tail -n 5 ~/Library/Logs/moneywiz-snapshot.log   # expect "snapshot updated"
   ```

5. Point the MCP server at the snapshot, in `.env` or the Claude Desktop
   config's `env` block:

   ```
   MONEYWIZ_DB_PATH=/Users/<you>/Library/Application Support/moneywiz-mcp/snapshot.sqlite
   ```

   Claude Desktop does not need Full Disk Access. If you granted it earlier,
   you can remove it.

## Updating or moving the database

If MoneyWiz moves its database (for example after enabling iCloud sync), run
`install.sh` again with the new path. The rebuilt helper is a different
binary, so remove the old Full Disk Access entry and grant the new one.

## Uninstall

```bash
tools/moneywiz-snapshot/uninstall.sh
```

This removes the agent, the helper, the log, and the snapshot (a full copy of
your financial data). Then remove the helper from Full Disk Access in System
Settings; macOS does not do that automatically.

## Troubleshooting

| Log message | Meaning |
|---|---|
| `cannot open source database: ... authorization denied` / `unable to open database file` | Full Disk Access is not granted to the installed helper, or was granted to a different build |
| `source has an unrecovered journal or write-ahead log` | MoneyWiz did not shut down cleanly; open it once and the next run succeeds |
| `source changed during the copy` | MoneyWiz wrote while the snapshot was taken; the next run retries |
| `... is not a directory (symlinks are refused)` | The snapshot folder was replaced by a symlink; remove it |

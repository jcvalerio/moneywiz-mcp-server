#!/bin/bash
# Build the single-purpose MoneyWiz snapshot helper with its paths baked in.
#
# Usage: build.sh /absolute/path/to/MoneyWiz.sqlite
#
# The source and destination are compiled into the binary, so the Full Disk
# Access grant you give it cannot be used to read any other file. Rebuilding
# (for example after MoneyWiz moves its database) produces a new binary that
# must be granted again; that is intentional.

set -euo pipefail

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$TOOL_DIR/build"
BINARY="$BUILD_DIR/moneywiz-snapshot"
DEST_DIR="$HOME/Library/Application Support/moneywiz-mcp"
IDENTIFIER="com.moneywiz-mcp.snapshot"

die() { echo "error: $*" >&2; exit 1; }

[ "$#" -eq 1 ] || die "usage: $0 /absolute/path/to/MoneyWiz.sqlite"
SOURCE="$1"

case "$SOURCE" in
  /*) ;;
  *) die "the database path must be absolute" ;;
esac
case "$SOURCE" in
  "$HOME/Library/Containers/com.moneywiz."*/*.sqlite) ;;
  "$HOME/Library/Application Support/MoneyWiz/"*.sqlite) ;;
  "$HOME/Library/Application Support/SilverWiz/"*.sqlite) ;;
  *) die "not a known MoneyWiz database location: $SOURCE" ;;
esac
case "$SOURCE$DEST_DIR" in
  *\"* | *\\* | *$'\n'*) die "paths containing quotes, backslashes, or newlines are not supported" ;;
esac
case "$SOURCE" in
  */../* | */./*) die "the database path must not contain . or .. components" ;;
esac

# SQLite refuses to open a path containing any symlink (SQLITE_OPEN_NOFOLLOW),
# so catch that now rather than on every scheduled run. lstat works on the
# path components even when macOS blocks reading the container's contents.
check_no_symlinks() {
  local path="$1" current="" part
  local IFS=/
  set -f
  for part in ${path#/}; do
    current="$current/$part"
    if [ -L "$current" ]; then
      set +f
      die "$current is a symlink; use the real path"
    fi
  done
  set +f
}
check_no_symlinks "$SOURCE"
check_no_symlinks "$DEST_DIR"

mkdir -p "$BUILD_DIR"
clang -std=c11 -O2 -Wall -Wextra -Werror -Wpedantic -Wshadow -Wformat=2 \
  -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
  -DSNAPSHOT_SOURCE="\"$SOURCE\"" \
  -DSNAPSHOT_DEST_DIR="\"$DEST_DIR\"" \
  "$TOOL_DIR/moneywiz_snapshot.c" -lsqlite3 -o "$BINARY"

# Ad-hoc signature with the hardened runtime: macOS ties the privacy grant to
# this exact code, so a modified or replaced binary does not inherit it.
codesign --force --sign - --options runtime --identifier "$IDENTIFIER" "$BINARY"

echo "Built $BINARY"
echo "  copies: $SOURCE"
echo "  to:     $DEST_DIR/snapshot.sqlite"

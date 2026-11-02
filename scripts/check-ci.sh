#!/bin/bash
# Local CI simulation: runs the same commands, with the same flags, as
# .github/workflows/ci.yml. Every step is blocking, exactly like CI.
#
# Usage:
#   scripts/check-ci.sh          all CI jobs
#   scripts/check-ci.sh --fast   skip the slower jobs (pre-commit over all
#                                files, package build check); used by the
#                                pre-push hook
#
# Keep in sync with .github/workflows/ci.yml when either changes.

set -euo pipefail

FAST=0
case "${1:-}" in
  "") ;;
  --fast) FAST=1 ;;
  *) echo "usage: $0 [--fast]" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."

CURRENT_STEP=""
trap 'echo; echo "❌ Failed: $CURRENT_STEP" >&2' ERR

step() {
  CURRENT_STEP="$1"
  echo
  echo "▶ $1"
}

echo "🚀 Local CI simulation (same commands as GitHub Actions)"

step "Install dependencies"
uv sync --all-extras >/dev/null

# --- Code Quality job ---
step "Ruff linter"
uv run ruff check . --output-format=github

step "Ruff formatter"
uv run ruff format --check .

# CI also passes --install-types --non-interactive; that only tries to
# pip-install missing stub packages (uv environments have no pip), so it does
# not change the result. --no-strict-optional does, so it must match.
step "Mypy (CI flags: --no-strict-optional)"
uv run mypy src/ --no-strict-optional

step "Bandit"
uv run bandit -r src/

# --- Test job ---
step "Tests (all, excluding integration)"
uv run pytest --cov=moneywiz_mcp_server --cov-report=xml --cov-report=term-missing -m "not integration"

# --- Integration Test job ---
step "Integration tests"
uv run pytest tests/integration/ -v --tb=short

if [ "$FAST" -eq 0 ]; then
  # --- Pre-commit job ---
  step "Pre-commit hooks (all files)"
  uv run pre-commit run --all-files

  # --- Build Package job (built in a temporary directory) ---
  step "Build package and check metadata"
  build_dir="$(mktemp -d)"
  trap 'rm -rf -- "${build_dir:?}"' EXIT
  uv build --out-dir "$build_dir" >/dev/null
  uvx twine check "$build_dir"/*
fi

echo
if [ "$FAST" -eq 1 ]; then
  echo "✅ Fast checks passed (pre-commit and package build skipped)"
else
  echo "✅ All CI checks passed"
fi

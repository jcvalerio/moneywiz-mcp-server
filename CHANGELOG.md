# Changelog

All notable changes to MoneyWiz MCP Server will be documented in this file.

This project follows semantic versioning where possible. See `docs/ROADMAP.md` and `docs/RELEASING.md` for compatibility expectations.

## Unreleased

### Changed

- **Breaking:** Python 3.11 is now the minimum supported version. Python 3.10 reached end of life on 2026-10-01, and patched releases of some dependencies no longer support it. Python 3.13 is now tested in CI.
- `mcp` is constrained to `<2` until the server is migrated to the 2.x API.
- Upgraded locked dependencies to resolve published security advisories, including `mcp`, `starlette`, `pyjwt`, `cryptography`, `python-multipart`, `anyio`, `filelock`, and `virtualenv`.

### Added

- Claude Desktop configuration example for running the published PyPI package with `uvx`.

### Fixed

- Package `__version__` now reflects installed distribution metadata instead of a hardcoded value.
- Database auto-detection now finds the database under `Data/Library/Application Support`, where MoneyWiz stores it once iCloud sync is enabled, and skips the always-empty CloudKit shared-scope store kept alongside it.
- Database auto-detection no longer selects SQLite side files (`-wal`, `-shm`, `-journal`), ranks MoneyWiz-named files ahead of unrelated SQLite stores, and logs a warning instead of silently skipping directories that macOS privacy controls block.
- `setup_env.py` now uses the same detection logic as the server, so it finds databases relocated by iCloud sync.
- Core Data `Z_ENT` (entity) ids are now resolved dynamically per database instead of hardcoded, fixing silently wrong or missing data (transactions, tags, account balances, categories, scheduled transactions, budgets) on databases where MoneyWiz assigned different entity ids.

## 1.0.1 - 2026-05-11

Patch release to validate the PyPI publishing workflow without changing MCP behavior.

### Added

- PyPI publishing workflow draft using GitHub Actions trusted publishing and a protected `pypi` environment.

### Compatibility notes

- Breaking changes: none.
- MCP tool schema changes: none.
- Configuration changes: none.
- Financial calculation changes: none.
- Existing source-checkout installs remain supported.

## 1.0.0 - 2026-05-10

Initial stable baseline release to preserve current user workflows before larger roadmap changes.

### Added

- Roadmap planning for release stability, binary distribution, onboarding, and feature completeness.
- Initial release checklist, versioning policy, and MCP compatibility guidance.
- Stable-version usage and rollback guidance for source-checkout installs.
- GitHub Release artifact workflow for source distribution and wheel uploads.

### Changed

- Cleaned package metadata for the first stable baseline and future publishing workflows.

### Current capabilities

- Read-only MoneyWiz SQLite access.
- Account listing and account details.
- Transaction search with natural language date ranges.
- Expense analysis by category.
- Income vs expense analysis.
- Savings recommendations.
- Spending/category/income trend analytics.
- Scheduled transaction analysis.
- Salary commitment planning.
- Budget status and budget-vs-actual analysis.

### Compatibility notes

- Existing source-checkout usage with `uv` and `.venv/bin/python -m moneywiz_mcp_server` should remain documented for users who want to pin this baseline.
- Future releases should call out any MCP tool schema, configuration, or response model changes explicitly.

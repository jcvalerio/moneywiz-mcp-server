# Changelog

All notable changes to MoneyWiz MCP Server will be documented in this file.

This project follows semantic versioning where possible. See `docs/ROADMAP.md` and `docs/RELEASING.md` for compatibility expectations.

## Unreleased

### Added

- PyPI publishing workflow draft using GitHub Actions trusted publishing and a protected `pypi` environment.

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

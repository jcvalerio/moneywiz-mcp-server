# Changelog

All notable changes to MoneyWiz MCP Server will be documented in this file.

This project follows semantic versioning where possible. See `docs/ROADMAP.md` and future release documentation for compatibility expectations.

## Unreleased

### Added

- Roadmap planning for release stability, binary distribution, onboarding, and feature completeness.
- Stable-version usage and rollback guidance for source-checkout installs.

### Changed

- Tightened release/versioning policy, MCP compatibility expectations, and release checklist guidance.

## 1.0.0 - TBD

Initial stable baseline release to preserve current user workflows before larger roadmap changes.

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

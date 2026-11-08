# Changelog

All notable changes to MoneyWiz MCP Server will be documented in this file.

This project follows semantic versioning where possible. See `docs/ROADMAP.md` and `docs/RELEASING.md` for compatibility expectations.

## Unreleased

### Added

- `analyze_monthly_cash_flow`: a monthly cash view. For each calendar month and currency, it checks whether scheduled income covers what has to leave bank accounts: payments from bank accounts, loan payments, savings contributions, and what each credit card needs from the bank. Bills charged to a card count only as part of that card's payment.
  - **Card payments:** a one-time payment scheduled after the statement closed is confirmed. Otherwise the statement is computed from the card's transactions and its closing day. A closed statement shows the charges minus payments already made. An open one shows charges so far plus card bills scheduled until it closes.
  - **Each month also reports:** a verdict (covered, tight or short), combined totals, the projected bank balance at month end, and the monthly budgets still to spend.
- `analyze_salary_breakdown` splits loan payments into principal and cost (interest, insurance, fees) using the loan's MoneyWiz payment plan. The plan names its principal category, so category names are never used to guess. Each month's interest comes from the plan's payment for that month, not the schedule's fixed split, and drift between the two is reported. `commitments_by_kind` reports `loan_principal` and `loan_cost`, and each commitment reports `principal_in_period` and `cost_in_period`. A new argument, `count_loan_principal=false`, leaves principal out to give the pure expense view. Loan payments that can't be split stay `debt_payment` and are listed in `loan_payment_notes`.
- Scheduled transfers report `recipient_account_name`.

### Compatibility notes

- **MCP tool schema changes:**
  - `analyze_salary_breakdown` adds the optional arguments `salary_currency`, `salary_frequency`, `display_currency`, `exchange_rates` and `count_savings_as_commitments`.
  - `analyze_salary_breakdown` adds the response fields `income_in_period`, `income_sources`, `commitments_by_kind`, `transfers_in_period`, `unclassified_transfers`, `display_currency`, `totals_in_display_currency`, `exchange_rates_used` and `currencies_without_rate`, plus `kind` on each commitment.
  - `coverage_analysis` can now be `unknown` (no income found) or `incomplete` (a currency has no exchange rate).
  - **Breaking:** in `get_commitments_ending_timeline`, `monthly_relief` and `total_monthly_relief` are now `{currency: amount}` maps instead of one float that mixed currencies. Relief is the amount of each payment, so it is no longer described as monthly.
  - `get_scheduled_transactions` lists one-time schedules (`commitment_type: one_time`) and counts them in its summary.
- **Behavior changes:**
  - `salary_amount` without `salary_currency` returns an error when the currency can't be inferred from the schedules or the MoneyWiz base currency. It no longer assumes USD.
  - When `salary_amount` is omitted, income comes from the scheduled deposits. The old placeholder salary of 5000 is gone.

### Fixed

- Investment and Forex (crypto) account balances now include what the accounts hold. Investment accounts add their shares at the latest price to their cash. Forex accounts are valued by the quantity held in each currency, not by the sum of past transaction values, which mixed historical prices and was often negative. Accounts report `cash_balance`, `holdings_value` and `holdings_without_price`, and `balance` is their total.
- `get_account` failed on every account: its response was missing `account_info` and `last_four_digits`, and `created_date` was a raw timestamp. It now returns them, with `created_date` as an ISO date.
- `analyze_salary_breakdown` counts every paycheck in the period (a biweekly salary over 3 months is 7 payments, not 1) and income in every currency.
- Amounts in different currencies are no longer compared or summed as if they were the same currency. They are kept per currency and combined using MoneyWiz's latest exchange rates.
- Scheduled transfers are classified from the MoneyWiz types of their accounts. Loan payments and savings contributions count as commitments. Credit card payments, internal moves, and transfers out of a card or loan don't.
- One-time scheduled transactions were never loaded. Schedules that end ("after N repeats" or "on date") were treated as endless. Both are now counted correctly.
- The MoneyWiz base currency is detected from the currency with the most rate-1 transactions. Rates are read from deposits, withdrawals and refunds only, because transfers store the rate between their two accounts.
- Scheduled transactions split across several categories (for example a loan payment's principal, interest and insurance, or a subscription plus its tax) reported only one category, the first stored. `get_scheduled_transactions` and each commitment in `analyze_salary_breakdown` now include `category_splits` with every category and its amount, and `category` is the largest share.
- The MCP handshake now reports the server's own version. It previously reported the `mcp` SDK's version (for example `1.30.0`) because FastMCP 1.x has no version setting.

## 2.0.0 - 2026-11-02

Major release that corrects data 1.0.x returned incorrectly. On current MoneyWiz 3 databases, 1.0.1 computed account balances from transfers only, looked up categories, payees, budgets, and tags in the wrong records, shifted dates by the machine's UTC offset, and misread most time-period phrases, all without errors. The corrections change financial results and date ranges for the same inputs, and Python 3.10 support is dropped, so this is a major version under the [versioning policy](docs/RELEASING.md#versioning-policy).

### Compatibility notes

- **Breaking changes:**
  - Python 3.11 or newer is required.
  - Financial results differ from 1.0.x for the same inputs: balances, categories, payees, budgets, scheduled transactions, and tags are now read correctly (see Fixed).
  - Dates are in local time, and date ranges are no longer shifted by the UTC offset.
  - `time_period` phrases are interpreted as written, and unsupported phrases return an error instead of silently using 3 months.
- **MCP tool schema changes:** none. Tool names, arguments, defaults, and response fields are unchanged; the `time_period` descriptions now list the supported phrases.
- **Configuration changes:** none required. On macOS, if Claude Desktop cannot open the database, use the optional snapshot helper and point `MONEYWIZ_DB_PATH` at its snapshot.

### Upgrade notes

- Source checkout: `git fetch --tags && git checkout v2.0.0 && uv sync --all-extras`, then restart Claude Desktop.
- PyPI with `uvx`: change the pinned version to `moneywiz-mcp-server==2.0.0` and restart Claude Desktop.
- Expect different numbers than 1.0.x; the new values match the MoneyWiz app.

### Rollback

- Source checkout: `git checkout v1.0.1 && uv sync --all-extras`.
- PyPI with `uvx`: pin `moneywiz-mcp-server==1.0.1`.

### Changed

- **Breaking:** Python 3.11 is now the minimum supported version. Python 3.10 reached end of life on 2026-10-01, and patched releases of some dependencies no longer support it. Python 3.13 is now tested in CI.
- `mcp` is constrained to `<2` until the server is migrated to the 2.x API.
- Upgraded locked dependencies to resolve published security advisories, including `mcp`, `starlette`, `pyjwt`, `cryptography`, `python-multipart`, `anyio`, `filelock`, and `virtualenv`.

### Added

- `tools/moneywiz-snapshot`: a least-privilege way to give the server access on macOS. A single-purpose helper, run by launchd, copies the MoneyWiz database to a private snapshot; only that helper needs Full Disk Access, so Claude Desktop and the MCP server need none.
- Claude Desktop configuration example for running the published PyPI package with `uvx`.

### Fixed

- Time period phrases are parsed with a real grammar. Previously, unsupported phrases such as "last 5 years" silently fell back to 3 months, "last 13 months" became 3 months and "last 60 days" became 7 days, because the parser matched substrings. Supported: `last N days|weeks|months|years`, `last week|month|year`, `this week|month|year`, `year to date`, `today`, `yesterday`, and `all time`; months and years use calendar arithmetic. Unsupported phrases now return an error listing the supported formats.
- Dates are now converted using the Core Data reference date in UTC. Previously every conversion applied the machine's UTC offset, so outside UTC, searches and budget, scheduled, and category date ranges were shifted by that many hours (west of UTC, recent transactions were missing from results) and transaction dates showed UTC clock time, putting evening entries on the next day.
- Package `__version__` now reflects installed distribution metadata instead of a hardcoded value.
- Database auto-detection now finds the database under `Data/Library/Application Support`, where MoneyWiz stores it once iCloud sync is enabled, and skips the always-empty CloudKit shared-scope store kept alongside it.
- Database auto-detection no longer selects SQLite side files (`-wal`, `-shm`, `-journal`), ranks MoneyWiz-named files ahead of unrelated SQLite stores, and logs a warning instead of silently skipping directories that macOS privacy controls block.
- `setup_env.py` now uses the same detection logic as the server, so it finds databases relocated by iCloud sync.
- Core Data `Z_ENT` (entity) ids are now resolved dynamically per database instead of hardcoded, fixing silently wrong or missing data (transactions, tags, account balances, categories, scheduled transactions, budgets) on databases where MoneyWiz assigned different entity ids, including current MoneyWiz 3 databases. Account balances now include every transaction type (deposits, withdrawals, transfers, refunds, reconciliations, investment, and budget transfers).

### Development

- `scripts/check-ci.sh` runs every CI job with CI's commands and flags, all blocking; `--fast` is used by the pre-push hook.
- Pre-commit runs ruff, mypy, and bandit through `uv`, so tool versions come from `uv.lock` and match CI.
- The Claude review workflow can post reviews again.

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

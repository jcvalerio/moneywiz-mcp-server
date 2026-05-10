# MoneyWiz MCP Server Roadmap

## Project Name

**MoneyWiz MCP Server** remains the recommended public name. It is clear, searchable, neutral, and consistent with the repository/package identity.

Recommended positioning:

> MoneyWiz MCP Server gives AI assistants secure, read-only access to MoneyWiz data for privacy-conscious personal finance analysis, including spending trends, savings recommendations, budgets, scheduled transactions, and salary planning.

## Roadmap Strategy

Start with **release stability and install simplicity** before expanding features.

Reasoning:

- Existing users may already depend on the current clone/uv setup.
- New feature work can change tool schemas, response models, or setup behavior.
- A tagged release gives users a stable fallback version.
- Binary/package distribution makes adoption easier before the project grows.
- A release process creates discipline: versioning, changelog, migration notes, and rollback paths.

This roadmap intentionally avoids competitor comparisons. It focuses on user value, stability, reliability, and ease of adoption.

## File Ownership

Use each file for a distinct purpose:

- `docs/ROADMAP.md` — planned work, task status, sequencing, and acceptance criteria.
- `CHANGELOG.md` — user-facing summary of released changes by version/date.
- `docs/RELEASING.md` — maintainer checklist for creating releases.
- `specs/` — deeper technical designs, investigations, and implementation notes.
- GitHub Issues — execution tracking for active tasks.
- GitHub Projects — live board/status view across issues and PRs.

## Tracking Workflow

Recommended flow:

1. Create a release foundation first.
2. Tag the current stable behavior as the first public baseline.
3. Document how existing users can stay on that version.
4. Add binary/package distribution.
5. Create GitHub Project and seed only the first wave of issues.
6. Implement feature improvements through small PRs.
7. Update this roadmap after each PR merges.
8. Update `CHANGELOG.md` only for user-facing changes.

## Versioning Recommendation

Use semantic versioning:

- Patch: bug fixes and documentation-only improvements, e.g. `1.0.1`.
- Minor: backwards-compatible tools/features, e.g. `1.1.0`.
- Major: breaking tool schemas, setup changes, or output contract changes, e.g. `2.0.0`.

For MCP users, treat these as potentially breaking unless carefully preserved:

- tool renames,
- argument renames,
- required argument changes,
- response field removals/renames,
- behavior changes that alter financial calculations,
- database setup/config changes.

## GitHub Project Recommendation

Create a GitHub Project named:

> MoneyWiz MCP Server Roadmap

Suggested board statuses:

- Backlog
- Ready
- In Progress
- Review
- Done

Suggested custom fields:

- Priority: `P0`, `P1`, `P2`
- Area: `release`, `analytics`, `database`, `docs`, `packaging`, `onboarding`, `security`, `ci`, `community`
- Size: `XS`, `S`, `M`
- Risk: `low`, `medium`, `high`

## Labels

Suggested labels:

- `area:release`
- `area:analytics`
- `area:database`
- `area:docs`
- `area:packaging`
- `area:ci`
- `area:onboarding`
- `area:security`
- `area:community`
- `type:feature`
- `type:docs`
- `type:chore`
- `type:test`
- `priority:p0`
- `priority:p1`
- `priority:p2`
- `size:xs`
- `size:s`
- `size:m`

## Status Legend

- `Not started` — planned but not yet active.
- `Ready` — sufficiently defined and ready for implementation.
- `In progress` — issue or PR is actively being worked on.
- `Blocked` — waiting on a decision or dependency.
- `Done` — merged and released or ready for the next release.

## Task Summary

| ID | Task | Priority | Size | Status | Issue | PR |
|---|---|---:|---:|---|---|---|
| MW-000 | Document release/versioning policy | P0 | XS | Not started | TBD | TBD |
| MW-001 | Add initial changelog | P0 | XS | Not started | TBD | TBD |
| MW-002 | Add release checklist | P0 | XS | Not started | TBD | TBD |
| MW-003 | Tag current stable baseline release | P0 | XS | Not started | TBD | TBD |
| MW-004 | Document how existing users stay on a stable version | P0 | XS | Not started | TBD | TBD |
| MW-005 | Clean package metadata for publishing | P0 | XS | Not started | TBD | TBD |
| MW-006 | Add GitHub release workflow draft | P0 | S | Not started | TBD | TBD |
| MW-007 | Evaluate standalone macOS binary options | P0 | XS | Not started | TBD | TBD |
| MW-008 | Add standalone macOS binary build workflow | P0 | M | Not started | TBD | TBD |
| MW-009 | Add diagnostics command | P1 | M | Not started | TBD | TBD |
| MW-010 | Improve Claude Desktop config generation | P1 | S | Not started | TBD | TBD |
| MW-011 | Add PyPI publishing workflow draft | P1 | S | Not started | TBD | TBD |
| MW-012 | Document `uvx` install path | P1 | XS | Not started | TBD | TBD |
| MW-013 | Support database folder paths | P1 | XS | Not started | TBD | TBD |
| MW-014 | Add exported backup detection to setup script | P1 | S | Not started | TBD | TBD |
| MW-015 | Add setup mode selection | P1 | S | Not started | TBD | TBD |
| MW-016 | Add category listing service | P1 | S | Not started | TBD | TBD |
| MW-017 | Add `list_categories` MCP tool | P1 | XS | Not started | TBD | TBD |
| MW-018 | Add net worth service | P1 | S | Not started | TBD | TBD |
| MW-019 | Add `calculate_net_worth` MCP tool | P1 | XS | Not started | TBD | TBD |
| MW-020 | Add all-time financial stats service | P1 | M | Not started | TBD | TBD |
| MW-021 | Add `get_financial_stats` MCP tool | P1 | XS | Not started | TBD | TBD |
| MW-022 | Rewrite README opening positioning | P1 | XS | Not started | TBD | TBD |
| MW-023 | Add capability overview table to README | P1 | XS | Not started | TBD | TBD |
| MW-024 | Add privacy and security documentation | P1 | S | Not started | TBD | TBD |
| MW-025 | Add supported MoneyWiz versions/schema notes | P1 | S | Not started | TBD | TBD |
| MW-026 | Draft Homebrew tap/formula instructions | P2 | S | Not started | TBD | TBD |
| MW-027 | Add demo assets plan | P2 | XS | Not started | TBD | TBD |
| MW-028 | Add marketplace listing checklist | P2 | XS | Not started | TBD | TBD |
| MW-029 | Add issue templates | P1 | XS | Not started | TBD | TBD |
| MW-030 | Raise coverage threshold gradually | P2 | S | Not started | TBD | TBD |

## Milestone 0: Release Foundation

Goal: create a stable baseline and release process before changing user-facing behavior.

### MW-000: Document release/versioning policy

- **Area:** release, docs
- **Priority:** P0
- **Size:** XS
- **Expected outcome:** Users and maintainers understand how versions map to compatibility.
- **Acceptance criteria:**
  - Versioning policy is documented in `docs/RELEASING.md` or README.
  - Defines patch/minor/major criteria.
  - Calls out MCP tool schema compatibility expectations.

### MW-001: Add initial changelog

- **Area:** release, docs
- **Priority:** P0
- **Size:** XS
- **Expected outcome:** Project has a user-facing changelog before the first tagged baseline.
- **Acceptance criteria:**
  - `CHANGELOG.md` exists.
  - Includes `Unreleased` section.
  - Includes initial baseline section such as `1.0.0` or `0.1.0` depending release decision.
  - Notes current capabilities at a high level.

### MW-002: Add release checklist

- **Area:** release, docs
- **Priority:** P0
- **Size:** XS
- **Expected outcome:** Maintainers have a repeatable release process.
- **Acceptance criteria:**
  - `docs/RELEASING.md` exists.
  - Checklist covers version bump, changelog, tests, tag, GitHub release, artifacts, and documentation updates.
  - Includes rollback guidance for users.

### MW-003: Tag current stable baseline release

- **Area:** release
- **Priority:** P0
- **Size:** XS
- **Depends on:** MW-000, MW-001, MW-002
- **Expected outcome:** Existing users have a stable tag they can pin to before larger roadmap work starts.
- **Acceptance criteria:**
  - Maintainer selects baseline version, likely `v1.0.0` if current README/package claims production-ready 1.0.0.
  - Git tag is created from the chosen stable commit.
  - GitHub Release notes include install instructions and compatibility notes.
  - README explains how to install or checkout the stable tag.

### MW-004: Document how existing users stay on a stable version

- **Area:** release, docs
- **Priority:** P0
- **Size:** XS
- **Expected outcome:** Current users can keep using the known-good version while new versions evolve.
- **Acceptance criteria:**
  - README includes `git checkout vX.Y.Z` instructions.
  - Docs explain how to upgrade intentionally.
  - Docs explain how to roll back.
  - Claude Desktop config examples remain compatible with pinned checkout installs.

### MW-005: Clean package metadata for publishing

- **Area:** packaging
- **Priority:** P0
- **Size:** XS
- **Expected outcome:** Package metadata is ready for public release and packaging.
- **Acceptance criteria:**
  - Real author/maintainer metadata replaces placeholder values.
  - Classifiers and keywords are accurate.
  - Versioning approach is documented.
  - `uv build` succeeds.

### MW-006: Add GitHub release workflow draft

- **Area:** release, ci
- **Priority:** P0
- **Size:** S
- **Expected outcome:** Releases can be prepared consistently from GitHub.
- **Acceptance criteria:**
  - Workflow triggers only on tags or GitHub Releases.
  - Builds package artifacts.
  - Uploads artifacts to the release.
  - Does not publish to PyPI unless explicitly configured later.

### MW-007: Evaluate standalone macOS binary options

- **Area:** packaging
- **Priority:** P0
- **Size:** XS
- **Expected outcome:** Decide whether to use PyInstaller, Briefcase, or another approach for a single-file macOS release.
- **Acceptance criteria:**
  - Short decision record added under `docs/decisions/` or `specs/`.
  - Includes pros/cons, signing/notarization considerations, and estimated maintenance cost.
  - Explicitly chooses the first implementation path.
  - No binary implementation in this task.

### MW-008: Add standalone macOS binary build workflow

- **Area:** packaging, ci
- **Priority:** P0
- **Size:** M
- **Depends on:** MW-007
- **Expected outcome:** GitHub Releases can include a downloadable macOS binary.
- **Acceptance criteria:**
  - Release workflow builds binary on a macOS runner.
  - Artifact smoke test verifies `--help`, version, or diagnostics command works.
  - README documents binary install.
  - Release notes explain binary vs source install options.

## Milestone 1: Install and Setup Experience

Goal: make setup and troubleshooting easier for both existing and new users.

### MW-009: Add diagnostics command

- **Area:** onboarding
- **Priority:** P1
- **Size:** M
- **Expected outcome:** Users can run a command that validates DB path, read-only access, schema basics, and MCP startup readiness.
- **Acceptance criteria:**
  - Command exits 0 when healthy and non-zero when unhealthy.
  - Reports actionable fixes for common failures.
  - Does not print sensitive transaction data.
  - Tests cover success and common failure modes.

### MW-010: Improve Claude Desktop config generation

- **Area:** onboarding, docs
- **Priority:** P1
- **Size:** S
- **Expected outcome:** Setup prints or writes an exact Claude Desktop JSON snippet with absolute paths.
- **Acceptance criteria:**
  - Generated config supports source checkout and binary install modes.
  - User can copy/paste without editing except server name if desired.
  - README references this flow.

### MW-011: Add PyPI publishing workflow draft

- **Area:** ci, packaging
- **Priority:** P1
- **Size:** S
- **Expected outcome:** Maintainers can publish releases to PyPI from GitHub Actions using trusted publishing or configured secrets.
- **Acceptance criteria:**
  - Workflow triggers only on release/tag.
  - Includes build and artifact upload.
  - Documented in release instructions.
  - Does not publish automatically on every push.

### MW-012: Document `uvx` install path

- **Area:** docs, packaging
- **Priority:** P1
- **Size:** XS
- **Depends on:** MW-011 and PyPI availability
- **Expected outcome:** Users can install/run without cloning once the package is published.
- **Acceptance criteria:**
  - README includes `uvx moneywiz-mcp-server` or equivalent supported command.
  - Claude Desktop examples include uvx-based config if reliable.
  - Legacy clone-based setup remains documented.

### MW-013: Support database folder paths

- **Area:** onboarding, database
- **Priority:** P1
- **Size:** XS
- **Expected outcome:** Configuration accepts either a direct SQLite file path or a folder containing `ipadMoneyWiz.sqlite`.
- **Acceptance criteria:**
  - Config normalizes folder paths to the SQLite file.
  - Existing direct file paths keep working.
  - Tests cover file path, folder path, and missing DB path.

### MW-014: Add exported backup detection to setup script

- **Area:** onboarding
- **Priority:** P1
- **Size:** S
- **Expected outcome:** `setup_env.py` can find exported MoneyWiz backup folders in common locations or accept a backup folder from the user.
- **Acceptance criteria:**
  - Detects `iMoneyWiz-Data-Backup-*` folders.
  - Finds `ipadMoneyWiz.sqlite` inside selected folder.
  - Clearly labels live DB vs backup DB choices.
  - Manual path flow supports file or folder.

### MW-015: Add setup mode selection

- **Area:** onboarding, security
- **Priority:** P1
- **Size:** S
- **Expected outcome:** Setup asks users to choose between `live_read_only` and `exported_backup` mode.
- **Acceptance criteria:**
  - `.env` includes `MONEYWIZ_DB_MODE=live_read_only|exported_backup`.
  - Setup explains privacy/safety tradeoffs in plain language.
  - README documents both modes.

## Milestone 2: Feature Completeness

Goal: add common high-level finance overview tools while keeping responses structured, multi-currency aware, and safe.

### MW-016: Add category listing service

- **Area:** database, analytics
- **Priority:** P1
- **Size:** S
- **Expected outcome:** A reusable service method returns MoneyWiz categories with IDs, names, parent/root hierarchy when available, and transaction counts if cheap to compute.
- **Acceptance criteria:**
  - Category service or transaction service method exists.
  - Handles uncategorized/missing names safely.
  - Unit tests cover flat categories and parent/child categories.
  - No MCP tool registration yet; this PR is service/model only.

### MW-017: Add `list_categories` MCP tool

- **Area:** analytics
- **Priority:** P1
- **Size:** XS
- **Depends on:** MW-016
- **Expected outcome:** Users can ask for all MoneyWiz categories through MCP.
- **Acceptance criteria:**
  - `list_categories` is registered with FastMCP.
  - Structured Pydantic response model exists.
  - Supports optional filters such as `include_empty` and `category_type` if available.
  - Integration/tool test added.
  - README tool list updated.

### MW-018: Add net worth service

- **Area:** analytics
- **Priority:** P1
- **Size:** S
- **Expected outcome:** A reusable service calculates assets, liabilities, net worth, and account breakdown by currency.
- **Acceptance criteria:**
  - Service handles multi-currency without fake conversion.
  - Positive balances count as assets; negative balances count as liabilities.
  - Response includes by-currency totals and account summaries.
  - Unit tests cover positive, negative, zero, and multi-currency balances.

### MW-019: Add `calculate_net_worth` MCP tool

- **Area:** analytics
- **Priority:** P1
- **Size:** XS
- **Depends on:** MW-018
- **Expected outcome:** Users can ask for net worth directly using structured multi-currency output.
- **Acceptance criteria:**
  - Tool is registered with FastMCP.
  - Returns structured Pydantic response.
  - Includes `total_assets`, `total_liabilities`, `net_worth`, `by_currency`, and `accounts`.
  - README and example prompts updated.

### MW-020: Add all-time financial stats service

- **Area:** analytics
- **Priority:** P1
- **Size:** M
- **Expected outcome:** A reusable service returns all-time income, expenses, transaction counts, date range, largest transactions, and yearly breakdowns.
- **Acceptance criteria:**
  - Uses existing transaction/category logic where possible.
  - Handles empty databases gracefully.
  - Returns per-currency totals rather than merging currencies incorrectly.
  - Unit tests cover normal, empty, and multi-year datasets.

### MW-021: Add `get_financial_stats` MCP tool

- **Area:** analytics
- **Priority:** P1
- **Size:** XS
- **Depends on:** MW-020
- **Expected outcome:** Users can ask for a complete historical financial overview.
- **Acceptance criteria:**
  - Tool is registered with FastMCP.
  - Structured Pydantic response model exists.
  - Integration/tool test added.
  - README updated.

## Milestone 3: Positioning and Trust

Goal: make the project's capabilities, safety model, and maintenance expectations clear.

### MW-022: Rewrite README opening positioning

- **Area:** docs
- **Priority:** P1
- **Size:** XS
- **Expected outcome:** README states the unique value proposition clearly and positively.
- **Acceptance criteria:**
  - Opening communicates privacy-first, read-only access, advanced analytics, budgets, and scheduled transactions.
  - Includes target users: MoneyWiz users who want AI-assisted personal finance insights.
  - Quick start remains near the top.

### MW-023: Add capability overview table to README

- **Area:** docs
- **Priority:** P1
- **Size:** XS
- **Expected outcome:** README clearly shows what this project supports without comparing against other projects.
- **Acceptance criteria:**
  - Table lists capabilities such as read-only mode, natural language dates, multi-currency summaries, category hierarchy, budgets, scheduled transactions, salary planning, net worth, and financial stats.
  - Planned capabilities are labeled honestly.
  - No competitor names or comparative claims are included.

### MW-024: Add privacy and security documentation

- **Area:** security, docs
- **Priority:** P1
- **Size:** S
- **Expected outcome:** Users understand what data is accessed, what is not modified, and how to use backup mode.
- **Acceptance criteria:**
  - New or updated docs explain local-only access, read-only SQLite mode, `.env`, and data exposure to MCP clients.
  - Includes best practices: backup mode, least-privilege paths, and avoiding sharing sensitive outputs.
  - README links to it.

### MW-025: Add supported MoneyWiz versions/schema notes

- **Area:** docs, database
- **Priority:** P1
- **Size:** S
- **Expected outcome:** Users know which MoneyWiz variants/paths are supported and how to report schema mismatches.
- **Acceptance criteria:**
  - README or docs list known macOS app bundle paths and database names.
  - Includes troubleshooting instructions for schema issues.
  - Includes GitHub issue template fields for MoneyWiz version and DB source.

## Milestone 4: Later Distribution and Growth

Goal: add optional install channels and adoption support after the first release/binary path is stable.

### MW-026: Draft Homebrew tap/formula instructions

- **Area:** packaging, docs
- **Priority:** P2
- **Size:** S
- **Expected outcome:** Users have a Homebrew-based install path once releases are available.
- **Acceptance criteria:**
  - Formula draft or tap plan exists.
  - README documents intended install command.
  - Dependencies and update process are clear.

### MW-027: Add demo assets plan

- **Area:** docs
- **Priority:** P2
- **Size:** XS
- **Expected outcome:** Define demo screenshots/GIF/video needed to improve onboarding and user confidence.
- **Acceptance criteria:**
  - Spec lists 3-5 demo prompts and desired screenshots.
  - Redaction/privacy requirements are documented.
  - No private financial data is committed.

### MW-028: Add marketplace listing checklist

- **Area:** community, docs
- **Priority:** P2
- **Size:** XS
- **Expected outcome:** Track listings across relevant MCP directories.
- **Acceptance criteria:**
  - Checklist includes relevant MCP directories and required metadata/assets.
  - Links are added after listings are claimed or updated.
  - Claims remain factual and non-comparative.

### MW-029: Add issue templates

- **Area:** community, docs
- **Priority:** P1
- **Size:** XS
- **Expected outcome:** Bug reports and feature requests include enough information to reproduce MoneyWiz/schema/setup issues.
- **Acceptance criteria:**
  - Bug report template asks for OS version, MoneyWiz version, install method, DB mode, error logs, and sanitized schema details.
  - Feature request template asks for use case and expected output.
  - Security issues point to `SECURITY.md`.

### MW-030: Raise coverage threshold gradually

- **Area:** test, ci
- **Priority:** P2
- **Size:** S
- **Expected outcome:** Increase confidence without blocking near-term feature work.
- **Acceptance criteria:**
  - Current coverage is measured.
  - A realistic next threshold is selected.
  - Tests are added for new services/tools before raising threshold.
  - CI remains green.

## Suggested First Wave of GitHub Issues

Create issues for these first. They protect existing users and establish a release process before broader roadmap work:

1. MW-000 — Document release/versioning policy
2. MW-001 — Add initial changelog
3. MW-002 — Add release checklist
4. MW-003 — Tag current stable baseline release
5. MW-004 — Document how existing users stay on a stable version
6. MW-005 — Clean package metadata for publishing
7. MW-006 — Add GitHub release workflow draft
8. MW-007 — Evaluate standalone macOS binary options
9. MW-008 — Add standalone macOS binary build workflow
10. MW-009 — Add diagnostics command

## PI Agent Usage Pattern

For each task, start a new chat or prompt with:

```text
Implement MW-XXX from docs/ROADMAP.md.
Keep the PR small and focused. Do not implement adjacent tasks.
Update tests and docs required by the acceptance criteria.
Run the relevant quality checks and summarize results.
```

# Releasing MoneyWiz MCP Server

This document defines the release and versioning process for maintainers.

## Goals

- Preserve a stable baseline for existing users.
- Make upgrades intentional and documented.
- Keep MCP tool schemas and response contracts predictable.
- Provide release artifacts that reduce local setup complexity over time.
- Clearly communicate compatibility, migration, and rollback guidance.

## Versioning Policy

MoneyWiz MCP Server uses semantic versioning for public releases. Release tags use a `v` prefix, for example `v1.0.0`, and the package version in `pyproject.toml` uses the matching bare version, for example `1.0.0`.

- **Patch** (`1.0.1`): bug fixes, documentation corrections, dependency maintenance, test/CI maintenance, and other changes that do not alter MCP tool contracts, configuration requirements, or financial calculation behavior.
- **Minor** (`1.1.0`): backwards-compatible additions such as new tools, new optional arguments with safe defaults, new response fields, new analytics, or new install methods that preserve existing source-checkout usage.
- **Major** (`2.0.0`): breaking changes such as renamed/removed tools, required argument changes, removed or renamed response fields, configuration changes that require user action, or behavior changes that materially alter financial calculations.

When in doubt, choose the more conservative version bump and document the compatibility impact in `CHANGELOG.md` and GitHub Release notes.

## MCP Compatibility Policy

Treat MCP tool contracts as user-facing API. Existing users may have saved Claude Desktop configuration, prompts, workflows, or downstream scripts that depend on current behavior.

Compatibility-sensitive areas include:

- Tool names.
- Tool descriptions when they change expected usage.
- Tool argument names, types, defaults, and required/optional status.
- Response model names, field names, field types, and field meaning.
- Error behavior that users may rely on for troubleshooting.
- Financial calculation formulas and date-range interpretation.
- Database path/configuration behavior.
- Claude Desktop configuration examples and source-checkout startup commands.

Backward-compatible changes usually include:

- Adding a new MCP tool.
- Adding an optional argument with the same default behavior as before.
- Adding a response field while preserving existing fields and meanings.
- Improving documentation, logging, validation messages, or tests without changing tool output contracts.

Breaking changes include:

- Renaming or removing an MCP tool.
- Renaming, removing, or changing the type of an argument.
- Making an optional argument required.
- Removing, renaming, or changing the meaning of a response field.
- Changing calculations in a way that users would see different financial results for the same inputs.
- Requiring users to change `.env`, database paths, install commands, or Claude Desktop configuration.

Breaking changes require a major version unless maintainers decide not to publish the change until a compatibility path exists.

## Stable Version Guidance for Users

For source-checkout installs, a stable release tag is the safest way to stay on known-good behavior. After the first baseline release is tagged, users can pin to it with:

```bash
git fetch --tags
git checkout v1.0.0
uv sync --all-extras
uv run python setup_env.py
```

The existing Claude Desktop configuration remains compatible with a pinned checkout as long as the checkout path does not move:

```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "/ABSOLUTE/PATH/TO/moneywiz-mcp-server/.venv/bin/python",
      "args": ["-m", "moneywiz_mcp_server"],
      "cwd": "/ABSOLUTE/PATH/TO/moneywiz-mcp-server"
    }
  }
}
```

To upgrade intentionally, read the release notes first, then check out the desired tag:

```bash
git fetch --tags
git checkout vX.Y.Z
uv sync --all-extras
```

To roll back, return to the previous known-good tag and restart Claude Desktop:

```bash
git fetch --tags
git checkout vPREVIOUS_VERSION
uv sync --all-extras
```

## Release Checklist

### 1. Prepare the release branch

- [ ] Start from an up-to-date `main` branch.
- [ ] Confirm CI is green on `main`.
- [ ] Create a small release branch, for example `release/vX.Y.Z`.
- [ ] Review merged changes since the previous tag.
- [ ] Identify compatibility-sensitive changes using the MCP Compatibility Policy above.
- [ ] Confirm whether the release is patch, minor, or major.

### 2. Run local checks

- [ ] Run linting:

  ```bash
  uv run ruff check . --output-format=github
  ```

- [ ] Run formatting check:

  ```bash
  uv run ruff format --check .
  ```

- [ ] Run type checking:

  ```bash
  uv run mypy src/ --install-types --non-interactive --no-strict-optional
  ```

- [ ] Run tests:

  ```bash
  uv run pytest tests/
  ```

- [ ] For documentation-only releases, still run at least lint/format checks and note any skipped checks in the PR and release notes.

### 3. Update version and changelog

- [ ] Update `pyproject.toml` to the release version if it is not already set.
- [ ] Update `CHANGELOG.md`:
  - [ ] move relevant items from `Unreleased` into the new version section,
  - [ ] set the release date,
  - [ ] summarize user-facing changes,
  - [ ] include compatibility notes,
  - [ ] include migration and rollback notes when needed.
- [ ] Confirm `README.md` install and Claude Desktop instructions still match the release.
- [ ] Confirm `docs/RELEASING.md` is still accurate.

### 4. Build artifacts

- [ ] Run the package build:

  ```bash
  uv build
  ```

- [ ] Verify package artifacts are created under `dist/`.
- [ ] Smoke test the built package where practical.
- [ ] If binary release is configured in a later task, build the macOS binary and smoke test it.
- [ ] Do not promise binary, Homebrew, or PyPI install paths until the corresponding release workflow exists and has been verified.

### 5. Merge release metadata

- [ ] Open a PR with only release metadata and documentation changes when possible.
- [ ] Confirm CI passes on the PR.
- [ ] Merge the PR into `main`.
- [ ] Pull the merged `main` locally before tagging.

### 6. Tag and publish

- [ ] Create an annotated tag from the merged release commit:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

- [ ] Create a GitHub Release from the tag.
- [ ] Upload package artifacts from `dist/`.
- [ ] Upload binary artifacts only if binary release support has been implemented and verified.
- [ ] Include install, upgrade, compatibility, and rollback instructions in release notes.

### 7. After release

- [ ] Verify release artifacts are downloadable.
- [ ] Verify documented install commands work from a clean checkout.
- [ ] Verify the source-checkout Claude Desktop configuration still works.
- [ ] Update marketplace listings if applicable.
- [ ] Create follow-up issues for any release problems.

## Baseline Release Guidance

The first release should preserve existing source-checkout usage so current users have a stable version to pin before the roadmap introduces packaging and feature changes.

Recommended baseline actions:

1. Confirm the current package version and README claims support a `v1.0.0` baseline.
2. Confirm no pending user-facing changes need to land before the baseline tag.
3. Run the full release checklist above.
4. Tag the current stable behavior as `v1.0.0`.
5. In the GitHub Release notes, include source-checkout install instructions, compatibility notes, and rollback instructions.

Baseline install and pinning instructions:

```bash
git clone https://github.com/jcvalerio/moneywiz-mcp-server.git
cd moneywiz-mcp-server
git checkout v1.0.0
uv sync --all-extras
uv run python setup_env.py
```

Baseline rollback instructions:

```bash
git fetch --tags
git checkout v1.0.0
uv sync --all-extras
```

## Release Notes Template

````markdown
# MoneyWiz MCP Server vX.Y.Z

## Highlights

- ...

## Compatibility

- Breaking changes: none / listed below.
- MCP tool schema changes: none / listed below.
- Configuration changes: none / listed below.
- Financial calculation changes: none / listed below.

## Install

### Source checkout

```bash
git clone https://github.com/jcvalerio/moneywiz-mcp-server.git
cd moneywiz-mcp-server
git checkout vX.Y.Z
uv sync --all-extras
uv run python setup_env.py
```

### Claude Desktop

Use the pinned checkout path in `cwd` and the `.venv/bin/python` inside that checkout as `command`.

### Binary

TBD once binary artifacts are available.

## Upgrade Notes

- Review compatibility notes before upgrading.
- Upgrade intentionally with:

```bash
git fetch --tags
git checkout vX.Y.Z
uv sync --all-extras
```

## Rollback

```bash
git fetch --tags
git checkout vPREVIOUS_VERSION
uv sync --all-extras
```
````

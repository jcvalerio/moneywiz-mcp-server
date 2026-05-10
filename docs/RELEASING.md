# Releasing MoneyWiz MCP Server

This document defines the release process for maintainers.

## Goals

- Preserve a stable baseline for existing users.
- Make upgrades intentional and documented.
- Provide release artifacts that reduce local setup complexity.
- Clearly communicate compatibility or breaking changes.

## Versioning Policy

Use semantic versioning:

- **Patch** (`1.0.1`): bug fixes, documentation corrections, non-breaking maintenance.
- **Minor** (`1.1.0`): backwards-compatible tools, optional arguments, new install methods, new analytics.
- **Major** (`2.0.0`): breaking MCP tool schemas, required argument changes, renamed tools, removed response fields, or configuration changes that require user action.

Treat the following as compatibility-sensitive:

- Tool names.
- Tool argument names/types/defaults.
- Required vs optional arguments.
- Response field names/types.
- Financial calculation behavior.
- Database path/configuration behavior.
- Claude Desktop configuration examples.

## Release Checklist

### 1. Prepare

- [ ] Confirm CI is green on `main`.
- [ ] Run local checks:
  - [ ] `uv run ruff check . --output-format=github`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy src/ --install-types --non-interactive --no-strict-optional`
  - [ ] `uv run pytest tests/`
- [ ] Confirm README install instructions still work.
- [ ] Confirm Claude Desktop config examples are accurate.

### 2. Version and changelog

- [ ] Choose the next version.
- [ ] Update package version in `pyproject.toml` if needed.
- [ ] Update `CHANGELOG.md`:
  - [ ] move relevant items from `Unreleased` into the new version section,
  - [ ] include compatibility notes,
  - [ ] include migration or rollback notes if needed.

### 3. Build artifacts

- [ ] Run `uv build`.
- [ ] Verify package artifacts are created under `dist/`.
- [ ] If binary release is configured, build the macOS binary.
- [ ] Smoke test release artifacts.

### 4. Tag and publish

- [ ] Commit release metadata changes.
- [ ] Create annotated tag:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

- [ ] Create GitHub Release from the tag.
- [ ] Upload package/binary artifacts.
- [ ] Include install, upgrade, and rollback instructions in release notes.

### 5. After release

- [ ] Verify release artifacts are downloadable.
- [ ] Verify documented install command works.
- [ ] Update marketplace listings if applicable.
- [ ] Create follow-up issues for any release problems.

## Baseline Release Guidance

The first release should preserve existing source-checkout usage so current users have a stable version to pin before the roadmap introduces packaging and feature changes.

Recommended baseline actions:

1. Tag the current stable behavior as `v1.0.0` if maintainers agree the current package version and README claims are accurate.
2. Document pinning:

```bash
git checkout v1.0.0
uv sync --all-extras
uv run python setup_env.py
```

3. Document rollback:

```bash
git fetch --tags
git checkout v1.0.0
uv sync --all-extras
```

## Release Notes Template

```markdown
# MoneyWiz MCP Server vX.Y.Z

## Highlights

- ...

## Compatibility

- Breaking changes: none / listed below.
- MCP tool schema changes: none / listed below.
- Configuration changes: none / listed below.

## Install

### Source checkout

```bash
git checkout vX.Y.Z
uv sync --all-extras
```

### Binary

TBD once binary artifacts are available.

## Upgrade Notes

- ...

## Rollback

```bash
git fetch --tags
git checkout vPREVIOUS_VERSION
uv sync --all-extras
```
```

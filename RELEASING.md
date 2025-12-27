# Release Process

Guide for creating releases of yt-dlp REST API.

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking API changes
- **MINOR** (0.2.0): New features, backward compatible
- **PATCH** (0.1.4): Bug fixes, backward compatible

## Pre-Release Checklist

- [ ] All PRs for this release merged to `develop`
- [ ] All tests passing (`make check`)
- [ ] CHANGELOG.md updated with new version entry
- [ ] No open issues/PRs in milestone (if applicable)

## Release Steps

### 1. Update CHANGELOG.md

Add entry in `develop` branch following [Keep a Changelog](https://keepachangelog.com) format:

```markdown
## [X.Y.Z] - YYYY-MM-DD

Brief description of the release.

### Added
- New feature

### Changed
- Modified behavior

### Fixed
- Bug fix (#issue-number)

### Security
- Security improvement
```

Update comparison links at bottom of file.

### 2. Create Release PR

```bash
# From develop branch
gh pr create --base main --head develop \
  --title "vX.Y.Z - Short Description" \
  --milestone "vX.Y.Z"  # if milestone exists
```

**PR body format:**

```markdown
## Short Description

1-2 sentence summary of the release.

### Added/Changed/Fixed/Security
- Item 1
- Item 2

---

**Full Changelog**: https://github.com/fvadicamo/yt-dlp-api/compare/vPREV...vX.Y.Z
```

### 3. Merge and Create Release

After PR approval and CI passes:

```bash
# Merge PR
gh pr merge <PR_NUMBER> --merge

# Create release with tag
gh release create vX.Y.Z \
  --title "vX.Y.Z - Short Description" \
  --notes-file <release-notes.md> \
  --target main
```

### 4. Close Milestone (if applicable)

```bash
gh api -X PATCH repos/fvadicamo/yt-dlp-api/milestones/<ID> -f state=closed
```

## Release Notes Format

- Start with `## Short Description` (h2, not h1)
- Use Keep a Changelog categories: Added, Changed, Fixed, Security
- End with `**Full Changelog**: <compare-link>`
- Do NOT include:
  - "Milestone: vX.Y.Z" (redundant)
  - Bot signatures or generation notices

## Tag Message Format

Git tag messages should follow this format:

```
vX.Y.Z - Short Description

Brief summary sentence.

Changed:
- Item 1
- Item 2

Fixed:
- Bug fix (#issue)
```

Use Keep a Changelog categories: Added, Changed, Fixed, Security, Removed, Deprecated.

**Example** (v0.1.5):
```
v0.1.5 - Dependency Updates & Maintenance

Dependency updates and maintenance release.

Changed:
- GitHub Actions updated (setup-python v6, github-script v8)
- Python dependencies updated (prometheus-client, cachetools, etc.)

Fixed:
- Flaky test test_request_increments_counter (#43, #44)
```

## Hotfix Process

For urgent fixes to production:

1. Create branch from `main`: `git checkout -b hotfix/description main`
2. Fix, test, commit
3. Create PR to `main` directly
4. After merge to main:
   - Create release/tag
   - Cherry-pick or merge `main` back to `develop`

## Commit Message Types

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Code style (formatting) |
| `refactor` | Code change without feature/fix |
| `perf` | Performance improvement |
| `test` | Adding/updating tests |
| `build` | Build system, dependencies |
| `ci` | CI/CD configuration |
| `chore` | Other maintenance |

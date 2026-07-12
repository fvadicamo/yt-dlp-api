# Contributing to yt-dlp REST API

Thank you for your interest in contributing!

## Prerequisites

- Python 3.11 or higher
- ffmpeg and Node.js 20+ if you want to exercise real downloads locally
  (the test suite mocks yt-dlp and needs neither)

### Virtual environment (required)

Never use the system/global Python for development. Before running any
Python or pip command:

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
which python               # must show venv/bin/python
```

## Development setup

```bash
git clone https://github.com/fvadicamo/yt-dlp-api.git
cd yt-dlp-api
python3 -m venv venv && source venv/bin/activate

make setup     # installs deps + pre-commit and pre-push hooks
make check     # verify everything is green
```

`make setup` installs the git hooks: formatting/lint/type/security checks
run on every commit, and the full test suite with the coverage gate runs
on push. The secret scan (gitleaks) also runs in CI; the privacy-denylist
hook is a maintainer-local no-op for contributors.

## Reporting issues

- **Bugs**: use the Bug Report issue template (Python version, error
  message, steps to reproduce)
- **Feature requests**: use the Feature Request template and describe the
  use case
- **Security issues**: see [SECURITY.md](SECURITY.md), do NOT open public
  issues

## Git workflow

Never commit directly to `main` or `develop`: all changes go through Pull
Requests to `develop`.

```bash
# 1. Start from develop
git checkout develop && git pull origin develop

# 2. Create a feature branch with tracking
git checkout -b feature/<task-name>
git push -u origin feature/<task-name>

# 3. Work, commit, push
git add <files>
git commit -m "type: description"
git push

# 4. Open a PR to develop; after the merge:
git checkout develop && git pull origin develop
git branch -d feature/<task-name>
```

Branch naming: `feature/<kebab-case>` (also `fix/`, `docs/`, `build/`,
`security/` prefixes are in use). No force pushes, no history rewriting on
pushed commits.

## Commit message format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]
```

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
| `security` | Vulnerability fixes or hardening |

Examples:

```
feat: add cookie validation service
fix: handle null values in video metadata
test: add unit tests for provider manager
```

## Code style

See [.gemini/styleguide.md](.gemini/styleguide.md) for the complete style
guide. Key rules:

- Python 3.11+ features allowed
- Black formatter, 100 char line length
- Type hints required for all functions
- Google-style docstrings for public APIs
- Import order stdlib / third-party / local (enforced by isort)

```bash
make format      # Black + isort
make lint        # Flake8
make type-check  # Mypy
make security    # Bandit
make check       # everything, including tests
```

## Testing requirements

- Coverage gate: **90% minimum**, enforced by pyproject, the pre-push hook
  and CI
- All tests must pass before a PR can merge (CI required checks: Lint,
  Tests, Secret Scan, Docker Smoke)
- Tests mock yt-dlp: no network or cookies needed

```bash
make test        # run the suite
make test-cov    # with coverage report (htmlcov/)
pytest tests/unit/test_youtube_provider.py -v   # a single file
```

## Documentation guidelines

Create documentation files only for content people will reference
repeatedly: setup guides, architecture decisions (`.s2s/decisions/`), API
contracts, configuration references. Do not create files for one-time
fixes, CI troubleshooting or temporary workarounds: commit messages are
documentation too, explain the "why" there. Prefer extending existing
files (README, this file) over adding new ones, and keep what exists
current: outdated docs are worse than none.

## Pull request process

1. Fork (or branch) and create a feature branch from `develop`
2. Make your changes
3. Ensure everything passes: `make check`
4. Commit with the conventional format and push
5. Open a Pull Request to `develop`

PR checklist:

- [ ] All tests passing, coverage >= 90%
- [ ] `make check` green (format, lint, types, security)
- [ ] Conventional commit messages
- [ ] Documentation updated when behavior changes

## Related documentation

- [README.md](README.md) - project overview and quick start
- [CONFIGURATION.md](CONFIGURATION.md) - configuration reference
- [DEPLOYMENT.md](DEPLOYMENT.md) - Docker and Kubernetes guide
- [RELEASING.md](RELEASING.md) - release process
- [SECURITY.md](SECURITY.md) - security policy
- [CHANGELOG.md](CHANGELOG.md) - version history
- [.gemini/styleguide.md](.gemini/styleguide.md) - complete code style guide

## First-time contributors

Look for issues labeled `good first issue`.

## Questions?

Open an issue with the "question" label.

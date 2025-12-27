# Contributing to yt-dlp REST API

Thank you for your interest in contributing!

## Prerequisites

### Python Version
- Python 3.11 or higher is required

### Virtual Environment (Required)

**NEVER use system/global Python for development.**

Before running any Python or pip command:

```bash
# Create virtual environment
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Verify activation
which python  # Should show venv/bin/python
```

## Reporting Issues

### Bug Reports
- Use the Bug Report issue template
- Include: Python version, error message, steps to reproduce

### Feature Requests
- Open a Discussion first, not an Issue
- Describe your use case

### Security Issues
- See [SECURITY.md](SECURITY.md) - do NOT open public issues

## Development Setup

```bash
# Clone the repository
git clone https://github.com/fvadicamo/yt-dlp-api.git
cd yt-dlp-api

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Verify setup
make check
```

## Git Workflow

### Protected Branches

**NEVER commit directly to `main` or `develop` branches.**

All changes require Pull Requests.

### Feature Branch Process

```bash
# 1. Start from develop
git checkout develop
git pull origin develop

# 2. Create feature branch with tracking
git checkout -b feature/<task-name>
git push -u origin feature/<task-name>

# 3. Work and commit
git add <files>
git commit -m "type: description"
git push

# 4. Open PR to develop, then after merge:
git checkout develop
git pull origin develop
git branch -d feature/<task-name>
```

### Branch Naming
- Format: `feature/<task-name-kebab-case>`
- Example: `feature/add-retry-logic`

### Forbidden Actions
- Committing directly to `develop` or `main`
- Force pushing (`git push --force`)
- Rewriting history on pushed commits

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]
```

### Types

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

### Examples

```
feat: add cookie validation service
fix: handle null values in video metadata
test: add unit tests for provider manager
docs: update README with setup instructions
```

## Code Style

See [.gemini/styleguide.md](.gemini/styleguide.md) for the complete style guide.

### Key Rules
- Python 3.11+ features allowed
- Black formatter (100 char line length)
- Type hints required for all functions
- Google-style docstrings for public APIs
- Import order: stdlib, third-party, local (enforced by isort)

### Quality Commands

```bash
make format     # Black + isort
make lint       # Flake8
make type-check # Mypy
make check      # All checks
```

## Pre-commit Hooks

Pre-commit hooks run automatically on each commit. To set up:

```bash
pre-commit install
pre-commit run --all-files  # Verify setup
```

If a hook fails, fix the issue, stage changes again, and retry the commit.

## Testing Requirements

- Minimum 80% code coverage
- All tests must pass before PR merge

```bash
make test       # Run all tests
make test-cov   # Run with coverage report
```

## Documentation Guidelines

### When to Create Documentation

Only create documentation files for:
- Setup guides that users will repeatedly reference
- Architecture decisions affecting long-term design
- API contracts for external consumers
- Configuration references for complex systems

### When NOT to Create Documentation

- One-time fixes (use commit messages)
- Test results or CI troubleshooting
- Temporary workarounds
- Implementation details that will change

### Best Practices
- Prefer adding to existing files (README, CONTRIBUTING) over new files
- Keep documentation current - outdated docs are worse than none
- Commit messages are documentation: explain the "why"

## Pull Request Process

1. Fork the repository
2. Create a feature branch from `develop`
3. Make your changes
4. Ensure all checks pass: `make check`
5. Commit with conventional format
6. Push and create a Pull Request to `develop`

### PR Checklist
- [ ] All tests passing
- [ ] `make check` passes (format, lint, type, security)
- [ ] Conventional commit messages used
- [ ] Documentation updated if needed

## Related Documentation

- [README.md](README.md) - Project overview and quick start
- [CONFIGURATION.md](CONFIGURATION.md) - Environment variables reference
- [DEPLOYMENT.md](DEPLOYMENT.md) - Docker and Kubernetes guide
- [RELEASING.md](RELEASING.md) - Release process guide
- [SECURITY.md](SECURITY.md) - Security policy
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [.gemini/styleguide.md](.gemini/styleguide.md) - Complete code style guide

## First-time Contributors

Look for issues labeled `good first issue` - these are designed for newcomers.

## Questions?

Open an issue with the "question" label.

# Development Setup Guide

This guide covers the complete setup for local development with pre-commit hooks, linting, formatting, and testing tools.

## Prerequisites

- Python 3.11 or higher
- Git
- Virtual environment tool (venv, virtualenv, or conda)

## Initial Setup

### 1. Clone and Setup Virtual Environment

```bash
# Clone the repository
git clone <repository-url>
cd yt-dlp-api

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows
```

### 2. Install Dependencies

```bash
# Install all development dependencies
pip install -r requirements-dev.txt

# Or install from pyproject.toml (recommended)
pip install -e ".[dev]"
```

### 3. Setup Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Optional: Install hooks for commit-msg and push stages
pre-commit install --hook-type commit-msg
pre-commit install --hook-type push

# Run hooks on all files to verify setup
pre-commit run --all-files
```

## Development Tools

All tools are configured in `pyproject.toml` for centralized configuration.

### Code Formatting

#### Black (Code Formatter)

```bash
# Format all Python files
black .

# Check without modifying
black --check .

# Format specific file
black app/core/config.py
```

Configuration: `[tool.black]` in `pyproject.toml`
- Line length: 100
- Target: Python 3.11

#### isort (Import Sorter)

```bash
# Sort imports in all files
isort .

# Check without modifying
isort --check-only .

# Sort specific file
isort app/core/config.py
```

Configuration: `[tool.isort]` in `pyproject.toml`
- Profile: black (compatible with Black)
- Line length: 100

### Linting

#### Flake8

```bash
# Lint all files
flake8 .

# Lint specific directory
flake8 app/

# Lint specific file
flake8 app/core/config.py
```

Configuration: `[tool.flake8]` in `pyproject.toml`

Plugins included:
- `flake8-bugbear`: Find likely bugs and design problems
- `flake8-comprehensions`: Better list/dict/set comprehensions
- `flake8-simplify`: Suggest code simplifications
- `flake8-docstrings`: Check docstring conventions
- `pep8-naming`: Check PEP 8 naming conventions

### Type Checking

#### mypy

```bash
# Type check all files
mypy .

# Type check specific directory
mypy app/

# Type check specific file
mypy app/core/config.py
```

Configuration: `[tool.mypy]` in `pyproject.toml`

Type stubs included:
- `types-PyYAML`
- `types-cachetools`

### Security Scanning

#### Bandit

```bash
# Scan for security issues
bandit -r app/

# Generate detailed report
bandit -r app/ -f json -o bandit-report.json
```

Configuration: `[tool.bandit]` in `pyproject.toml`

### Testing

#### pytest

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_config.py

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Generate HTML coverage report
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

Configuration: `[tool.pytest.ini_options]` in `pyproject.toml`

Coverage requirements:
- Minimum coverage: 90%
- Reports: terminal, HTML, XML

## Pre-commit Hooks

Pre-commit hooks run automatically before each commit. They include:

### On Every Commit:
1. **File checks**: trailing whitespace, EOF, YAML/JSON/TOML syntax
2. **Black**: Auto-format code
3. **isort**: Sort imports
4. **Flake8**: Lint code
5. **mypy**: Type check (excluding tests)
6. **Bandit**: Security scan (excluding tests)

### On Push:
7. **pytest**: Run full test suite with coverage

### Manual Execution

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run flake8 --all-files
pre-commit run mypy --all-files

# Run hooks for staged files only
pre-commit run

# Skip hooks for a commit (not recommended)
git commit --no-verify -m "message"

# Update hooks to latest versions
pre-commit autoupdate
```

## Workflow

### Standard Development Flow

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes to code
# ... edit files ...

# 4. Run formatters manually (optional, pre-commit will do this)
black .
isort .

# 5. Run linters to catch issues early
flake8 .
mypy .

# 6. Run tests
pytest

# 7. Stage changes
git add .

# 8. Commit (pre-commit hooks run automatically)
git commit -m "feat: add new feature"

# 9. Push (pytest runs on push)
git push origin feature/my-feature
```

### Quick Quality Check

```bash
# Run all quality checks manually
black . && isort . && flake8 . && mypy . && bandit -r app/ && pytest
```

### CI/CD Integration

The same tools run in CI/CD pipelines. Local pre-commit ensures you catch issues before pushing.

## Troubleshooting

### Pre-commit Hook Failures

If a hook fails:

1. **Read the error message** - it usually tells you what's wrong
2. **Fix the issue** manually or let the tool auto-fix (Black, isort)
3. **Stage the changes** again: `git add .`
4. **Retry the commit**: `git commit -m "message"`

### Common Issues

#### Black/isort conflicts
- Not possible - isort is configured with `profile = "black"`

#### Flake8 line length errors
- Black handles line length, Flake8 ignores E501

#### mypy errors in tests
- Tests are excluded from strict type checking

#### Bandit false positives
- Add `# nosec` comment with justification
- Or configure in `pyproject.toml`

#### pytest coverage too low
- Add tests to reach 90% coverage
- Or adjust threshold in `pyproject.toml` (not recommended)

### Skipping Hooks (Emergency Only)

```bash
# Skip pre-commit hooks (not recommended)
git commit --no-verify -m "emergency fix"

# Skip specific hook
SKIP=flake8 git commit -m "message"

# Skip multiple hooks
SKIP=flake8,mypy git commit -m "message"
```

## IDE Integration

### VS Code

Install extensions:
- Python (Microsoft)
- Pylance
- Black Formatter
- isort
- Flake8
- Mypy Type Checker

Add to `.vscode/settings.json`:

```json
{
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "python.linting.banditEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### PyCharm

1. Go to Settings → Tools → Black
2. Enable "On save"
3. Go to Settings → Tools → External Tools
4. Add tools for flake8, mypy, bandit

## Configuration Files

All tool configurations are centralized in `pyproject.toml`:

- `[tool.black]` - Code formatting
- `[tool.isort]` - Import sorting
- `[tool.flake8]` - Linting
- `[tool.mypy]` - Type checking
- `[tool.bandit]` - Security scanning
- `[tool.pytest.ini_options]` - Testing
- `[tool.coverage.*]` - Coverage reporting

Pre-commit orchestration: `.pre-commit-config.yaml`

## Best Practices

1. **Always use virtual environment** - Never install to system Python
2. **Run pre-commit before pushing** - Catch issues early
3. **Keep coverage above 90%** - Write tests for new code
4. **Fix type errors** - Don't use `# type: ignore` without good reason
5. **Address security warnings** - Review Bandit findings
6. **Commit frequently** - Small, focused commits
7. **Update dependencies** - Run `pre-commit autoupdate` regularly

## Additional Resources

- [Black Documentation](https://black.readthedocs.io/)
- [isort Documentation](https://pycqa.github.io/isort/)
- [Flake8 Documentation](https://flake8.pycqa.org/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [pytest Documentation](https://docs.pytest.org/)
- [pre-commit Documentation](https://pre-commit.com/)

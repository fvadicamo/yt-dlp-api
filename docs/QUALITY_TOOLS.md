# Code Quality Tools Overview

## Centralized Configuration

All tools are configured in `pyproject.toml` for single-source configuration.

## Tools Included

### Formatting
- **Black** (24.1.1) - Opinionated code formatter
- **isort** (5.13.2) - Import sorter (Black-compatible profile)

### Linting
- **Flake8** (7.0.0) with plugins:
  - flake8-bugbear - Find bugs and design issues
  - flake8-comprehensions - Better comprehensions
  - flake8-simplify - Code simplifications
  - flake8-docstrings - Docstring checks
  - pep8-naming - Naming conventions

### Type Checking
- **mypy** (1.8.0) - Static type checker
- Type stubs: types-PyYAML, types-cachetools

### Security
- **Bandit** (1.7.6) - Security vulnerability scanner

### Testing
- **pytest** (7.4.4) with coverage
- Minimum coverage: 90%

### Automation
- **pre-commit** (3.6.0) - Git hooks orchestration

## Quick Reference

```bash
# Setup
make setup

# Format code
make format

# Run all checks
make check

# Run tests
make test-cov
```

See [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md) for complete documentation.

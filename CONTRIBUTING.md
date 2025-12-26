# Contributing to yt-dlp REST API

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/fvadicamo/yt-dlp-api.git
cd yt-dlp-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run tests
make test

# Run all checks
make check
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch from `develop`: `git checkout -b feature/your-feature`
3. Make your changes
4. Ensure tests pass: `make check`
5. Commit with conventional format: `feat: add new feature`
6. Push and create a Pull Request to `develop`

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`

## Code Style

- Python 3.11+
- Black formatter (100 char line length)
- Type hints required
- Google-style docstrings
- 80%+ test coverage

## Related Documentation

- [CHANGELOG.md](CHANGELOG.md) - Version history and changes
- [RELEASING.md](RELEASING.md) - Release process guide
- [SECURITY.md](SECURITY.md) - Security policy and reporting

## Questions?

Open an issue with the "question" label.

# AGENTS.md - AI Code Review Guidelines

> Instructions for AI coding agents (Codex, Cursor, Gemini CLI, etc.)

## Project Context

**yt-dlp REST API** - A FastAPI wrapper around yt-dlp for video downloading via HTTP.

- **Language**: Python 3.11+
- **Framework**: FastAPI with asyncio
- **Core**: yt-dlp subprocess management
- **Testing**: pytest with pytest-asyncio

## Review Focus

### Security (CRITICAL)

1. **Command injection**: No `shell=True` in subprocess calls
2. **Path traversal**: Validate all user-provided paths
3. **Secrets exposure**: Redact API keys, passwords in logs
4. **Cookie security**: Proper file permissions, no path leaks
5. **Denial of Service (DoS)**: Check for resource exhaustion (e.g., large file sizes, long-running requests). See `StorageManager` for existing controls.
6. **Server-Side Request Forgery (SSRF)**: Ensure outgoing requests are to whitelisted domains. See `URLValidator` for existing controls.

### Code Quality

- **Async patterns**: Proper `await` usage, no blocking I/O in async functions
- **Type hints**: Complete annotations on all public functions
- **Error handling**: Structured exceptions, proper logging
- **Test coverage**: Minimum 85%, critical paths 95%
- **Complexity**: Adhere to complexity limits (McCabe complexity < 10) to keep functions maintainable

## Code Style

- **Formatter**: Black with 100 char line length
- **Imports**: isort with Black profile
- **Linting**: Flake8
- **Type checking**: MyPy strict mode
- **Docstrings**: Google-style for public APIs

## Commit Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
```

## PR Guidelines

- Reference task IDs from `.kiro/specs/yt-dlp-rest-api/tasks.md`
- Include test coverage for new features
- Run `make check` before submitting

## Project Structure

```
app/
├── core/           # Configuration, validation, templates
├── providers/      # Video provider implementations (YouTube, etc.)
├── services/       # Business logic (storage, rate limiting)
├── middleware/     # Auth, rate limiting middleware
└── models/         # Pydantic data models

tests/
├── unit/           # Unit tests
└── integration/    # API integration tests
```

## Key Files

### Source
- `app/providers/youtube.py` - YouTube provider with subprocess handling
- `app/core/validation.py` - URL and format validation
- `app/services/storage.py` - File storage and cleanup
- `app/middleware/auth.py` - API key authentication

### Tests
- `tests/conftest.py` - Shared fixtures
- `tests/unit/` - Unit tests
- `tests/integration/` - API integration tests

### Config
- `pyproject.toml` - Tool configuration (Black, pytest, mypy)
- `Makefile` - Development commands

## Related Documentation

- `CONTRIBUTING.md` - Complete contributor guide
- `.gemini/styleguide.md` - Detailed code style guide
- `RELEASING.md` - Release process

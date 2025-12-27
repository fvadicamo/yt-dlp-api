# Claude Code Context - yt-dlp REST API

**Repo**: https://github.com/fvadicamo/yt-dlp-api
**Latest Release**: v0.1.5 - Dependency Updates & Maintenance
**Status**: MVP Complete, public on GitHub

---

## 📚 Quick Links to Source of Truth

### Project Specifications
- **Requirements**: [.kiro/specs/yt-dlp-rest-api/requirements.md](../.kiro/specs/yt-dlp-rest-api/requirements.md)
- **Design**: [.kiro/specs/yt-dlp-rest-api/design.md](../.kiro/specs/yt-dlp-rest-api/design.md)
- **Tasks**: [.kiro/specs/yt-dlp-rest-api/tasks.md](../.kiro/specs/yt-dlp-rest-api/tasks.md)

### Workflow & Standards
- **Contributing**: [CONTRIBUTING.md](../CONTRIBUTING.md)
  Git workflow, commit format, code style, testing - **CRITICAL**: NEVER commit to main/develop
- **Code Style**: [.gemini/styleguide.md](../.gemini/styleguide.md) - Python 3.11+, PEP 8, Black 100 chars
- **Releasing**: [RELEASING.md](../RELEASING.md) - Release process, tag format, release notes

---

## 🚀 Quick Reference Commands

### Development Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Testing
```bash
make test          # Run all tests
make test-cov      # Run with coverage
pytest tests/unit/test_file.py -v  # Run specific file
```

### Quality Checks
```bash
make check         # Run all checks (format, lint, type, security, test)
make format        # Black + isort
make lint          # Flake8
make type-check    # Mypy
```

### Git Workflow
```bash
# Create feature branch (from develop)
git checkout develop && git pull origin develop
git checkout -b feature/<name>
git push -u origin feature/<name>

# Commit with conventional format
git commit -m "type: description"
# Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
```

---

## 🔍 Key Implementation Patterns

### Async Test Pattern
```python
@pytest.mark.asyncio
async def test_method_name(self, youtube_provider):
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(stdout, b""))
        mock_subprocess.return_value = mock_process
        result = await youtube_provider.method()
        assert result["key"] == "value"
```

### Parametrized Test Pattern
```python
@pytest.mark.parametrize("url,expected", [
    ("https://youtube.com/watch?v=abc", True),
    ("https://vimeo.com/123", False),
])
def test_validate_url(self, youtube_provider, url, expected):
    assert youtube_provider.validate_url(url) == expected
```

---

## 📝 Workflow Notes

### Before Opening PR
- [ ] All tests passing: `make test`
- [ ] `make check` passes (lint, type, security)
- [ ] Conventional commit messages used
- [ ] Branch tracking configured: `git branch -vv`

---

## 🔗 Important Files

### Source Files
- `app/providers/youtube.py` - YouTube provider implementation
- `app/providers/base.py` - Provider abstract interface
- `app/core/validation.py` - URL and format validation
- `app/middleware/auth.py` - API key authentication

### Test Files
- `tests/conftest.py` - Shared fixtures
- `tests/unit/` - Unit tests

### Config Files
- `pyproject.toml` - Pytest config, coverage settings
- `Makefile` - Development commands

---

## 💡 Claude-Specific Tips

### Context Refresh
When starting a new session, read:
1. This file (`.claude/CLAUDE.md`)
2. Active plan file if any: `.claude/plans/*.md`

### Design Patterns
- Provider abstraction: `VideoProvider` ABC
- Async operations: FastAPI + asyncio
- Structured logging: structlog (JSON)
- Testing: pytest + pytest-asyncio + pytest-mock

---

**Note**: This file is a quick reference. For complete source of truth, see CONTRIBUTING.md, .gemini/styleguide.md, and .kiro/specs/.

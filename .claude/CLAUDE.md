# Claude Code Context - yt-dlp REST API

**Last Updated**: 2025-12-16
**Branch**: `develop`
**Current Task**: 6 - Rate Limiting System
**Repo**: https://github.com/fvadicamo/yt-dlp-api

---

## 📊 Status Tracker (UPDATE AD OGNI TASK)

### Task Completati
- [x] Task 1: Project setup and core infrastructure
- [x] Task 2: Provider abstraction layer
- [x] Task 3: Cookie management system (100% coverage)
- [x] Task 4: YouTube provider (all subtasks including retry logic)
- [x] Task 5: Input Validation and Security (PR #5 merged)
  - 5.1: Input validation utilities (URLValidator, FormatValidator)
  - 5.2: Template processor (path traversal prevention)
  - 5.3: API key authentication
  - 5.4: Security tests (102 tests)

### MVP Critical Completed
- [x] Task 1.4: Configuration and logging tests
- [x] Task 3.4: Cookie management tests (CRITICAL)
- [x] Task 4.7: YouTube provider tests (CRITICAL)
- [x] Task 5.4: Security tests (CRITICAL) - 102 tests

### MVP Critical Pending
- [ ] Task 11.4: Startup validation tests
- [ ] Task 15.3: Basic security validation (Docker scan)

---

## 📚 Quick Links to Source of Truth

### Project Specifications
- **Requirements**: [.kiro/specs/yt-dlp-rest-api/requirements.md](../.kiro/specs/yt-dlp-rest-api/requirements.md)
  47 requisiti funzionali con pattern EARS
- **Design**: [.kiro/specs/yt-dlp-rest-api/design.md](../.kiro/specs/yt-dlp-rest-api/design.md)
  Architettura completa, data models, provider interface
- **Tasks**: [.kiro/specs/yt-dlp-rest-api/tasks.md](../.kiro/specs/yt-dlp-rest-api/tasks.md)
  15 task principali con 80+ subtask, progresso tracciato

### Workflow & Standards
- **Git Workflow**: [.kiro/steering/git-workflow.md](../.kiro/steering/git-workflow.md)
  **CRITICAL**: NEVER commit to main/develop, feature branches ALWAYS
- **Python venv**: [.kiro/steering/python-venv-requirement.md](../.kiro/steering/python-venv-requirement.md)
  Uso obbligatorio virtual environment
- **Documentation Policy**: [.kiro/steering/documentation-policy.md](../.kiro/steering/documentation-policy.md)
  Policy minimalista: evitare doc files non necessari

### Code Review & Standards
- **Style Guide**: [.gemini/styleguide.md](../.gemini/styleguide.md)
  Python 3.11+, PEP 8, Black 100 chars, type hints obbligatori
- **Gemini Config**: [.gemini/config.yaml](../.gemini/config.yaml)
  Auto-review su PR, coverage 80%+ enforcement
- **Cursor Rules**: [.cursorrules](../.cursorrules)
  Operational rules for Cursor AI: commit format, code style, Git workflow, venv requirement
---

## 🤖 Cursor Configuration

### Cursor Rules File
The project includes a `.cursorrules` file in the root directory that configures Cursor AI to automatically follow project guidelines:

- **Conventional Commits**: Enforces commit message format (`type: description`)
- **Code Style**: Python PEP 8, 100 char line length, type hints, Google-style docstrings
- **Git Workflow**: Prevents commits to main/develop, enforces feature branches
- **Virtual Environment**: Reminds to use venv before Python/pip commands
- **Documentation Policy**: Minimalist approach, avoid unnecessary doc files

**Reference**: See [.cursorrules](../.cursorrules) for complete operational rules.

For detailed guidelines, refer to:
- Git workflow: `.kiro/steering/git-workflow.md`
- Code style: `.gemini/styleguide.md`
- Python venv: `.kiro/steering/python-venv-requirement.md`
- Documentation policy: `.kiro/steering/documentation-policy.md`

---

## 🚀 Quick Reference Commands

### Development Setup
```bash
# Virtual environment (ALWAYS required)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Testing
```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/unit/test_youtube_provider.py -v

# Run with coverage for specific module
pytest tests/unit/test_youtube_provider.py \
  --cov=app/providers/youtube \
  --cov-report=term-missing

# Open HTML coverage report
open htmlcov/index.html
```

### Quality Checks
```bash
# Run all checks (format, lint, type, security, test)
make check

# Individual checks
make format         # Black + isort
make lint           # Flake8
make type-check     # Mypy
make security       # Bandit
```

### Git Workflow
```bash
# BEFORE starting work - verify branch
git branch --show-current
git branch -vv  # Check tracking

# Create new feature branch (from develop)
git checkout develop
git pull origin develop
git checkout -b feature/<task-name>
git push -u origin feature/<task-name>  # CRITICAL: Set tracking

# Commit with conventional format
git add <files>
git commit -m "type: description"
# Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore

# Push (tracking already set)
git push
```

### After PR Merge (manual by user)
```bash
git checkout develop
git pull origin develop
git branch -d feature/<task-name>
git push origin --delete feature/<task-name>
```

---

## ✅ Resolved Issues

### Issue #1: Retry Logic (Task 4.6) - RESOLVED
**Status**: ~~NOT IMPLEMENTED~~ **FIXED in Task 4.8** (2025-12-06)

**Resolution**:
- Added `_is_retriable_error()` method to classify errors
- Added `_execute_with_retry()` method with exponential backoff [2, 4, 8]s
- Integrated retry in `get_info()` (10s timeout per attempt)
- Integrated retry in `download()` (no timeout)
- Added 13 new retry tests in `TestRetryLogic` class
- Requirement 18 now fully satisfied

---

## 📊 Project Status

**Coverage**: 92.65% (target: 85%, goal: 90%) ✅
**Tests Passing**: 481 tests ✅
**Branch**: `develop`

### Remaining Tasks for MVP

**Core Implementation (6-13):**
- [ ] Task 6: Rate Limiting System ← CURRENT
- [ ] Task 7: Storage and File Management
- [ ] Task 8: Job Management System
- [ ] Task 9: API Endpoints Implementation
- [ ] Task 10: Error Handling and Monitoring
- [ ] Task 11: Startup Validation
- [ ] Task 12: FastAPI Application Assembly
- [ ] Task 13: Docker Containerization

**Documentation (14):**
- [ ] 14.1: README.md
- [ ] 14.2: DEPLOYMENT.md

**Final Validation (15):**
- [ ] 15.3: Basic security validation (Docker scan)

---

## 🔍 Key Implementation Patterns

### Async Test Pattern (from Task 3.4)
```python
@pytest.mark.asyncio
async def test_method_name(self, youtube_provider):
    """Test description."""
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        stdout = json.dumps(sample_data).encode()
        mock_process.communicate = AsyncMock(return_value=(stdout, b""))
        mock_subprocess.return_value = mock_process

        result = await youtube_provider.method()

        assert result["expected_key"] == "expected_value"
```

### Error Test Pattern
```python
@pytest.mark.asyncio
async def test_error_scenario(self, youtube_provider):
    """Test error handling."""
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"ERROR: Specific error message")
        )
        mock_subprocess.return_value = mock_process

        with pytest.raises(SpecificError, match="error message"):
            await youtube_provider.method()
```

### Parametrized Test Pattern
```python
@pytest.mark.parametrize("url,expected", [
    ("https://youtube.com/watch?v=abc", True),
    ("https://vimeo.com/123", False),
])
def test_validate_url(self, youtube_provider, url, expected):
    """Test URL validation."""
    assert youtube_provider.validate_url(url) == expected
```

---

## 📝 Workflow Notes

### When to Commit
- After each major test class implementation
- After coverage improvements
- Before running `make check`
- Use conventional commit format: `test: add X tests for Y`

### Before Opening PR
- [ ] All tests passing: `pytest tests/unit/test_youtube_provider.py`
- [ ] Coverage >= 95% for youtube.py
- [ ] `make check` passes (lint, type, security)
- [ ] `tasks.md` updated (Task 4.7 marked complete)
- [ ] Branch tracking configured: `git branch -vv`
- [ ] Conventional commit messages used

### PR Template
See plan file § 4.1 for complete PR body template with:
- Test coverage summary
- Note on missing retry logic
- Checklist
- Testing commands

---

## 🔗 Important Files

### Source Files
- `app/providers/youtube.py` - YouTube provider implementation
- `app/providers/base.py` - Provider abstract interface
- `app/providers/exceptions.py` - Exception types
- `app/models/video.py` - Data models (VideoFormat, DownloadResult)
- `app/core/validation.py` - URL and format validation
- `app/core/template.py` - Template processor with security
- `app/middleware/auth.py` - API key authentication

### Test Files
- `tests/conftest.py` - Shared fixtures
- `tests/unit/test_cookie_service.py` - Cookie service tests
- `tests/unit/test_youtube_provider.py` - YouTube provider tests
- `tests/unit/test_security.py` - Security tests (102 tests)
- `tests/unit/test_validation.py` - Validation tests
- `tests/unit/test_template.py` - Template processor tests
- `tests/unit/test_auth.py` - Authentication tests

### Config Files
- `pyproject.toml` - Pytest config, coverage settings
- `requirements-dev.txt` - Test dependencies
- `Makefile` - Development commands

---

## 💡 Claude-Specific Tips

### Context Refresh
When starting a new session, read:
1. This file (`.claude/CLAUDE.md`) for overview
2. `.kiro/specs/yt-dlp-rest-api/tasks.md` for current task status
3. Plan file if active: `.claude/plans/*.md`

### Common Commands
```bash
# Check current branch and tracking
git branch -vv

# Quick test of YouTube provider
pytest tests/unit/test_youtube_provider.py -v -k "test_validate_url"

# Coverage of specific file
pytest --cov=app/providers/youtube --cov-report=term-missing

# Find test pattern examples
grep -r "@pytest.mark.asyncio" tests/unit/test_cookie_service.py
```

### Documentation Philosophy
Per `.kiro/steering/documentation-policy.md`:
- Evitare doc files non necessari
- Code comments solo dove logica non è self-evident
- Docstrings per public APIs (Google-style)
- README only for deployment/setup

---

## 📚 References

### Requirements
- **Req 17A**: Command logging con redaction (CRITICAL - security) ✅
- **Req 18**: Retry logic con exponential backoff ✅
- **Req 27**: Rate limiting (Task 6 - CURRENT)
- **Req 35**: YouTube provider implementation ✅

### Design Patterns
- Provider abstraction: `VideoProvider` ABC
- Async operations: FastAPI + asyncio
- Structured logging: structlog (JSON)
- Testing: pytest + pytest-asyncio + pytest-mock

### Tools & Versions
- Python: 3.11+
- FastAPI: Latest
- pytest: 7.4.4
- pytest-asyncio: 0.23.3
- pytest-mock: 3.12.0
- Black: 100 char line length
- Coverage target: 85% minimum, 90% goal

---

**Note**: Questo file è un quick reference per Claude Code. Per la source of truth completa, fare sempre riferimento ai file in `.kiro/specs/` e `.kiro/steering/`.

**Handoff completato**: Kiro AWS → Claude Sonnet 4.5 (2025-12-05)

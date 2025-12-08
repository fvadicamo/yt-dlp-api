# Claude Code Context - yt-dlp REST API

**Last Updated**: 2025-12-06
**Branch**: `feature/youtube-provider-implementation`
**Task**: 4.8 - Retry Logic Implementation (COMPLETED)
**Repo**: https://github.com/fvadicamo/yt-dlp-api

---

## 📊 Status Tracker (UPDATE AD OGNI TASK)

### Task Completati
- [x] Task 1: Project setup and core infrastructure
- [x] Task 2: Provider abstraction layer
- [x] Task 3: Cookie management system (100% coverage)
- [x] Task 4.1-4.5: YouTube provider core methods
- [x] Task 4.6: Retry logic structure - FIXED in Task 4.8
- [x] Task 4.7: YouTube provider tests (94% coverage, 62 tests)
- [x] Task 4.8: Retry logic implementation + tests (155 tests, 92% coverage)

### Criticità Risolte
- ~~Issue #1: Retry logic (4.6) - NOT IMPLEMENTED~~ **RESOLVED in Task 4.8**

### MVP Critical Pending
- [ ] Task 5.4: Security tests
- [ ] Task 11.4: Startup validation tests
- [ ] Task 15.3: Basic security validation

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
  Python 3.11+, PEP 8, Black 88 chars, type hints obbligatori
- **Gemini Config**: [.gemini/config.yaml](../.gemini/config.yaml)
  Auto-review su PR, coverage 80%+ enforcement

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

**Coverage**: 92.14% (target: 85%, goal: 90%) ✅
**Tests Passing**: 155 tests ✅
**Branch**: `feature/youtube-provider-implementation`

**Task 4 Status (YouTube Provider Implementation)** - ALL COMPLETE ✅:
- ✅ 4.1: Metadata extraction
- ✅ 4.2: Format listing
- ✅ 4.3: Subtitle discovery
- ✅ 4.4: Video download
- ✅ 4.5: Audio extraction
- ✅ 4.6: Retry logic structure (FIXED in 4.8)
- ✅ 4.7: Tests (94% coverage, 62 tests)
- ✅ 4.8: Retry logic implementation + tests (COMPLETED 2025-12-06)

**MVP Critical Tests**:
- ✅ 1.4: Configuration and logging tests
- ✅ 3.4: Cookie management tests (CRITICAL)
- ✅ 4.7: YouTube provider tests (CRITICAL) - COMPLETE
- ⏳ 5.4: Security tests (CRITICAL)
- ⏳ 11.4: Startup validation tests
- ⏳ 15.3: Basic security validation

---

## 🎯 Completed Task: 4.8 Retry Logic Implementation

**Files Modified**:
- `app/providers/youtube.py` - Added retry logic methods
- `tests/unit/test_youtube_provider.py` - Added TestRetryLogic class

**Implementation Details**:
- `_is_retriable_error()`: Classifies HTTP 5xx, connection, timeout errors as retriable
- `_execute_with_retry()`: Exponential backoff [2, 4, 8]s, max 3 attempts
- Integrated in `get_info()` (10s timeout) and `download()` (no timeout)

**Test Coverage**:
- 13 parametrized tests for `_is_retriable_error()`
- 10 tests for `_execute_with_retry()` behavior
- 2 integration tests verifying retry in get_info/download

**Test Classes Implemented** (Total: 12):
1. `TestURLValidation` - URL patterns, video ID extraction
2. `TestMetadataExtraction` - get_info() with all scenarios
3. `TestFormatListing` - Format parsing, categorization, sorting
4. `TestDownload` - Download with various parameters
5. `TestCommandRedaction` - Security: sensitive data redaction (REQ 17A - CRITICAL)
6. `TestErrorHandling` - All exception types
7. `TestCookieIntegration` - Cookie validation calls
8. `TestLogging` - Structured logging verification

**NOT in Scope** (retry logic missing):
- Retry logic tests (cannot test until implemented)
- Integration tests with real yt-dlp (optional, post-MVP)

**Pattern Reference**: `tests/unit/test_cookie_service.py` (457 lines, Task 3.4)

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
- `app/providers/youtube.py` - YouTube provider implementation (to test)
- `app/providers/base.py` - Provider abstract interface
- `app/providers/exceptions.py` - Exception types
- `app/models/video.py` - Data models (VideoFormat, DownloadResult)

### Test Files
- `tests/conftest.py` - Shared fixtures
- `tests/unit/test_cookie_service.py` - Pattern reference (Task 3.4)
- `tests/unit/test_youtube_provider.py` - **TO CREATE**

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
- **Req 17A**: Command logging con redaction (CRITICAL - security)
- **Req 18**: Retry logic con exponential backoff (NOT IMPLEMENTED)
- **Req 35**: YouTube provider implementation

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
- Black: 88 char line length
- Coverage target: 85% minimum, 90% goal

---

**Note**: Questo file è un quick reference per Claude Code. Per la source of truth completa, fare sempre riferimento ai file in `.kiro/specs/` e `.kiro/steering/`.

**Handoff completato**: Kiro AWS → Claude Sonnet 4.5 (2025-12-05)

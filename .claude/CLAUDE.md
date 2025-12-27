# Claude Code Context - yt-dlp REST API

## Project Guidelines

See @AGENTS.md for security, code style, commits, and project structure.

## Specifications

- @.kiro/specs/yt-dlp-rest-api/requirements.md
- @.kiro/specs/yt-dlp-rest-api/design.md

## Standards

- @CONTRIBUTING.md - Git workflow, testing, PRs
- @.gemini/styleguide.md - Complete code style
- @RELEASING.md - Release process

---

## Quick Commands

```bash
make check      # All checks (format, lint, type, security, test)
make test       # Run tests
make test-cov   # Run with coverage
make format     # Black + isort
```

```bash
# Feature branch workflow
git checkout develop && git pull origin develop
git checkout -b feature/<name>
git push -u origin feature/<name>
```

---

## Implementation Patterns

### Async Test Pattern
```python
@pytest.mark.asyncio
async def test_method(self, provider):
    with patch("asyncio.create_subprocess_exec") as mock:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(stdout, b""))
        mock.return_value = mock_process
        result = await provider.method()
        assert result["key"] == "value"
```

### Parametrized Test
```python
@pytest.mark.parametrize("input,expected", [
    ("https://youtube.com/watch?v=abc", True),
    ("https://vimeo.com/123", False),
])
def test_validate(self, input, expected):
    assert validate(input) == expected
```

---

## Workflow Notes

### Before Opening PR
- [ ] `make check` passes
- [ ] Conventional commits used
- [ ] Branch tracking: `git branch -vv`

---

## Claude-Specific Tips

### Context Refresh
1. This file (`.claude/CLAUDE.md`)
2. Active plan: `.claude/plans/*.md`

### Design Patterns
- Provider abstraction: `VideoProvider` ABC
- Async: FastAPI + asyncio
- Logging: structlog (JSON)
- Testing: pytest + pytest-asyncio + pytest-mock

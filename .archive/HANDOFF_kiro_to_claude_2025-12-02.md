# ⚠️ ARCHIVED DOCUMENT

> **Status**: ARCHIVED - Migrated to `.claude/CLAUDE.md`
> **Archive Date**: 2025-12-06
> **Reason**: Content consolidated into CLAUDE.md for single source of truth

---

# HANDOFF: Kiro → Claude

**Data**: 2025-12-02  
**Progetto**: yt-dlp REST API Backend  
**Da**: Kiro AWS  
**A**: Claude Sonnet 4.5

## Project Overview

- **Scopo**: REST API backend containerizzato per download video YouTube tramite yt-dlp con gestione cookie, rate limiting, e monitoraggio
- **Stack**: Python 3.11, FastAPI, yt-dlp, Docker, pytest, structlog, Prometheus
- **Repo**: https://github.com/fvadicamo/yt-dlp-api

## Critical Files & Locations

### Documentation & Specs (`.kiro/`)

**Path: `.kiro/specs/yt-dlp-rest-api/` - NON spostare per retrocompatibilità Kiro**

- `requirements.md` - 47 requisiti funzionali con EARS pattern e INCOSE quality rules
- `design.md` - Architettura completa, data models, API endpoints, security design
- `tasks.md` - 15 task principali con 80+ subtask, progresso tracciato

**Steering files in `.kiro/steering/`:**
- `git-workflow.md` - Workflow git obbligatorio: feature branches, PR, tracking upstream
- `python-venv-requirement.md` - Uso obbligatorio virtual environment per Python
- `documentation-policy.md` - Policy minimalista: evitare doc files non necessari

### Code Review Setup (`.gemini/`)

- `styleguide.md` - Code style rules per Python (Black, isort, flake8, mypy, bandit)
- `config.yaml` - Gemini reviewer config per GitHub Action auto-review

### CI/CD (`.github/workflows/`)

- `gemini-code-review.yml` - Auto-review con Gemini su PR (commenta ma non blocca)
- `ci.yml` - CI pipeline: lint, type-check, test, coverage (85% required)

## Current Development State

### Git Status

```
Current branch: feature/youtube-provider-implementation
Status: Clean working tree, up to date with origin
```

**All branches:**
```
* feature/youtube-provider-implementation (current)
  develop (main development branch)
  main (production)
  feature/cookie-management-system (merged)
  feature/project-setup-and-core-infrastructure (merged)
```

**Recent commits:**
```
172e4ee docs(tasks): mark retry logic implementation as complete
ec01b88 feat: implement YouTube provider core methods
6bdfe20 Merge pull request #3 from fvadicamo/feature/cookie-management-system
f9a46ae fix: configure mypy to handle fastapi import across environments
d2d014a fix: resolve coverage and linting issues
```

### Active Task

- **ID/Nome**: Task 4 - YouTube Provider Implementation
- **Branch**: `feature/youtube-provider-implementation`
- **Status**: 6/7 subtask completati (4.1-4.6 done, 4.7 CRITICAL tests pending)
- **Next Step**: Implementare task 4.7 (YouTube provider tests - CRITICAL) prima di aprire PR

### Last Completed

- **Task**: Task 3 - Cookie Management System (merged in develop)
- **Commit**: `6bdfe20` - Merge PR #3 con 44 test, 90% coverage cookie service
- **Features**: CookieService, TTL cache, hot-reload endpoint, admin API

## Development Workflow in Use

### Branching

- **Pattern**: `feature/<task-name-kebab-case>` da `develop`
- **Tracking**: SEMPRE `git push -u origin <branch>` al primo push
- **Verifica**: `git branch -vv` per confermare tracking
- **Protected**: `main` e `develop` - SOLO via PR, MAI commit diretti

### PR Process

1. Push branch → apri PR MANUALMENTE su GitHub
2. Gemini auto-review (GitHub Action) commenta codice
3. Fix su branch → push (auto-update PR)
4. Merge MANUALE dopo approval (merge commit, NO squash/rebase)
5. Delete branch dopo merge

### Key Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run checks
make check          # All: format, lint, type, security, test
make test           # Tests only
make test-cov       # Tests with coverage report

# Development
make format         # Black + isort
make lint           # Flake8
make type-check     # Mypy
```

## For Claude: Next Actions

### Immediate Tasks

1. **Leggi contesto completo**:
   - `.kiro/specs/yt-dlp-rest-api/requirements.md` (requisiti)
   - `.kiro/specs/yt-dlp-rest-api/design.md` (architettura)
   - `.kiro/specs/yt-dlp-rest-api/tasks.md` (progresso)

2. **Leggi code standards**:
   - `.gemini/styleguide.md` (regole obbligatorie)
   - `.kiro/steering/git-workflow.md` (workflow git)

3. **Rivedi stato progetto**:
   - `git log --oneline -20` per storia recente
   - `tasks.md` per vedere task completati e pending

4. **Completa task corrente**:
   - Implementa task 4.7 (YouTube provider tests - CRITICAL)
   - Esegui `make check` per validare
   - Commit e push su `feature/youtube-provider-implementation`
   - Apri PR verso `develop`

### Permissions

✅ **Puoi fare autonomamente:**
- Continuare sviluppo task 4.7 (tests)
- Creare branch per task 5+ (seguendo workflow)
- Modificare codice (rispettando styleguide)
- Aggiornare `tasks.md` con progresso
- Commit e push su feature branches
- Eseguire `make check` e fix errori

❌ **Richiedi conferma per:**
- Merge PR (utente fa merge manuale)
- Modifiche a file `.kiro/specs/` (design/requirements)
- Breaking changes architetturali
- Modifiche GitHub workflows
- Modifiche steering rules
- Abbassare coverage requirement (attualmente 85%, target 90%)

## Project Structure

```
yt-dlp-api/
├── .kiro/
│   ├── specs/yt-dlp-rest-api/    # Requirements, design, tasks
│   └── steering/                  # Git workflow, Python venv, doc policy
├── .gemini/                       # Code review config
├── .github/workflows/             # CI/CD pipelines
├── app/
│   ├── api/                       # FastAPI endpoints (admin.py)
│   ├── core/                      # Config, logging
│   ├── models/                    # Data models (video.py)
│   ├── providers/                 # Provider abstraction (youtube.py)
│   ├── services/                  # Business logic (cookie_service.py)
│   └── utils/                     # Utilities
├── tests/
│   ├── unit/                      # Unit tests (70 tests passing)
│   └── integration/               # Integration tests (empty)
├── Makefile                       # Development commands
├── pyproject.toml                 # Python config, test settings
└── requirements*.txt              # Dependencies
```

## Key Implementation Notes

### Completed Features (Tasks 1-3)

1. **Project Setup** (Task 1): Config service, structured logging, pytest setup
2. **Provider Abstraction** (Task 2): VideoProvider interface, ProviderManager, YouTube skeleton
3. **Cookie Management** (Task 3): CookieService with TTL cache, hot-reload, admin endpoints

### Current Work (Task 4)

**YouTube Provider Implementation** - 6/7 done:
- ✅ 4.1: Metadata extraction (get_info with 10s timeout)
- ✅ 4.2: Format listing (sorted by quality)
- ✅ 4.3: Subtitle discovery
- ✅ 4.4: Video download (with logging & redaction)
- ✅ 4.5: Audio extraction
- ✅ 4.6: Retry logic structure
- ⏳ 4.7: **Tests (CRITICAL)** - DA FARE

### Testing Requirements

- **Coverage**: 85% minimum (target 90% dopo task 4)
- **Framework**: pytest + pytest-asyncio + pytest-mock
- **Current**: 70 tests passing, 86.19% coverage
- **Task 4.7**: Richiede test per YouTube provider (mock yt-dlp, test retry, error handling)

## Important Notes

- **Cookie files**: Netscape format, validati con YouTube test, cache 1h, hot-reload supportato
- **Logging**: Structured JSON con request_id, redaction di sensitive data (cookies, API keys)
- **Rate limiting**: Token bucket, per-API-key, burst support (da implementare task 6)
- **Error handling**: Standardized error codes, retry logic con exponential backoff
- **Security**: API key auth, input validation, container hardening (task 5 pending)

## Handoff Checklist

- [x] File HANDOFF.md creato
- [x] Git status documentato
- [x] Task corrente identificato (4.7 tests)
- [x] Prossimi step chiari
- [x] Permissions definite
- [x] Code standards referenziati
- [ ] Claude legge tutti i file `.kiro/`
- [ ] Claude implementa task 4.7
- [ ] Claude crea `CLAUDE.md` permanente (dopo familiarizzazione)

---

**Fine handoff. Buon lavoro Claude! 🚀**

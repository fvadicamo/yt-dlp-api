# yt-dlp-api Backlog

**Updated**: 2026-07-11
**Format**: Single markdown file for tracking work items

---

## ID Conventions

| Prefix | Category | Example |
|--------|----------|---------|
| FEAT | Features | FEAT-001 |
| BUG | Bug fixes | BUG-001 |
| TECH | Technical tasks | TECH-001 |
| DEBT | Technical debt | DEBT-001 |

**Status values**: `draft` | `planned` | `in_progress` | `blocked` | `completed`

---

## Planned

### FEAT-001: GHCR publishing with yt-dlp update strategy

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-11 (PR #62)

**Context**: There is no published image: users must clone and build. yt-dlp
is installed unpinned at build time and never updated by dependabot
(implements requirement 45). A reference project must be `docker run`-able.

**Acceptance Criteria**:
- [x] Release workflow: on tag, build multi-arch (amd64/arm64) and push to
      GHCR with semver + `latest` tags (docker-publish.yml, smoke-tested
      before push)
- [x] Weekly scheduled rebuild refreshing yt-dlp, published as `weekly` tag
- [x] yt-dlp pinned in requirements-ytdlp.txt (dependabot-managed; version
      already exposed in /health component checks)
- [ ] README quick start uses the published image (with TECH-004, after the
      first tagged publish)

### FEAT-002: Transcript endpoint

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-12 (PR #63)

**Context**: Consumers (automation pipelines, AI/RAG ingestion) want the
transcript of a video as text, without downloading media. yt-dlp can fetch
manual subtitles and auto-captions with `--skip-download`. No comparable OSS
API exposes this cleanly.

**Acceptance Criteria**:
- [x] `GET /api/v1/transcript?url=&lang=&source=&fmt=` returning
      JSON segments / text / SRT / raw VTT
- [x] Source selection: manual subtitles preferred, auto-captions fallback
- [x] 404 TRANSCRIPT_NOT_FOUND when no captions exist for the language
- [x] Rate-limited as metadata; VTT parser handles auto-caption rolling
      duplicates and inline tags; unit + endpoint + e2e + container smoke

### FEAT-003: Job completion webhooks

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-12 (PR #64)

**Context**: Downstream systems (workflow engines, data platforms, external
STT pipelines) need push notifications when a download job completes or
fails, instead of polling `GET /jobs/{id}`.

**Acceptance Criteria**:
- [x] Optional `webhook_url` on download requests
- [x] POST with job payload on completion/failure, retries with backoff
- [x] HMAC signature header (shared secret from config)
- [x] SSRF protection: outbound host allowlist in config, off by default
- [x] Unit coverage for service/worker/endpoint (22 tests)

### TECH-004: README and docs overhaul for reference status

**Status**: in_progress | **Created**: 2026-07-11

**Context**: README quick start requires cloning; no badges, no published
image, docs don't cover the new capabilities.

**Acceptance Criteria**:
- [ ] Badges (CI, coverage, GHCR, license), image-first quick start
- [ ] Architecture diagram, transcript/webhook examples, integration recipes
      (workflow engines, external STT) in generic form
- [ ] DEPLOYMENT/CONFIGURATION updated with new env vars and GHCR flow

### TECH-005: Release v0.2.0

**Status**: planned | **Created**: 2026-07-11

**Context**: First release with the differentiator features and CI gates;
first GHCR-published version.

**Acceptance Criteria**:
- [ ] CHANGELOG entry, version bump (single source), tag, GHCR publish green
- [ ] RELEASING.md updated with the GHCR steps

### TECH-006: Reconstruct project history in s2s format

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-12

**Context**: The project was specified in `.kiro/specs/` (47 requirements,
15 tasks, completed through v0.1.5) before adopting s2s. Reconstruct the
history (releases, key decisions) into s2s artifacts for traceability;
`.kiro/` remains as the original spec archive.

**Acceptance Criteria**:
- [x] Completed work mapped into this backlog with release references
      (MVP entry + TECH/FEAT entries with PR and release numbers)
- [x] Key architectural decisions captured in `.s2s/decisions/`:
      ADR-0001..0005 reconstructed from the MVP design, ADR-0006/0007
      for the 2026-07 production-readiness work
- [x] `.claude/CLAUDE.md` quick links point to s2s as the live tracker

### DEBT-001: Reconcile or close the docs-consolidation branch

**Status**: planned | **Created**: 2026-07-12

**Context**: Remote branch `feature/docs-consolidation` (2025-12) removes
`.kiro/steering/` and `docs/DEVELOPMENT_SETUP.md`, folding their content
into CONTRIBUTING/AGENTS/RELEASING. It predates the 2026-07 waves and now
conflicts with the refreshed docs. The consolidation *idea* is still valid.

**Acceptance Criteria**:
- [ ] Decide: rebase and land the consolidation, or close the branch as
      superseded (recommended: re-do the consolidation fresh, small PR)
- [ ] Either way, delete the stale remote branch afterwards

---

## In Progress

### TECH-003: Test robustness (weak modules, warnings, container e2e)

**Status**: in_progress | **Created**: 2026-07-11

**Context**: Suite was 785 tests / 90.5% total, with providers/manager.py at
54%, download_worker.py 72%, api/download.py 76%, api/video.py 77%
(historical task 2.4 never done) and ~340 deprecation warnings per run.

**Acceptance Criteria**:
- [x] providers/manager.py >= 90%, download_worker.py >= 85%, api modules >= 85%
      (all four now at 100%; total 94%, 837 tests)
- [x] `--cov-fail-under=90` in pyproject (aligned with pre-push hook)
- [x] Warnings eliminated: pydantic 2.13 upgrade removed the deprecation
      storm, orphaned mock coroutines closed in timeout tests (0 warnings)
- [x] Container-level e2e smoke in CI (Docker Smoke job, shipped with TECH-002)
- [ ] PR merged into develop

---

## Completed

### TECH-002: CI workflow with blocking quality gates

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-11 (PRs #57 #58, release v0.1.6)

**Context**: The only PR checks came from the AI review workflow (all
continue-on-error, dependabot excluded), so required contexts never reported
on dependabot PRs and 9 of them sat unmergeable. Security alerts folded in:
run-gemini-cli < 0.1.22 (critical RCE), black < 26.3.1 (high),
pytest < 9.0.3 (medium).

**Acceptance Criteria**:
- [x] Blocking jobs: Lint (black/isort/flake8/mypy/bandit), Tests with
      `--cov-fail-under=90`, Secret Scan (gitleaks), Docker Smoke
- [x] Docker image build + container smoke test (`scripts/docker_smoke.sh`)
- [x] Runs on PRs from dependabot too
- [x] Branch protection required contexts switched to the CI jobs (develop+main)
- [x] All 3 security alerts fixed; 9 dependabot PRs superseded and closed
- [x] Shipped to main as maintenance release v0.1.6 (alerts on default branch: 0)

### BUG-001: Unreadable cookie file crashes startup even in degraded mode

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-11

**Context**: Found by the container smoke test: `StartupValidator.check_cookies`
called `path.exists()` outside the try/except, so an unreadable cookie
file/volume raised `PermissionError` from `os.stat` and killed startup even
with `ALLOW_DEGRADED_START=true` (crash loop instead of degraded start).

**Acceptance Criteria**:
- [x] Unreadable cookie path treated as failed cookie check with the OS error
      in the message (`_check_cookie_access` helper)
- [x] Regression tests covering PermissionError in strict and degraded mode
- [x] In degraded mode the app boots with the provider disabled

### TECH-001: Repo hygiene and privacy guardrails

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-11 (PR #56)

**Context**: Version drift (app 1.0.0 vs tag v0.1.5, Dockerfile label 0.1.0),
pyproject/requirements.txt dependency divergence, placeholder URLs in
pyproject, no secret scanning, stale tracking docs.

**Acceptance Criteria**:
- [x] Versions aligned to released 0.1.5 (single source: `app/__init__.py`)
- [x] pyproject deps/URLs/author fixed, requirements.txt canonical
- [x] gitleaks + local privacy denylist hooks in pre-commit
- [x] `.gitignore` covers local-only files (`.local/`, `CLAUDE.local.md`)
- [x] `.kiro` tasks.md and `.claude/CLAUDE.md` reflect reality (15.x done)
- [x] s2s initialized with backlog migrated from `.kiro` tracking
- [x] PR merged into develop (#56, exact dependency pins added in review)

### MVP: Tasks 1-15 from the original .kiro plan (v0.1.0 - v0.1.5)

**Status**: completed | **Created**: 2025-12-05 | **Completed**: 2025-12-26

**Context**: Full MVP delivered through the `.kiro/specs/yt-dlp-rest-api/`
plan: core infrastructure, provider abstraction, cookie management, YouTube
provider with retries, validation/security, rate limiting, storage, job
system, API endpoints, error handling and metrics, startup validation, app
assembly, Docker, documentation, final integration (test mode, e2e, security
validation, resource validation). 785 tests, ~90% coverage.

**Traceability**:
- Spec: `.kiro/specs/yt-dlp-rest-api/` (requirements 1-47, tasks 1-15)
- Releases: v0.1.0 (MVP), v0.1.1 (review fixes), v0.1.2 (OSS files),
  v0.1.3 (security hardening), v0.1.5 (dependency maintenance)

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

### TECH-002: CI workflow with blocking quality gates

**Status**: planned | **Created**: 2026-07-11

**Context**: Today the only PR checks come from the AI review workflow, where
every step is `continue-on-error: true` (advisory) and dependabot PRs are
skipped entirely, so the required status checks never report on them and 9
dependabot PRs sit unmergeable. A dedicated `ci.yml` must provide real gates.

**Acceptance Criteria**:
- [ ] Blocking jobs: format (black/isort), lint (flake8), types (mypy),
      security (bandit + gitleaks), tests with `--cov-fail-under=90`
- [ ] Docker image build + container smoke test (health, auth, docs)
- [ ] Runs on PRs from dependabot too
- [ ] Branch protection required contexts switched to the new CI jobs
- [ ] Open dependabot PRs rebased/merged or closed

### TECH-003: Test robustness (weak modules, warnings, container e2e)

**Status**: planned | **Created**: 2026-07-11

**Context**: Suite is 785 tests / 90.5% total, but providers/manager.py sits
at 54%, download_worker.py at 72%, api/download.py 76%, api/video.py 77%
(historical task 2.4 never done). The run emits ~340 deprecation warnings.
Existing e2e tests run in-process with TestClient, not against the real
container.

**Acceptance Criteria**:
- [ ] providers/manager.py >= 90%, download_worker.py >= 85%, api modules >= 85%
- [ ] `--cov-fail-under=90` in pyproject (aligned with pre-push hook)
- [ ] Deprecation warnings triaged and eliminated or filtered with rationale
- [ ] Container-level e2e smoke in CI (docker compose up + external HTTP checks)

### FEAT-001: GHCR publishing with yt-dlp update strategy

**Status**: planned | **Created**: 2026-07-11

**Context**: There is no published image: users must clone and build. yt-dlp
is installed unpinned at build time and never updated by dependabot
(implements requirement 45). A reference project must be `docker run`-able.

**Acceptance Criteria**:
- [ ] Release workflow: on tag, build multi-arch (amd64/arm64) and push to
      GHCR with semver + `latest` tags
- [ ] Weekly scheduled rebuild refreshing yt-dlp, published as rolling tag
- [ ] yt-dlp version pinned and visible (build arg + exposed in /health)
- [ ] README quick start uses the published image (no clone required)

### FEAT-002: Transcript endpoint

**Status**: planned | **Created**: 2026-07-11

**Context**: Consumers (automation pipelines, AI/RAG ingestion) want the
transcript of a video as text, without downloading media. yt-dlp can fetch
manual subtitles and auto-captions with `--skip-download`. No comparable OSS
API exposes this cleanly.

**Acceptance Criteria**:
- [ ] `GET /api/v1/transcript?url=&lang=&fmt=` returning text/JSON/SRT/VTT
- [ ] Source selection: manual subtitles preferred, auto-captions fallback
- [ ] Clear 404 semantics when no transcript exists for the language
- [ ] Rate-limited as metadata category, covered by unit + e2e tests

### FEAT-003: Job completion webhooks

**Status**: planned | **Created**: 2026-07-11

**Context**: Downstream systems (workflow engines, data platforms, external
STT pipelines) need push notifications when a download job completes or
fails, instead of polling `GET /jobs/{id}`.

**Acceptance Criteria**:
- [ ] Optional `webhook_url` on download requests
- [ ] POST with job payload on completion/failure, retries with backoff
- [ ] HMAC signature header (shared secret from config)
- [ ] SSRF protection: outbound host allowlist in config, off by default
- [ ] Unit + e2e coverage

### TECH-004: README and docs overhaul for reference status

**Status**: planned | **Created**: 2026-07-11

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

**Status**: planned | **Created**: 2026-07-11

**Context**: The project was specified in `.kiro/specs/` (47 requirements,
15 tasks, completed through v0.1.5) before adopting s2s. Reconstruct the
history (releases, key decisions) into s2s artifacts for traceability;
`.kiro/` remains as the original spec archive.

**Acceptance Criteria**:
- [ ] Completed work mapped into this backlog with release references
- [ ] Key architectural decisions captured in `.s2s/decisions/` (MADR)
- [ ] `.claude/CLAUDE.md` quick links point to s2s as the live tracker

### BUG-001: Unreadable cookie file crashes startup even in degraded mode

**Status**: planned | **Created**: 2026-07-11

**Context**: Found by the container smoke test: `StartupValidator.check_cookies`
calls `path.exists()`, which raises an uncaught `PermissionError` when the
cookie file/volume is unreadable (wrong mount permissions), killing startup
even with `ALLOW_DEGRADED_START=true`. Production impact: crash loop instead
of degraded start with a clear health status.

**Acceptance Criteria**:
- [ ] Unreadable cookie path is treated as a failed cookie check (message
      includes the OS error), not an exception
- [ ] Regression test covering `PermissionError`/`OSError` on cookie access
- [ ] In degraded mode the app boots with the provider disabled

---

## In Progress

### TECH-002: CI workflow with blocking quality gates

**Status**: in_progress | **Created**: 2026-07-11

**Context**: see Planned entry above (moved here 2026-07-11). Security alerts
found on the way and folded into this work: run-gemini-cli < 0.1.22
(critical RCE), black < 26.3.1 (high), pytest < 9.0.3 (medium).

**Acceptance Criteria**: as in the Planned entry, plus:
- [ ] Open dependabot security alerts fixed (gemini-cli, black, pytest)

---

## Completed

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

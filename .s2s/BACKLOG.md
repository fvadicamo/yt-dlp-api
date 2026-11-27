# yt-dlp-api Backlog

**Updated**: 2026-08-05
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

### DEBT-004: The type gates outside CI are still narrower than the CI one

**Status**: planned | **Created**: 2026-08-05

**Context**: DEBT-003 aligned the blocking gate with `make type-check`, but the
pre-commit mypy hook keeps `exclude: ^tests/` and pins mypy 1.19.1 against
requirements-dev's 2.3.0. Measured during the DEBT-003 canary: committing three
deliberate type errors in `tests/` printed `mypy (no files to check) Skipped`,
so the local commit hook let them through and only CI caught them. Widening the
hook is not free, since it runs mypy in an isolated env whose
`additional_dependencies` would have to grow the test-only packages.

The other Lint tools have the same command asymmetry (`flake8 .` vs
`flake8 app/ tests/`, `black --check .` vs `app/ tests/`, `bandit -r app/`
with and without `-c pyproject.toml`). All four were measured on 2026-08-05:
identical results on both sides, so no active defect, only the same shape that
produced DEBT-003.

**Acceptance Criteria**:
- [ ] Decide whether the pre-commit mypy hook covers `tests/` or is documented
      as deliberately narrower than the gate
- [ ] Hook's mypy version reconciled with `requirements-dev.txt`
- [ ] Remaining Lint steps either routed through their make target or left
      duplicated on purpose, with the reason written down

### DEBT-008: the unicode traversal test does not test unicode

**Status**: planned | **Created**: 2026-08-06

**Context**: Surfaced closing DEBT-006 and deliberately left out of it, because
the fix is a possible security change rather than a test change.
`test_template.py::test_unicode_path_traversal` says it covers "various Unicode
representations of `..`", but Python resolves `\uXXXX` escapes at parse time, so
its two cases are the byte-identical string `"../etc/passwd"`. DEBT-006 made the
test able to fail; it did not make it test what its name promises. Its sibling
`test_security.py::test_unicode_normalization_attacks` is parametrized and has
the same question mark over what its inputs actually are.

**Measured on 2026-08-06**, calling `validate_template` directly:

| input | `is_valid` | NFKC of input |
|---|---|---|
| `../etc/passwd` (ascii) | **False** | `../etc/passwd` |
| `．．/etc/passwd` (U+FF0E) | **True** | `../etc/passwd` |
| `․․/etc/passwd` (U+2024) | **True** | `../etc/passwd` |
| `﹒﹒/etc/passwd` (U+FE52) | **True** | `../etc/passwd` |

`validate_template` matches `PATH_TRAVERSAL_PATTERNS` against the raw string and
never normalizes; `sanitize_filename` is the method that does NFKC.

**Why that asymmetry matters here**: those are two different code paths, and the
one an API client reaches is the raw one. `output_template` goes
`download.py:125` (the only validation) → job params → `youtube.py:532`, which
appends it to the yt-dlp argv as `-o` unchanged. `build_output_path` /
`process_template`, which do sanitize, are not on that path.

**What is NOT established, and must be measured before any fix**: that this is
exploitable. A fullwidth `．．` is not `..` to any filesystem, so an escape needs
something downstream to NFKC-normalize the path, and no evidence was found that
yt-dlp or the filesystem does. The honest statement today is that a security
check covers less than its test name claims, with unknown severity, and the
repo's own rule applies: settle it against the built image and real yt-dlp, not
by reasoning about it.

**Acceptance Criteria**:
- [ ] Exploitability settled empirically: a real `-o` with each variant against
      the built image, checking where the file actually lands
- [ ] If it escapes the output dir: `validate_template` normalizes before
      matching, with the ascii and unicode forms both rejected by test
- [ ] If it does not: the finding written down as defence-in-depth, with the
      test renamed or its inputs made genuinely non-ascii, so the name and the
      coverage agree either way
- [ ] `test_unicode_normalization_attacks` inputs audited the same way

### DEBT-007: migrate the TestClient backend to httpx2

**Status**: planned | **Created**: 2026-08-05

**Context**: Split out of DEBT-005, which pinned starlette and deliberately left
this open. starlette 1.4.0 imports `httpx2 as httpx` in `testclient.py` and
falls back to plain `httpx` with a `StarletteDeprecationWarning`, so the suite
runs with exactly one warning. Silencing it means installing `httpx2` in the dev
dependencies, and that is a migration rather than a line:

- measured on 2026-08-05, adding `httpx2==2.9.1` turns `make type-check` **red**
  with 2 `return-value` errors, because `TestClient.post` then returns
  `httpx2._models.Response` against helpers annotated `httpx.Response`. The
  DEBT-003 per-line ignores do not cover it (`Error code "return-value" not
  covered by "type: ignore[no-any-return]"`) and are reported unused at the
  same time. The original DEBT-005 entry claimed httpx2 would make those
  ignores unnecessary; it does not, it makes them insufficient.
- it pulls `httpx2` + `httpcore2` + `truststore` into the dev env purely for
  `TestClient`, while `app/services/webhook_service.py` keeps using
  `httpx==0.28.1` at runtime, so the test types would reference a different
  HTTP library from the one the application uses.

The coherent version of this change is one HTTP client, not two: move webhook
delivery to httpx2 as well, or wait until fastapi/starlette make httpx2 the
default and httpx the fallback. Neither is urgent, and the pin means the
decision is no longer forced by whatever a fresh install happens to resolve.

**Acceptance Criteria**:
- [ ] Decide whether httpx2 replaces httpx everywhere or the warning stays
      documented until upstream flips the default
- [ ] If adopted: the two helper annotations in `test_api_endpoints.py` moved to
      the httpx2 types and the DEBT-003 ignores removed, gate green
- [ ] Suite back to 0 warnings on a fresh install

### TECH-007: Drive adoption of the published image

**Status**: planned | **Created**: 2026-07-13

**Context**: The project positions itself as the reference OSS dockerized
yt-dlp REST API, but has no external users yet. Several roadmap decisions
(IDEA-001 additional providers, IDEA-003 SDKs, IDEA-004 Helm chart) are
explicitly demand-driven and stay parked until real usage shows up. Without
adoption signals the roadmap cannot be prioritized.

**Acceptance Criteria**:
- [ ] GitHub Discussions enabled with a "which provider next?" thread
- [ ] Repo topics and description tuned for discoverability
- [ ] Announcement where self-hosters look for this (awesome-selfhosted
      style lists, yt-dlp community)

### FEAT-004: External STT callback contract (from IDEA-002)

**Status**: planned | **Created**: 2026-07-13

**Context**: IDEA-002. Subtitles and auto-captions cover most videos, but some
have none. Audio extraction plus job webhooks already let an external STT
pipeline do the work; what is missing is a documented contract so the
transcript endpoint can fall back to a config-declared external service.

**Acceptance Criteria**:
- [ ] Documented `POST audio -> transcript` callback contract
- [ ] Config-declared external STT endpoint, off by default
- [ ] `/transcript` falls back to it when no captions exist
- [ ] Decide first whether a concrete consumer needs it (do not build on spec)

---

## In Progress

<!-- Move items here when work begins -->

---

## Completed

### DEBT-006: a few tests cannot fail

**Status**: completed | **Created**: 2026-08-05 | **Completed**: 2026-08-05

**Context**: Found reviewing DEBT-003, same defect class as the debt itself: a
check that cannot fail reads as a pass. Four sites, all pre-existing and all
counted in the 911:

- `test_template.py::test_unicode_path_traversal` asserts inside
  `if result.is_valid:`, and both of its cases are rejected by
  `validate_template`, so the body never runs and the test asserts nothing.
  Its sibling `test_security.py::test_unicode_normalization_attacks` has the
  same shape but 2 of its 4 cases do validate, so that one is live.
- `test_monitoring.py:464` asserts `X or response.status_code == 200` inside
  `if response.status_code == 200`, so the right operand is always true.
- `test_monitoring.py:453` has the same `or response.status_code == 200`
  escape hatch, which defeats the check on exactly the healthy path.
- `test_rate_limiter.py:652` is `status != 429 or status == 200`, which is
  merely a convoluted way to write `status != 429`. Correct, only obscure.

**The criterion was not that the tests pass, it was that they can fail**, so
each site was measured by breaking the behaviour under it and watching the
colour. Run against the same three deliberate breaks (a rejected template that
hands back `processed_path` with no `error_message`; `/metrics` returning
`200 application/json` with no metric names; `_is_excluded_path` returning
`False`):

- **before**: `1 failed, 3 passed`. The three sites the entry called dead stayed
  green while the code under them was broken, and the rate-limiter one went red,
  which is exactly the entry's own classification, now measured instead of read.
- **after**: `4 failed`. Same breaks, same code, four red tests.

**The scan for the two shapes was mechanical, and the instrument lied once.**
Shape B (the always-true `or`) is a grep: `grep -rnE "^\s*assert .*\bor\b"
tests/` returns 7 hits, of which 1 is the word "or" inside a string literal, 4
are genuine disjunctions, 1 is weak but not vacuous
(`test_metrics.py:62`, three real operands, left in place), and 1 is the same
convoluted form as the rate-limiter site: `test_template.py:151` was
`not result.startswith(".") or result == "unnamed"`, where the right operand is
implied by the left and can never rescue it. Simplified, and its sibling test
three lines above already wrote it that way.

Shape A (an assert in a branch that never runs) is not greppable, so it was
measured with coverage pointed at `tests/` itself: 27 never-executed statements
out of 5674, 7 of them asserts. **Five of those seven were false positives.**
All five sit in `test_download_worker.py` immediately after an `await` on a
cancelled task, and breaking `stop()` and `_run()` turned all four owning tests
red, so the asserts do execute and coverage simply loses the line events there.
The other two are the `if result.is_valid:` body of the test fixed above, dead
on purpose: the input is always rejected, so the live branch is the `else`, and
the `if` half stays as the contract for the sanitising alternative. The
remaining 20 never-executed lines are unused fixtures and stub methods, not
assertions.

**One thing this deliberately did not fix**: the test now can fail, but it still
does not test unicode, because Python resolves its `\uXXXX` escapes at parse
time and both cases are the same ascii string. Making the inputs genuinely
non-ascii can turn into a validator change, so it was split out → **DEBT-008**.

**Rule of thumb this produced**: coverage over test code finds candidate dead
asserts, it does not confirm them. Async lines after a cancellation read as
uncovered while running fine, so every candidate needs the same deliberate
break as the sites themselves; a scan that only reads the report would have
"fixed" five working tests.

**Acceptance Criteria**:
- [x] `test_unicode_path_traversal` asserts something on the rejected branch
      too: a rejection must carry an `error_message` and must not hand back a
      `processed_path`
- [x] The `or status == 200` escape hatches removed, so the assertions bind;
      both `/metrics` tests now assert the status explicitly first
- [x] Scan done mechanically for both shapes, with the grep and the coverage
      run recorded above; one further instance found and fixed
      (`test_template.py:151`), one near-miss left in place with the reason

### DEBT-005: starlette was unbounded, so a fresh install took whatever was newest

**Status**: completed | **Created**: 2026-08-05 | **Completed**: 2026-08-05

**Context**: `requirements.txt` pinned fastapi and httpx but not starlette,
which arrives transitively. fastapi 0.139.2 declares `starlette>=0.46.0` with
no ceiling (`importlib.metadata.requires("fastapi")`), so every fresh install
took the newest starlette in existence, in a repo that pins everything else to
the exact version. The item existed because that is the one input able to turn
CI red on a PR whose author changed nothing.

**Measured before deciding**, and two of the three findings corrected the entry
as originally written:

- the drift is faster than the ticket. The entry was written on 2026-08-05
  recording a fresh resolve of starlette **1.3.1**; a fresh resolve the same
  week returned **1.4.0**. One unbounded dependency, one minor version, nobody
  touched a line.
- the type-error delta the entry describes was **already absorbed**. Under the
  real gate (`mypy .`, which CI reaches through `make type-check` since
  DEBT-003), both a fresh env at 1.4.0 and the stale in-tree venv at 0.50.0
  report `Success: no issues found in 79 source files`. What survived was an
  asymmetry, not a failure: the two DEBT-003 ignores are needed at 1.x and dead
  at 0.50.0, and `warn_unused_ignores = false` hides the difference. The live
  delta was one warning, present on fresh installs and absent on the stale venv.
- adopting `httpx2` would **not** have fixed this. It leaves starlette floating
  (still resolves 1.4.0 with httpx2 installed), so it does not touch the failure
  mode at all, and it turns the gate red: see DEBT-007.

**Acceptance Criteria**:
- [x] Decided: pin, because it is the only one of the two options that addresses
      an unbounded input; `starlette==1.4.0` in `requirements.txt` and in
      `pyproject.toml`, which its own comment requires to stay in sync
      (`requirements-dev.txt` inherits it through `-r requirements.txt`)
- [x] A stale local venv can no longer disagree with CI about which errors exist:
      the version is now an input rather than a resolution result, and bumps
      arrive as dependabot PRs like every other dependency
- [x] The stale rationale on the two DEBT-003 ignores corrected: with one pinned
      resolution they are unconditionally needed, and the comment no longer
      claims a second resolution exists
- [ ] **Not met, split out deliberately**: the suite still emits one
      `StarletteDeprecationWarning` on a fresh install. Closing that means
      adopting httpx2, which is a migration with its own costs → DEBT-007

### DEBT-003: The CI type gate is narrower than the documented local one

**Status**: completed | **Created**: 2026-08-04 | **Completed**: 2026-08-05 (PR #110)

**Context**: The CI `Lint` job runs `mypy app/`, while `make type-check` (the
command CONTRIBUTING tells contributors to run) runs `mypy .`. The gap is not
theoretical: `make check` had been failing on a clean checkout for an unknown
number of releases while every required check stayed green, because the 19
errors were all in `tests/`. The errors themselves are fixed in v0.2.4; the
asymmetry that hid them is not.

**Measured before deciding**: `mypy app/` checked 46 files, `mypy .` checked 79,
and the 33 in the delta were all of `tests/`. Under the old gate mypy itself
reported `unused section(s): module = ['tests.*']`, so the gate read neither the
tests nor the configuration about them. The `tests.*` override was hiding 70
real errors in 8 files (43 `union-attr`, 17 `operator`, 8 `arg-type`, 2 `misc`),
and `check_untyped_defs = false` skipped the body of every fully unannotated
test. Dropping the whole override instead would have cost 514 errors, 444 of
them `no-untyped-def`.

**Acceptance Criteria**:
- [x] Scope decided: CI widened, because the documented command is the local one
      and narrowing would have left `tests/` unread by every gate
- [x] CI calls `make type-check` rather than repeating `mypy .`, so the two
      cannot drift apart again
- [x] `tests.*` overrides reviewed one code at a time: `arg-type`, `union-attr`,
      `operator` and `misc` re-enabled and their 70 sites fixed (50 narrowing
      asserts, 8 `isinstance`, 5 genuine defects including a `cleanup_scheduler`
      `interval` annotated `int` while only ever forwarding to `asyncio.sleep`,
      5 per-line ignores where the wrong type is what the test asserts);
      `check_untyped_defs` re-enabled; `disallow_untyped_defs` deliberately left
      off
- [x] Verified by watching it fail: a throwaway branch (PR #109, closed) with
      three deliberate type errors in `tests/` turned the Lint job red on
      exactly those three, with Tests green
- [x] Follow-ups recorded rather than absorbed: DEBT-004 (gates outside CI),
      DEBT-005 (starlette unpinned)

### TECH-008: Drain the dependabot queue and release v0.2.4

**Status**: completed | **Created**: 2026-08-04 | **Completed**: 2026-08-04

**Context**: Eight dependabot PRs open since 2026-07-20 with both queues at
their configured limit (pip 5/5, github-actions 3/3), so dependabot could not
propose anything new, including the next yt-dlp release. Two of the eight were
runtime dependencies baked into the published image (fastapi, structlog), which
is what made this a release rather than a sync.

**Acceptance Criteria**:
- [x] PRs #94-#101 merged into develop, both queues free, CI green on the
      combined state
- [x] The two CI-action bumps that no PR check exercises (`setup-qemu-action`,
      `login-action`, used only in `docker-publish.yml`, which never runs on
      `pull_request`) verified by dispatching that workflow on develop, where it
      publishes only the rolling `weekly` tag
- [x] `make check` restored to green: the two `-> "TestClient.post"`
      annotations corrected, the in-tree venv excluded from `mypy .` (the
      asymmetry that hid them is DEBT-003)
- [x] `pyproject.toml` dev extras realigned with `requirements-dev.txt`: they
      still pinned flake8 7.0.0 with flake8-bugbear 24.1.17, reproducing under
      `pip install -e ".[dev]"` the exact incompatibility DEBT-002 fixed
- [x] Image exercised against real YouTube before the tag

### BUG-005: /formats returns 500 on real YouTube (fractional audio bitrate)

**Status**: completed | **Created**: 2026-07-13 | **Completed**: 2026-07-13 (PR #88)

**Context**: Found by calling the deployed v0.2.2 image. yt-dlp reports `abr`
as a fractional float (129.796); the provider passed it into
`VideoFormat.audio_bitrate` (typed int), and pydantic rejected every format at
the response boundary, so `GET /api/v1/formats` answered 500 for effectively
every video. Test fixtures used `"abr": 128`, which is why the suite was blind
to it. `duration` had the same shape.

**Acceptance Criteria**:
- [x] Provider rounds yt-dlp numeric fields to the int its dataclass declares
      (audio_bitrate, filesize, duration)
- [x] Regression tests with the real float values from yt-dlp
- [x] Verified against real YouTube: 37 formats, all response models built

### BUG-006: /health reports unhealthy on a working deployment

**Status**: completed | **Created**: 2026-07-13 | **Completed**: 2026-07-13 (PR #87)

**Context**: The `youtube_connectivity` probe had a hardcoded 2s timeout, but
a real yt-dlp invocation takes ~1.7s in the published image, so `/health`
flipped to unhealthy on any jitter while every component worked.

**Acceptance Criteria**:
- [x] `timeouts.health_check` setting (`APP_TIMEOUTS_HEALTH_CHECK`), default 10s
- [x] Documented in CONFIGURATION.md, DEPLOYMENT.md, config.yaml
- [x] Test asserting the probe honours the configured value

### DEBT-002: flake8 toolchain pinned below its plugins

**Status**: completed | **Created**: 2026-07-13 | **Completed**: 2026-07-13 (PR #86)

**Context**: Dependabot PR #85 (flake8-bugbear 25.11.29) could not install:
bugbear requires flake8>=7.2.0 while requirements-dev pinned flake8==7.0.0.
The new bugbear release also surfaced B042 on `APIError`, whose `__init__`
passed only `message` to `super()`, breaking copy/pickle round-trips.

**Acceptance Criteria**:
- [x] flake8 7.3.0 + flake8-bugbear 25.11.29, lint clean
- [x] `APIError` forwards all args to `super().__init__()`, `__str__` preserved

### DEBT-001: Reconcile or close the docs-consolidation branch

**Status**: completed | **Created**: 2026-07-12 | **Completed**: 2026-07-12

**Context**: Remote branch `feature/docs-consolidation` (2025-12) removes
`.kiro/steering/` and `docs/DEVELOPMENT_SETUP.md`, folding their content
into CONTRIBUTING/AGENTS/RELEASING. It predates the 2026-07 waves and now
conflicts with the refreshed docs. The consolidation *idea* is still valid.

**Acceptance Criteria**:
- [x] Consolidation re-done fresh: CONTRIBUTING.md now hosts setup, venv
      policy, git workflow, commit conventions and documentation
      guidelines; the Kiro steering files and docs/DEVELOPMENT_SETUP.md
      are removed; .cursorrules and .claude/CLAUDE.md references updated
- [x] Stale remote branch deleted after the merge

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

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-12 (PR #65)

**Context**: README quick start requires cloning; no badges, no published
image, docs don't cover the new capabilities.

**Acceptance Criteria**:
- [x] Badges (CI, publish, release, coverage, license), image-first quick start
- [x] Architecture diagram, transcript/webhook examples, integration recipes
      (workflow engines, AI/RAG, external STT) in generic form
- [x] DEPLOYMENT/CONFIGURATION/RELEASING updated (webhooks vars, GHCR flow)

### TECH-005: Release v0.2.0

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-12 (PR #67, tag v0.2.0)

**Context**: First release with the differentiator features and CI gates;
first GHCR-published version.

**Acceptance Criteria**:
- [x] CHANGELOG entry, version bump, tag, GHCR publish green (8m04s,
      multi-arch); image verified pullable anonymously with yt-dlp
      2026.07.04 and app 0.2.0 inside
- [x] RELEASING.md updated with the GHCR steps

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

### TECH-003: Test robustness (weak modules, warnings, container e2e)

**Status**: completed | **Created**: 2026-07-11 | **Completed**: 2026-07-12 (PR #61)

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
- [x] PR merged into develop (#61)

---

### BUG-002/003/004: Real-YouTube 2026 fixes (found by the first production deploy)

**Status**: completed | **Created**: 2026-07-12 | **Completed**: 2026-07-12

**Context**: The first deployment against real YouTube (test mode masks all
three) surfaced: (BUG-002) yt-dlp rewrites the cookie jar on every run, so
the documented read-only cookies mount crashed every real invocation with
OSError 30; (BUG-003) the hardcoded `--extractor-args
youtube:player_client=web` triggered YouTube's PO-token requirement and
discarded all web-client subtitles; (BUG-004) pip installs of yt-dlp do not
bundle the EJS challenge-solver scripts, so signature/n-challenge solving
failed and /info returned only images.

**Acceptance Criteria**:
- [x] Executions run against a private writable cookie copy
      (`app/utils/cookies.py`, single interception in the provider retry
      wrapper + cookie auth test); read-only mounts work; jar rotation is
      discarded by design (hot-reload is the refresh path)
- [x] Forced web player client removed (yt-dlp maintained client selection)
- [x] `yt-dlp-ejs` pinned in requirements-ytdlp.txt
- [x] Verified against real YouTube with a read-only cookie mount:
      /info 200 with full metadata, /transcript 200 with 60 manual-sub
      segments

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

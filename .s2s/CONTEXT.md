# yt-dlp-api - Component Context

<!--
This file is maintained by Spec2Ship init command.
Import this in CLAUDE.md using @.s2s/CONTEXT.md
Run /s2s:init to populate or update this file.

MEMORY LOADING:
- This file should be imported in CLAUDE.md via @.s2s/CONTEXT.md
- Claude Code automatically loads referenced files into memory at session start

NOTE: S2S paths and how-to documentation are in README.md (not loaded in memory)
-->

## Business Domain

Developer tools / self-hosted media automation. A REST backend that turns
yt-dlp into a service consumable by automation pipelines (workflow engines,
data platforms, AI/RAG ingestion) instead of a CLI bound to a shell.

## Project Objectives

- Become the reference open-source dockerized yt-dlp REST API: pull the image,
  set an API key, and use it in production without building anything
- Offer capabilities absent from comparable OSS projects: transcript
  extraction as clean text/JSON, job completion webhooks, hardened security
  posture (auth, rate limiting, input validation), first-class observability
- Keep production-grade quality enforced by CI gates: 90%+ coverage,
  lint/type/security checks, container-level e2e smoke tests

## Project Constraints

- Public OSS repository (MIT): no references to any private deployment
  or infrastructure may enter the repo, in any form
- Python 3.11+ / FastAPI / yt-dlp invoked as subprocess (no yt-dlp Python API
  coupling); ffmpeg and Node.js 20+ required at runtime
- API key authentication and rate limiting are mandatory on all API endpoints
- Coverage gate at 90%; conventional commits; feature branches with PRs

## Component Overview

REST API for video downloads and metadata extraction using yt-dlp. Supports
YouTube (provider abstraction ready for more platforms) with cookie
authentication and hot-reload, async job queue with priority and retries,
storage management with automatic cleanup, Prometheus metrics, structured
JSON logging, and a test mode that mocks yt-dlp for development and e2e runs.
Planned differentiators: transcript endpoint (subtitles/auto-captions as
text/JSON/SRT/VTT), job completion webhooks (HMAC-signed), GHCR multi-arch
images with a weekly yt-dlp refresh.

## Scope

**Type**: Full implementation - complete feature set

**In scope**:
- Video/audio download, metadata, formats, subtitles, transcripts via REST
- Async job management, webhooks, storage lifecycle, observability
- Docker-first distribution (GHCR multi-arch, docker compose, k8s examples)
- Security hardening and CI quality gates

**Out of scope**:
- Web UI (API-first; UI projects like MeTube already cover that niche)
- Built-in ML transcription (STT stays delegated to external pipelines
  consuming audio via API/webhooks)
- Multi-tenant user management (API keys are the only identity model)
- Providers beyond YouTube in v0.2 (abstraction exists; more providers later)

## Technical Stack

- Python 3.11, FastAPI, uvicorn, pydantic v2, structlog, prometheus-client
- yt-dlp subprocess + ffmpeg + Node.js 20 (JS challenge resolution)
- pytest / pytest-asyncio, coverage >= 90%, pre-commit (black, isort, flake8,
  mypy, bandit, gitleaks)
- Docker multi-stage (python:3.11-slim), docker compose, GHCR publishing

## Component Open Questions

- GHCR namespace: recommended `ghcr.io/fvadicamo/yt-dlp-api` (matches repo,
  zero-config with GITHUB_TOKEN); alternative: Docker Hub mirror later if
  discoverability requires it
- Multi-provider roadmap: recommended to defer until after v0.2.0 and open a
  GitHub Discussion to let demand drive the first non-YouTube provider

---
*Last updated: 2026-07-11*

# Transcripts from subtitles/auto-captions; external STT via webhooks

- Status: accepted
- Date: 2026-07-12

## Context

Automation and AI/RAG consumers want video transcripts as data. Embedding
an ML transcription stack (Whisper-class) would explode image size, require
GPUs and duplicate what dedicated pipelines do better.

## Decision

`GET /api/v1/transcript` serves manual subtitles with auto-caption fallback
via yt-dlp `--skip-download` (JSON segments/text/SRT/VTT). Videos without
captions return 404. External STT pipelines integrate through the existing
audio extraction plus HMAC-signed job webhooks; a direct STT-backend
contract stays parked (IDEA-002) until real demand.

## Consequences

- The core image stays lean and GPU-free
- Caption-less videos need an external pipeline (documented recipe)
- The VTT parser must dedupe YouTube auto-caption rolling cues

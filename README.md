# YT-DLP REST API

A production-ready REST API for video downloads and metadata extraction using yt-dlp. Supports YouTube with cookie authentication, async job processing, and Prometheus metrics.

## Features

- **Video Operations**: Metadata extraction, format listing, video/audio download
- **Async Downloads**: Job queue with priority, progress tracking, retry logic
- **Authentication**: API key authentication with multi-key support
- **Rate Limiting**: Token bucket rate limiter (100 rpm metadata, 10 rpm downloads)
- **Cookie Management**: Hot-reload, validation, 7-day expiry warnings
- **Monitoring**: Prometheus metrics, structured JSON logging, health checks
- **Security**: Non-root container, input validation, path traversal prevention
- **Docker Ready**: Multi-stage build, docker-compose, resource limits

## Quick Start

### Docker (Recommended)

1. **Clone and configure:**
```bash
git clone https://github.com/fvadicamo/yt-dlp-api.git
cd yt-dlp-api

# Create required directories
mkdir -p downloads cookies logs

# Create .env file with your API key
echo 'API_KEY=["your-secure-api-key"]' > .env
echo 'ALLOW_DEGRADED_START=true' >> .env  # Optional: start without cookies
```

2. **Start the service:**
```bash
docker compose up -d
```

3. **Verify it's running:**
```bash
curl http://localhost:8000/health
```

### Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Run the application
uvicorn app.main:app --reload
```

## API Usage

### Authentication

All API endpoints (except health checks) require an API key:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/info?url=...
```

### Get Video Info

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/api/v1/info?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### List Available Formats

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/api/v1/formats?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Download Video (Async)

```bash
# Start download job
curl -X POST -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format_id": "best"}' \
  http://localhost:8000/api/v1/download

# Response: {"job_id": "abc123", "status": "pending", ...}

# Check job status
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/jobs/abc123
```

### Extract Audio Only

```bash
curl -X POST -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "extract_audio": true, "audio_format": "mp3"}' \
  http://localhost:8000/api/v1/download
```

### Health Check

```bash
# Full health check (returns 503 if unhealthy)
curl http://localhost:8000/health

# Liveness probe (always 200 if app is running)
curl http://localhost:8000/liveness

# Readiness probe (200 if ready to accept traffic)
curl http://localhost:8000/readiness
```

### Prometheus Metrics

```bash
curl http://localhost:8000/metrics
```

## Cookie Setup (Required for YouTube)

YouTube requires authentication cookies for most downloads. Export cookies from your browser:

### Chrome

1. Install [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) extension
2. Go to youtube.com and log in
3. Click the extension icon → Export → Save as `cookies/youtube.txt`

### Firefox

1. Install [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) extension
2. Go to youtube.com and log in
3. Click the extension icon → Export → Save as `cookies/youtube.txt`

### Validate Cookies

```bash
curl -X POST -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"provider": "youtube"}' \
  http://localhost:8000/api/v1/admin/validate-cookie
```

### Hot-Reload Cookies

```bash
curl -X POST -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"provider": "youtube"}' \
  http://localhost:8000/api/v1/admin/reload-cookie
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | (required) | JSON array of API keys, e.g. `["key1", "key2"]` |
| `ALLOW_DEGRADED_START` | `false` | Start without valid cookies |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics |

See [DEPLOYMENT.md](DEPLOYMENT.md#environment-variables-reference) for the complete list of 30+ configuration options.

### config.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 8000

storage:
  output_dir: "/app/downloads"
  cleanup_age: 24        # hours
  max_file_size: 524288000  # 500MB

downloads:
  max_concurrent: 5
  queue_size: 100

rate_limiting:
  metadata_rpm: 100
  download_rpm: 10
  burst_capacity: 20

logging:
  level: "INFO"
  format: "json"

providers:
  youtube:
    enabled: true
    cookie_path: "/app/cookies/youtube.txt"
    retry_attempts: 3
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with component status |
| `/liveness` | GET | Kubernetes liveness probe |
| `/readiness` | GET | Kubernetes readiness probe |
| `/metrics` | GET | Prometheus metrics |
| `/api/v1/info` | GET | Get video metadata |
| `/api/v1/formats` | GET | List available formats |
| `/api/v1/download` | POST | Start download job |
| `/api/v1/jobs/{id}` | GET | Get job status |
| `/api/v1/admin/validate-cookie` | POST | Validate provider cookies |
| `/api/v1/admin/reload-cookie` | POST | Hot-reload cookies |

Full API documentation available at `/docs` (Swagger UI) or `/redoc`.

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_URL` | 400 | URL malformed or unsupported |
| `INVALID_FORMAT` | 400 | Format ID invalid |
| `AUTH_FAILED` | 401 | API key missing or invalid |
| `VIDEO_UNAVAILABLE` | 404 | Video private/deleted/geo-blocked |
| `JOB_NOT_FOUND` | 404 | Job ID not found or expired |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit hit, check Retry-After |
| `DOWNLOAD_FAILED` | 500 | Download operation failed |
| `QUEUE_FULL` | 503 | Download queue at capacity |

## Troubleshooting

### "No provider available for URL"

- YouTube provider may be disabled (missing/invalid cookies)
- Check `/health` endpoint for component status
- Ensure cookies are exported correctly
- Try `ALLOW_DEGRADED_START=true` for testing without cookies

### "Cookie validation failed"

- Cookies may be expired (YouTube cookies last ~1 year)
- Re-export cookies from browser
- Check cookie file format (Netscape format required)
- Verify cookie file permissions

### "Rate limit exceeded"

- Wait for Retry-After seconds indicated in response
- Metadata: 100 requests/minute
- Downloads: 10 requests/minute

### Container won't start

- Ensure `API_KEY` environment variable is set
- Check logs: `docker compose logs -f`
- Verify config.yaml is mounted correctly

## Documentation

| Document | Description |
|----------|-------------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Docker and Kubernetes deployment guide |
| [CONFIGURATION.md](CONFIGURATION.md) | Complete configuration reference (30+ options) |
| [CHANGELOG.md](CHANGELOG.md) | Version history and release notes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup and contribution guidelines |
| [RELEASING.md](RELEASING.md) | Release process for maintainers |
| [SECURITY.md](SECURITY.md) | Security policy and vulnerability reporting |

## Development

```bash
# Run tests
make test

# Run all checks (format, lint, type, security, test)
make check

# Format code
make format
```

## System Requirements

- Python 3.11+
- ffmpeg (for audio extraction)
- Node.js 20+ (for yt-dlp JavaScript challenges)
- Docker (recommended for deployment)

## License

MIT

# Configuration Guide

Complete reference for configuring yt-dlp REST API.

## Configuration Precedence

Configuration values are loaded in the following order (highest priority first):

1. **Environment Variables** - `APP_*` prefix overrides everything
2. **YAML Configuration** - `config.yaml` file settings
3. **Default Values** - Built-in defaults

Example: If `config.yaml` sets `server.port: 9000` but `APP_SERVER_PORT=8080` is set, the API will use port 8080.

## Configuration File

The default configuration file is `config.yaml` in the application root. Override the path with:

```bash
# Via environment
CONFIG_PATH=/custom/path/config.yaml

# Via CLI
python -m uvicorn app.main:app --env CONFIG_PATH=/custom/config.yaml
```

## Schema Reference

### Server Configuration

Controls the HTTP server behavior.

```yaml
server:
  host: "0.0.0.0"    # Bind address
  port: 8000         # HTTP port
  workers: 4         # Uvicorn worker processes
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `host` | string | `0.0.0.0` | `APP_SERVER_HOST` | Valid IP or hostname |
| `port` | integer | `8000` | `APP_SERVER_PORT` | 1-65535 |
| `workers` | integer | `4` | `APP_SERVER_WORKERS` | >= 1 |

### Timeouts Configuration

Operation timeout limits in seconds.

```yaml
timeouts:
  metadata: 10       # Video info fetch timeout
  download: 300      # Download operation timeout (5 min)
  audio_conversion: 60  # FFmpeg conversion timeout
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `metadata` | integer | `10` | `APP_TIMEOUTS_METADATA` | >= 1 |
| `download` | integer | `300` | `APP_TIMEOUTS_DOWNLOAD` | >= 1 |
| `audio_conversion` | integer | `60` | `APP_TIMEOUTS_AUDIO_CONVERSION` | >= 1 |

### Storage Configuration

File system and cleanup settings.

```yaml
storage:
  output_dir: "/app/downloads"   # Download destination
  cookie_dir: "/app/cookies"     # Cookie files location
  cleanup_age: 24                # Hours before file deletion
  cleanup_threshold: 80          # Disk usage % to trigger cleanup
  max_file_size: 524288000       # 500MB in bytes
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `output_dir` | string | `/app/downloads` | `APP_STORAGE_OUTPUT_DIR` | Valid writable path |
| `cookie_dir` | string | `/app/cookies` | `APP_STORAGE_COOKIE_DIR` | Valid readable path |
| `cleanup_age` | integer | `24` | `APP_STORAGE_CLEANUP_AGE` | >= 1 |
| `cleanup_threshold` | integer | `80` | `APP_STORAGE_CLEANUP_THRESHOLD` | 1-100 |
| `max_file_size` | integer | `524288000` | `APP_STORAGE_MAX_FILE_SIZE` | >= 1 |

### Downloads Configuration

Job queue and concurrency settings.

```yaml
downloads:
  max_concurrent: 5    # Parallel downloads
  queue_size: 100      # Max pending jobs
  job_ttl: 24          # Hours to keep completed jobs
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `max_concurrent` | integer | `5` | `APP_DOWNLOADS_MAX_CONCURRENT` | >= 1 |
| `queue_size` | integer | `100` | `APP_DOWNLOADS_QUEUE_SIZE` | >= 1 |
| `job_ttl` | integer | `24` | `APP_DOWNLOADS_JOB_TTL` | >= 1 |

### Rate Limiting Configuration

Token bucket rate limiter settings.

```yaml
rate_limiting:
  metadata_rpm: 100    # Requests per minute for /info, /formats
  download_rpm: 10     # Requests per minute for /download
  burst_capacity: 20   # Maximum token bucket capacity
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `metadata_rpm` | integer | `100` | `APP_RATE_LIMITING_METADATA_RPM` | >= 1 |
| `download_rpm` | integer | `10` | `APP_RATE_LIMITING_DOWNLOAD_RPM` | >= 1 |
| `burst_capacity` | integer | `20` | `APP_RATE_LIMITING_BURST_CAPACITY` | >= 1 |

**How Token Bucket Works:**
- Tokens refill at `rpm/60` per second
- Each request consumes 1 token
- Burst allows temporary spikes up to `burst_capacity`
- When tokens exhausted, returns 429 with `Retry-After` header

### Templates Configuration

Output filename templates using yt-dlp syntax.

```yaml
templates:
  default_output: "%(title)s-%(id)s.%(ext)s"
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `default_output` | string | `%(title)s-%(id)s.%(ext)s` | `APP_TEMPLATES_DEFAULT_OUTPUT` | Valid yt-dlp template |

**Available Template Variables:**
- `%(title)s` - Video title
- `%(id)s` - Video ID
- `%(ext)s` - File extension
- `%(uploader)s` - Channel name
- `%(upload_date)s` - Upload date (YYYYMMDD)
- `%(duration)s` - Duration in seconds
- `%(resolution)s` - Video resolution

See [yt-dlp output template](https://github.com/yt-dlp/yt-dlp#output-template) for full list.

### Providers Configuration

Video provider settings.

```yaml
providers:
  youtube:
    enabled: true
    cookie_path: null          # Override cookie file path
    retry_attempts: 3          # Max retry attempts
    retry_backoff: [2, 4, 8]   # Backoff delays in seconds
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `youtube.enabled` | boolean | `true` | `APP_YOUTUBE_ENABLED` | - |
| `youtube.cookie_path` | string | `null` | `APP_YOUTUBE_COOKIE_PATH` | Valid file path or null |
| `youtube.retry_attempts` | integer | `3` | `APP_YOUTUBE_RETRY_ATTEMPTS` | >= 0 |
| `youtube.retry_backoff` | list[int] | `[2, 4, 8]` | `APP_YOUTUBE_RETRY_BACKOFF` | JSON array |

**Retry Behavior:**
- Retries only on transient errors (network, rate limits)
- Does not retry on permanent errors (video unavailable, invalid URL)
- Exponential backoff: waits 2s, then 4s, then 8s between attempts

### Logging Configuration

Structured logging settings.

```yaml
logging:
  level: "INFO"      # Log level
  format: "json"     # Output format
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `level` | string | `INFO` | `APP_LOGGING_LEVEL` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `format` | string | `json` | `APP_LOGGING_FORMAT` | json, text |

**Log Levels:**
- `DEBUG` - Detailed debugging (includes yt-dlp output)
- `INFO` - Normal operation (requests, job status)
- `WARNING` - Recoverable issues (cookie expiry, retry)
- `ERROR` - Failed operations
- `CRITICAL` - System failures

### Security Configuration

Authentication and CORS settings.

```yaml
security:
  api_keys: []                 # List of valid API keys
  allow_degraded_start: false  # Start without cookies
  cors_origins: ["*"]          # Allowed CORS origins
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `api_keys` | list[string] | `[]` | `APP_SECURITY_API_KEYS` | JSON array, at least 1 required |
| `allow_degraded_start` | boolean | `false` | `APP_SECURITY_ALLOW_DEGRADED_START` | - |
| `cors_origins` | list[string] | `["*"]` | `APP_SECURITY_CORS_ORIGINS` | JSON array of origins |

**Security Notes:**
- `api_keys` must be set unless `allow_degraded_start: true`
- API keys should be 32+ characters for security
- Use specific CORS origins in production instead of `*`

### Monitoring Configuration

Prometheus metrics settings.

```yaml
monitoring:
  metrics_enabled: true    # Enable /metrics endpoint
  metrics_port: 9090       # Prometheus scrape port
```

| Field | Type | Default | Env Variable | Validation |
|-------|------|---------|--------------|------------|
| `metrics_enabled` | boolean | `true` | `APP_MONITORING_METRICS_ENABLED` | - |
| `metrics_port` | integer | `9090` | `APP_MONITORING_METRICS_PORT` | 1-65535 |

## Configuration Patterns

### Light Workload (< 100 downloads/day)

```yaml
server:
  workers: 2

downloads:
  max_concurrent: 2
  queue_size: 20

rate_limiting:
  metadata_rpm: 30
  download_rpm: 5

storage:
  cleanup_age: 12
```

### Medium Workload (100-500 downloads/day)

```yaml
server:
  workers: 4

downloads:
  max_concurrent: 5
  queue_size: 100

rate_limiting:
  metadata_rpm: 100
  download_rpm: 10

storage:
  cleanup_age: 24
  cleanup_threshold: 75
```

### Heavy Workload (500+ downloads/day)

```yaml
server:
  workers: 8

downloads:
  max_concurrent: 10
  queue_size: 500

rate_limiting:
  metadata_rpm: 200
  download_rpm: 30
  burst_capacity: 50

storage:
  cleanup_age: 6
  cleanup_threshold: 60
  max_file_size: 1073741824  # 1GB
```

### High Security Environment

```yaml
security:
  cors_origins: ["https://app.example.com"]
  allow_degraded_start: false

logging:
  level: "WARNING"  # Reduce log verbosity

providers:
  youtube:
    retry_attempts: 1  # Fail fast
```

### Development/Testing

```yaml
server:
  host: "127.0.0.1"  # Local only
  workers: 1

logging:
  level: "DEBUG"
  format: "text"     # Human-readable

security:
  api_keys: ["dev-key-for-testing"]
  allow_degraded_start: true

rate_limiting:
  metadata_rpm: 1000  # No limits in dev
  download_rpm: 100
```

## Troubleshooting

### "At least one API key must be configured"

**Cause:** `security.api_keys` is empty and `allow_degraded_start` is false.

**Fix:**
```bash
# Via environment
export APP_SECURITY_API_KEYS='["your-api-key"]'

# Or enable degraded start for testing
export APP_SECURITY_ALLOW_DEGRADED_START=true
```

### "cleanup_threshold must be between 1 and 100"

**Cause:** Invalid value for `storage.cleanup_threshold`.

**Fix:** Set a value between 1 and 100 (percentage).

### "level must be one of ['DEBUG', 'INFO', ...]"

**Cause:** Invalid log level specified.

**Fix:** Use one of: DEBUG, INFO, WARNING, ERROR, CRITICAL (case-insensitive).

### Environment Variable Not Taking Effect

**Cause:** Wrong variable name or format.

**Checklist:**
1. Prefix is `APP_` (e.g., `APP_SERVER_PORT`)
2. Nested config uses `_` (e.g., `APP_RATE_LIMITING_METADATA_RPM`)
3. Lists are JSON: `APP_SECURITY_API_KEYS='["key1", "key2"]'`
4. Booleans are lowercase: `APP_SECURITY_ALLOW_DEGRADED_START=true`

### Configuration Not Loading from YAML

**Cause:** File not found or invalid YAML.

**Debug:**
```bash
# Check file exists
ls -la config.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Check file permissions
stat config.yaml
```

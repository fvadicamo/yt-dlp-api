# Deployment Guide

This guide covers deploying yt-dlp REST API in various environments.

## Docker Deployment (Recommended)

### Prerequisites

- Docker 20.10+
- Docker Compose v2+
- 2GB RAM minimum
- 10GB disk space for downloads

### Quick Start

```bash
# Clone repository
git clone https://github.com/fvadicamo/yt-dlp-api.git
cd yt-dlp-api

# Create directories
mkdir -p downloads cookies logs

# Configure environment
cat > .env << EOF
API_KEY=["your-secure-api-key-here"]
ALLOW_DEGRADED_START=false
LOG_LEVEL=INFO
METRICS_ENABLED=true
EOF

# Add YouTube cookies (required for most downloads)
# Export from browser using cookies.txt extension
cp /path/to/exported/cookies.txt cookies/youtube.txt

# Start service
docker compose up -d

# Verify
curl http://localhost:8000/health
```

### Docker Compose Configuration

The default `docker-compose.yml` includes (see full file for additional options):

```yaml
services:
  ytdlp-api:
    build: .
    container_name: ytdlp-api
    restart: unless-stopped
    ports:
      - "8000:8000"    # API
      - "9090:9090"    # Metrics
    environment:
      - APP_SECURITY_API_KEYS=${API_KEY?API_KEY_required}
      - APP_SECURITY_ALLOW_DEGRADED_START=${ALLOW_DEGRADED_START:-false}
      - APP_LOGGING_LEVEL=${LOG_LEVEL:-INFO}
      - APP_MONITORING_METRICS_ENABLED=${METRICS_ENABLED:-true}
    volumes:
      - ./downloads:/app/downloads
      - ./cookies:/app/cookies:ro
      - ./config.yaml:/app/config.yaml:ro
      - ./logs:/app/logs
    cpus: '2.0'
    mem_limit: 2g
    mem_reservation: 1g
    security_opt:
      - no-new-privileges:true
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

### Building Custom Image

```bash
# Build with specific tag
docker build -t ytdlp-api:v1.0.0 .

# Build for specific platform
docker build --platform linux/amd64 -t ytdlp-api:amd64 .
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes 1.24+
- kubectl configured
- Persistent volume provisioner (for downloads)

### Deployment Manifests

#### Namespace and ConfigMap

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ytdlp-api

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ytdlp-config
  namespace: ytdlp-api
data:
  config.yaml: |
    server:
      host: "0.0.0.0"
      port: 8000
    storage:
      output_dir: "/app/downloads"
      cleanup_age: 24
    rate_limiting:
      metadata_rpm: 100
      download_rpm: 10
```

#### Secrets

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: ytdlp-secrets
  namespace: ytdlp-api
type: Opaque
stringData:
  api-keys: '["your-api-key-1", "your-api-key-2"]'
  youtube-cookies: |
    # Netscape HTTP Cookie File
    .youtube.com	TRUE	/	TRUE	...
```

#### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ytdlp-api
  namespace: ytdlp-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ytdlp-api
  template:
    metadata:
      labels:
        app: ytdlp-api
    spec:
      securityContext:
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      containers:
      - name: ytdlp-api
        image: ytdlp-api:latest
        ports:
        - containerPort: 8000
          name: http
        - containerPort: 9090
          name: metrics
        env:
        - name: APP_SECURITY_API_KEYS
          valueFrom:
            secretKeyRef:
              name: ytdlp-secrets
              key: api-keys
        - name: APP_SECURITY_ALLOW_DEGRADED_START
          value: "false"
        resources:
          requests:
            memory: "1Gi"
            cpu: "1"
          limits:
            memory: "2Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /liveness
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /readiness
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: cookies
          mountPath: /app/cookies
          readOnly: true
        - name: downloads
          mountPath: /app/downloads
      volumes:
      - name: config
        configMap:
          name: ytdlp-config
      - name: cookies
        secret:
          secretName: ytdlp-secrets
          items:
          - key: youtube-cookies
            path: youtube.txt
      - name: downloads
        persistentVolumeClaim:
          claimName: ytdlp-downloads
```

#### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ytdlp-api
  namespace: ytdlp-api
spec:
  selector:
    app: ytdlp-api
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  - name: metrics
    port: 9090
    targetPort: 9090
```

#### PersistentVolumeClaim

```yaml
# k8s/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ytdlp-downloads
  namespace: ytdlp-api
spec:
  accessModes:
    - ReadWriteMany    # Required for multi-replica deployment
  resources:
    requests:
      storage: 50Gi
  # storageClassName: nfs-client  # Uncomment for NFS provisioner
```

> **Note:** For multi-replica deployments (`replicas: 2+`), use `ReadWriteMany` access mode with a storage class that supports it (NFS, GlusterFS, CephFS, or cloud-native options like AWS EFS, Azure Files, GCP Filestore). Alternatively, use `ReadWriteOnce` with `replicas: 1` or offload downloads to object storage (S3/MinIO).

### Apply Manifests

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Verify
kubectl get pods -n ytdlp-api
kubectl logs -f deployment/ytdlp-api -n ytdlp-api
```

## Production Best Practices

### Security

1. **API Keys**: Use strong, unique API keys (32+ characters)
2. **Cookies**: Mount as read-only, rotate periodically
3. **Network**: Use reverse proxy (nginx/traefik) with TLS
4. **Container**: Runs as non-root (UID 1000) by default

### Monitoring

1. **Prometheus**: Scrape `/metrics` endpoint
2. **Alerting**: Set alerts for:
   - High error rate (`http_requests_total{status=~"5.."}`)
   - Queue depth (`download_queue_size > 50`)
   - Cookie expiry (`cookie_age_days > 300`)

### Resource Planning

| Workload | CPU | Memory | Storage |
|----------|-----|--------|---------|
| Light (< 100 downloads/day) | 1 core | 1 GB | 20 GB |
| Medium (100-500/day) | 2 cores | 2 GB | 50 GB |
| Heavy (500+/day) | 4 cores | 4 GB | 100 GB+ |

### High Availability

For HA deployments:

1. **Stateless**: API is stateless, scale horizontally
2. **Shared Storage**: Use NFS/S3 for downloads volume
3. **Load Balancer**: Distribute traffic across replicas
4. **Session Affinity**: Not required (stateless)

### Backup

```bash
# Backup cookies (important!)
cp -r cookies/ /backup/cookies-$(date +%Y%m%d)/

# Backup config
cp config.yaml /backup/config-$(date +%Y%m%d).yaml
```

## Environment Variables Reference

All configuration options can be set via environment variables with the `APP_` prefix.

### Security

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_SECURITY_API_KEYS` | Yes | - | JSON array of API keys |
| `APP_SECURITY_ALLOW_DEGRADED_START` | No | `false` | Start without valid cookies |
| `APP_SECURITY_CORS_ORIGINS` | No | `["*"]` | Allowed CORS origins |

### Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_SERVER_HOST` | No | `0.0.0.0` | Bind address |
| `APP_SERVER_PORT` | No | `8000` | HTTP port |
| `APP_SERVER_WORKERS` | No | `4` | Number of uvicorn workers |

### Timeouts

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_TIMEOUTS_METADATA` | No | `10` | Metadata fetch timeout (seconds) |
| `APP_TIMEOUTS_DOWNLOAD` | No | `300` | Download timeout (seconds) |
| `APP_TIMEOUTS_AUDIO_CONVERSION` | No | `60` | Audio conversion timeout (seconds) |

### Storage

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_STORAGE_OUTPUT_DIR` | No | `/app/downloads` | Download directory |
| `APP_STORAGE_COOKIE_DIR` | No | `/app/cookies` | Cookie files directory |
| `APP_STORAGE_CLEANUP_AGE` | No | `24` | Hours before file cleanup |
| `APP_STORAGE_CLEANUP_THRESHOLD` | No | `80` | Disk usage % to trigger cleanup |
| `APP_STORAGE_MAX_FILE_SIZE` | No | `524288000` | Max file size in bytes (500MB) |

### Downloads

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_DOWNLOADS_MAX_CONCURRENT` | No | `5` | Max concurrent downloads |
| `APP_DOWNLOADS_QUEUE_SIZE` | No | `100` | Max queue size |
| `APP_DOWNLOADS_JOB_TTL` | No | `24` | Hours to keep completed jobs |

### Rate Limiting

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_RATE_LIMITING_METADATA_RPM` | No | `100` | Metadata requests per minute |
| `APP_RATE_LIMITING_DOWNLOAD_RPM` | No | `10` | Download requests per minute |
| `APP_RATE_LIMITING_BURST_CAPACITY` | No | `20` | Token bucket burst capacity |

### Templates

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_TEMPLATES_DEFAULT_OUTPUT` | No | `%(title)s-%(id)s.%(ext)s` | Output filename template |

### YouTube Provider

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_YOUTUBE_ENABLED` | No | `true` | Enable YouTube provider |
| `APP_YOUTUBE_COOKIE_PATH` | No | - | Override cookie file path |
| `APP_YOUTUBE_RETRY_ATTEMPTS` | No | `3` | Number of retry attempts |
| `APP_YOUTUBE_RETRY_BACKOFF` | No | `[2, 4, 8]` | Backoff delays (seconds) |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_LOGGING_LEVEL` | No | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `APP_LOGGING_FORMAT` | No | `json` | Log format (json or text) |

### Monitoring

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_MONITORING_METRICS_ENABLED` | No | `true` | Enable Prometheus metrics |
| `APP_MONITORING_METRICS_PORT` | No | `9090` | Metrics endpoint port |

## Troubleshooting

### Container Fails to Start

```bash
# Check logs
docker compose logs -f

# Common issues:
# - API_KEY not set: Set in .env file
# - Port conflict: Change ports in docker-compose.yml
# - Permission denied: Check volume permissions
```

### Cookie Validation Fails

```bash
# Test cookie file manually
docker compose exec ytdlp-api yt-dlp --cookies /app/cookies/youtube.txt \
  --dump-json "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### High Memory Usage

- Reduce `max_concurrent` downloads in config
- Set lower memory limit
- Enable cleanup scheduler

### Slow Downloads

- Check network bandwidth
- Verify ffmpeg is installed: `docker compose exec ytdlp-api ffmpeg -version`
- Check for rate limiting from YouTube

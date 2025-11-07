# YT-DLP REST API Backend

A REST API backend for yt-dlp video downloads and metadata extraction from YouTube.

## Project Status

This project is currently under development following a spec-driven development approach.

### Completed Tasks

- ✅ **Task 1: Project Setup and Core Infrastructure**
  - Project structure initialized with proper Python package layout
  - Configuration management with YAML and environment variable support
  - Structured logging with JSON output and request_id propagation
  - Comprehensive test suite with 97% coverage

## Development Setup

### Prerequisites

- Python 3.11+
- Virtual environment (venv, virtualenv, or conda)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd yt-dlp-api
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements-dev.txt
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_config.py -v
```

## Project Structure

```
yt-dlp-api/
├── app/                    # Application code
│   ├── api/               # API endpoints
│   ├── core/              # Core functionality (config, logging)
│   ├── models/            # Data models
│   ├── providers/         # Video provider implementations
│   ├── services/          # Business logic services
│   └── utils/             # Utility functions
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── docker/               # Docker configuration
├── docs/                 # Documentation
├── config.yaml           # Default configuration
├── requirements.txt      # Production dependencies
└── requirements-dev.txt  # Development dependencies
```

## Configuration

The application supports configuration via:

1. **YAML file** (`config.yaml`)
2. **Environment variables** (with `APP_` prefix)

Environment variables take precedence over YAML configuration.

### Example Configuration

```yaml
server:
  host: "0.0.0.0"
  port: 8000

logging:
  level: "INFO"
  format: "json"

storage:
  output_dir: "/app/downloads"
  max_file_size: 524288000  # 500MB
```

### Environment Variable Override

```bash
export APP_SERVER_PORT=9000
export APP_LOGGING_LEVEL=DEBUG
```

## Features

### Implemented

- ✅ YAML-based configuration with validation
- ✅ Environment variable overrides
- ✅ Structured JSON logging with request_id propagation
- ✅ API key hashing for secure logging
- ✅ Comprehensive test coverage

### Planned

- 🔄 Provider abstraction layer
- 🔄 YouTube provider implementation
- 🔄 Cookie management system
- 🔄 REST API endpoints
- 🔄 Job management and async downloads
- 🔄 Rate limiting
- 🔄 Docker containerization

## Development Guidelines

### Virtual Environment

**Always use a virtual environment for Python development.** Never use system/global Python.

See `.kiro/steering/python-venv-requirement.md` for detailed guidelines.

### Git Workflow

- Work on feature branches: `feature/<task-name>`
- Commit frequently with descriptive messages
- Follow Conventional Commits format
- Merge to `develop` branch via merge commit (no squash/rebase)

### Testing

- Write tests for all new functionality
- Maintain high test coverage (>90%)
- Run tests before committing
- Use pytest fixtures for common setup

## License

MIT

## Contributing

This project follows spec-driven development. See `.kiro/specs/yt-dlp-rest-api/` for:
- `requirements.md` - Feature requirements
- `design.md` - Architecture and design
- `tasks.md` - Implementation tasks

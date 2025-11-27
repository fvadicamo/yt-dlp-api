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

### Quick Start

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
# or
pip install -e ".[dev]"
```

4. Setup pre-commit hooks:
```bash
pre-commit install
pre-commit run --all-files
```

Or use the Makefile for quick setup:
```bash
make setup
```

### Development Tools

This project uses a comprehensive set of development tools:

- **Black** - Code formatting
- **isort** - Import sorting
- **Flake8** - Linting (with plugins: bugbear, comprehensions, simplify, docstrings, pep8-naming)
- **mypy** - Type checking
- **Bandit** - Security scanning
- **pytest** - Testing with coverage
- **pre-commit** - Git hooks for automated quality checks

All tools are configured in `pyproject.toml` for centralized configuration.

For detailed setup instructions, tool usage, and best practices, see [Development Setup Guide](docs/DEVELOPMENT_SETUP.md).

### Running Tests

```bash
# Run all tests with coverage
pytest
# or
make test-cov

# Run specific test file
pytest tests/unit/test_config.py -v

# Run all quality checks
make check
```

### Common Commands

```bash
make help           # Show all available commands
make format         # Format code with Black and isort
make lint           # Run Flake8 linter
make type-check     # Run mypy type checker
make security       # Run Bandit security scanner
make test           # Run tests
make test-cov       # Run tests with coverage
make check          # Run all checks
make clean          # Clean cache files
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

### Code Quality

This project enforces code quality through:

- **Pre-commit hooks** - Automated checks before each commit
- **90% test coverage** - Minimum coverage requirement
- **Type safety** - Full mypy type checking
- **Security scanning** - Bandit security checks
- **Consistent formatting** - Black + isort

### Git Workflow

- Work on feature branches: `feature/<task-name>`
- Commit frequently with descriptive messages
- Follow Conventional Commits format
- Pre-commit hooks run automatically on commit
- Full test suite runs on push
- Merge to `develop` branch via merge commit (no squash/rebase)

### Testing

- Write tests for all new functionality
- Maintain high test coverage (>90%)
- Tests run automatically via pre-commit on push
- Use pytest fixtures for common setup

### Virtual Environment

**Always use a virtual environment for Python development.** Never use system/global Python.

See `.kiro/steering/python-venv-requirement.md` for detailed guidelines.

## License

MIT

## Contributing

This project follows spec-driven development. See `.kiro/specs/yt-dlp-rest-api/` for:
- `requirements.md` - Feature requirements
- `design.md` - Architecture and design
- `tasks.md` - Implementation tasks

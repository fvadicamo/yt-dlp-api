.PHONY: help install install-dev setup test test-cov lint format type-check security check clean pre-commit

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -r requirements.txt

install-dev:  ## Install development dependencies
	pip install -r requirements-dev.txt

setup:  ## Complete development setup (install deps + pre-commit)
	pip install -e ".[dev]"
	pre-commit install
	pre-commit install --hook-type push
	@echo "✓ Development environment ready!"

test:  ## Run tests
	pytest

test-cov:  ## Run tests with coverage report
	pytest --cov=app --cov-report=term-missing --cov-report=html

lint:  ## Run linting (flake8)
	flake8 .

format:  ## Format code (black + isort)
	black .
	isort .

format-check:  ## Check code formatting without changes
	black --check .
	isort --check-only .

type-check:  ## Run type checking (mypy)
	mypy .

security:  ## Run security checks (bandit)
	bandit -r app/

check:  ## Run all checks (format, lint, type, security, test)
	@echo "Running format check..."
	@make format-check
	@echo "\nRunning linter..."
	@make lint
	@echo "\nRunning type checker..."
	@make type-check
	@echo "\nRunning security scanner..."
	@make security
	@echo "\nRunning tests..."
	@make test-cov
	@echo "\n✓ All checks passed!"

pre-commit:  ## Run pre-commit on all files
	pre-commit run --all-files

pre-commit-update:  ## Update pre-commit hooks
	pre-commit autoupdate

clean:  ## Clean cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ coverage.xml .coverage.* 2>/dev/null || true
	@echo "✓ Cleaned cache and temporary files"

venv:  ## Create virtual environment
	python3 -m venv venv
	@echo "✓ Virtual environment created. Activate with: source venv/bin/activate"

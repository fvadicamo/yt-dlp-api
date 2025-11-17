#!/bin/bash
# Verification script for development setup

set -e

echo "🔍 Verifying development setup..."
echo ""

# Check Python version
echo "✓ Checking Python version..."
python --version | grep "3.11" || (echo "❌ Python 3.11+ required" && exit 1)

# Check virtual environment
echo "✓ Checking virtual environment..."
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Virtual environment not activated"
    echo "   Run: source venv/bin/activate"
fi

# Check if dependencies are installed
echo "✓ Checking dependencies..."
python -c "import black, isort, flake8, mypy, pytest, bandit" 2>/dev/null || \
    (echo "❌ Dependencies not installed. Run: make install-dev" && exit 1)

# Check configuration files
echo "✓ Checking configuration files..."
test -f pyproject.toml || (echo "❌ pyproject.toml not found" && exit 1)
test -f .pre-commit-config.yaml || (echo "❌ .pre-commit-config.yaml not found" && exit 1)
test -f .flake8 || (echo "❌ .flake8 not found" && exit 1)

# Check pre-commit installation
echo "✓ Checking pre-commit hooks..."
if [ -f .git/hooks/pre-commit ]; then
    echo "   Pre-commit hooks installed"
else
    echo "⚠️  Pre-commit hooks not installed. Run: pre-commit install"
fi

echo ""
echo "✅ Setup verification complete!"
echo ""
echo "Next steps:"
echo "  1. Run 'make format' to format code"
echo "  2. Run 'make check' to run all quality checks"
echo "  3. Run 'make test-cov' to run tests with coverage"

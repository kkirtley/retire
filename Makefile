.PHONY: help install test lint format format-check pre clean venv ui

SCENARIO ?= scenarios/baseline_canonical.yaml
COMPARE ?=

# Default target
help:
	@echo "RetirePlan Development Commands"
	@echo "================================"
	@echo ""
	@echo "Setup:"
	@echo "  make venv         Create virtual environment (.venv)"
	@echo "  make install      Install package in editable mode with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test         Run pytest"
	@echo "  make lint         Run ruff linter (ruff check .)"
	@echo "  make format-check Run black formatter check"
	@echo "  make format       Auto-format code with black"
	@echo "  make ui           Launch desktop UI (override with SCENARIO=... COMPARE=...)"
	@echo ""
	@echo "Pre-commit:"
	@echo "  make pre          Run ALL checks before pushing: lint + format-check + test"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        Remove cache, artifacts, and .pytest_cache"
	@echo ""

# Create virtual environment
venv:
	@echo "Creating virtual environment..."
	python3.12 -m venv .venv
	@echo "✅ Virtual environment created at .venv"
	@echo "   Activate with: source .venv/bin/activate"

# Install package and dependencies
install:
	@echo "Installing retireplan in editable mode..."
	. .venv/bin/activate && pip install --upgrade pip && pip install -e ".[dev]"
	@echo "✅ Installation complete"

# Run tests
test:
	@echo "Running pytest..."
	. .venv/bin/activate && pytest
	@echo "✅ Tests complete"

# Run linter
lint:
	@echo "Running ruff linter..."
	. .venv/bin/activate && ruff check .
	@echo "✅ Linting complete"

# Check formatting
format-check:
	@echo "Checking code formatting with black..."
	. .venv/bin/activate && black --check .
	@echo "✅ Formatting check complete"

# Auto-format code
format:
	@echo "Auto-formatting code with black..."
	. .venv/bin/activate && black .
	@echo "✅ Code formatted"

# Launch desktop UI
ui:
	@echo "Launching RetirePlan UI..."
	@if [ -n "$(COMPARE)" ]; then \
		. .venv/bin/activate && retireplan ui $(SCENARIO) --compare $(COMPARE); \
	else \
		. .venv/bin/activate && retireplan ui $(SCENARIO); \
	fi

# Pre-push: run all checks
pre: lint format-check test
	@echo ""
	@echo "╔════════════════════════════════════════╗"
	@echo "║ ✅ ALL CHECKS PASSED - Ready to push! ║"
	@echo "╚════════════════════════════════════════╝"

# Clean up cache and artifacts
clean:
	@echo "Cleaning up cache and artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	@echo "✅ Cleanup complete"

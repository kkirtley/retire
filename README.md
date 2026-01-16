# RetirePlan

Deterministic retirement planning engine for veteran households. Models VA income, Social Security, Medicare, taxes, and comprehensive financial projections through age 100.

## Requirements

- Python 3.12+
- pip (Python package installer)

## Setup & Development

### 1. Create Virtual Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 2. Install Package in Development Mode

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

This installs:
- Core dependencies: `pydantic`, `pyyaml`, `typer`
- Dev dependencies: `pytest`, `ruff`, `black`, `pre-commit`

### 3. Verify Installation

```bash
pip list | grep retireplan
```

## Make Targets

The project includes a `Makefile` for convenient development commands:

```bash
make help         # Show all available targets
make test         # Run pytest
make lint         # Run ruff linter
make format-check # Check code formatting with black
make format       # Auto-format code with black
make pre          # Run ALL checks: lint + format-check + test (use before pushing)
make clean        # Remove cache and artifacts
make install      # Install package in editable mode with dev dependencies
make venv         # Create virtual environment
```

### Pre-push Workflow

Before pushing your code, run:
```bash
make pre
```

This will run:
1. **Ruff linting** — code style and correctness checks
2. **Black format check** — code formatting validation
3. **Pytest** — unit tests

If all pass, you'll see a ready-to-push confirmation.

## Running Tests

```bash
pytest
```

Or using make:
```bash
make test
```

For verbose output with details:
```bash
pytest -v
```

## Code Quality

### Run Linter (Ruff)

```bash
ruff check .
```

Using make:
```bash
make lint
```

Auto-fix fixable issues:
```bash
ruff check . --fix
```

### Run Formatter Check (Black)

```bash
black --check .
```

Using make:
```bash
make format-check
```

Auto-format code:
```bash
black .
```

Using make:
```bash
make format
```

### Run All Checks

Using make (recommended):
```bash
make pre
```

Or manually:
```bash
ruff check .
black --check .
pytest
```

## Pre-commit Hooks

Setup pre-commit hooks to run checks automatically before each commit:

```bash
pre-commit install
```

This installs git hooks that will run:
- Ruff linting (with auto-fix)
- Black formatting
- Trailing whitespace cleanup
- File ending normalization
- YAML validation
- Large file detection

To run hooks manually on all files:
```bash
pre-commit run --all-files
```

## CLI Commands

### Validate Scenario

```bash
retireplan validate scenarios/baseline.yaml
```

### Run Projection

```bash
retireplan run scenarios/baseline.yaml --out results/baseline_run.json --charts results/
```

## Project Structure

```
retireplan/               # Main package
├── __init__.py
├── cli/                  # Command-line interface
│   ├── __init__.py
│   └── main.py
├── core/                 # Projection engine (Stage 2+)
├── tax/                  # Tax calculations (Stage 3+)
├── medicare/             # Medicare & IRMAA (Stage 6+)
├── mortgage/             # Mortgage amortization (Stage 4+)
└── io/                   # YAML/JSON I/O (Stage 1+)

scenarios/                # YAML scenario files
tests/                    # Unit and integration tests
.pre-commit-config.yaml   # Pre-commit hooks configuration
.gitlab-ci.yml            # GitLab CI pipeline
pyproject.toml            # Project configuration
README.md                 # This file
```

## CI/CD

The project includes a GitLab CI configuration (`.gitlab-ci.yml`) that runs:

1. **Ruff Check** - Code linting
2. **Black Check** - Code formatting validation
3. **Pytest** - Unit tests

All checks must pass before merging.

## Development Workflow

1. Create a feature branch
2. Activate virtual environment: `source .venv/bin/activate`
3. Make changes to code
4. Run pre-commit hooks: `pre-commit run --all-files`
5. Run tests: `pytest`
6. Commit changes (pre-commit hooks will run automatically)
7. Push and create merge request

## Architecture

RetirePlan follows a **local-first** design with:

- **No external data integration**: All calculations run offline
- **Deterministic v1**: No Monte Carlo simulation (extensible for v2)
- **Clean separation**: Core engine, tax module, account management, CLI
- **Comprehensive testing**: Unit tests, golden tests, scenario validation
- **YAML-based scenarios**: Versioned, human-readable configuration

### Build Stages

- **Stage 0**: ✅ Project scaffolding, CI tooling
- **Stage 1**: Data model + YAML loader + validation
- **Stage 2**: Deterministic annual projection engine
- **Stage 3**: Federal + Missouri taxes
- **Stage 4**: Mortgage amortization + payoff solver
- **Stage 5**: Social Security + VA income + survivor transitions
- **Stage 6**: Medicare premiums + IRMAA thresholds
- **Stage 7**: Withdrawal strategy + Roth conversions + RMDs
- **Stage 8**: Reporting (tables + charts)
- **Stage 9**: PySide6 UI + SQLite persistence

## License

MIT

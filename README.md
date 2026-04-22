# RetirePlan

Deterministic, local-first retirement planning engine for a veteran household. The current codebase is organized around a rich YAML scenario model, a package-level scenario loader, and a staged projection engine that will expand capability area by area through the full retirement workflow.

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

## Current Capability

The current implementation uses the schema in `retireplan/schema/retirement.py` as the authoritative model and exposes it through the package for validation and projection work.

The default execution path is `deterministic_annual`. Historical analysis is an optional secondary comparison layer and is not part of the primary engine mode.

Scenario inheritance is implicit. Active `scenario_*.yaml` files are delta documents that the loader merges onto the sibling `scenarios/baseline_canonical.yaml`; there is no supported `extends` field.

Implemented now:
- Schema-backed YAML loading and validation
- CLI `validate` and `run` commands wired to the loader
- Non-fatal scenario diagnostics for version/file mismatches and stale age data
- Annual projection with taxes, mortgage cashflow, Medicare and IRMAA costs, survivor transitions, and yearly ledger output
- Deterministic resource-pressure spending guardrails that can ratchet base living expenses down toward a configured floor before a year is marked failed
- Stage 7 withdrawal strategy support including Roth conversions, RMDs, QCDs, charitable-giving coordination, and top-level projection summaries
- Stage 8 reporting exports including chart-ready series and CSV/JSON output artifacts from the CLI
- Stage 9 PySide6 desktop UI with YAML-first scenario editing, results tabs, charts, Roth conversion planning, IRMAA review, and scenario comparison

Optional scenario simplification:

```yaml
strategy:
	account_rollovers:
		enabled: true
		roll_traditional_401k_to_ira: true
		roll_roth_401k_to_ira: true
```

When enabled, the engine rolls each retired owner's 401k balances into the first same-owner IRA of the matching tax type at retirement. The original 401k buckets remain in the ledger with zero balances so historical contributions and pre-retirement reporting still reconcile.

See `STAGE_TRACKER.md` for the persistent deterministic stabilization status.

## CLI Commands

### Validate Scenario

```bash
retireplan validate scenarios/baseline_canonical.yaml
```

Force strict validation when you want loader warnings promoted to hard failures:

```bash
retireplan validate scenarios/baseline_canonical.yaml --strict-validation
```

For real household runs, prefer `--strict-validation` so stale ages, filename/version mismatches, and incomplete modeled-death inputs fail before projection output is produced.

### Run Projection

```bash
retireplan run scenarios/baseline_canonical.yaml --out results/baseline_run.json --charts results/
```

The `run` command always executes the `deterministic_annual` engine mode. If a scenario enables `historical_analysis`, the CLI appends that analysis as a secondary report section after the deterministic projection completes.

Strict validation is also available on `run`:

```bash
retireplan run scenarios/baseline_canonical.yaml --strict-validation --out results/baseline_run.json --charts results/
```

Current strict-validation behavior hard-fails on schema errors and on loader diagnostics that are warnings in non-strict mode, including stale ages, filename/version mismatches, and incomplete modeled-death data.

Scenario merge behavior is fixed globally in code:
- objects deep-merge
- lists replace

`validation.override_merge_rules` remains in the schema for compatibility but does not alter runtime merge behavior.

### Launch Desktop UI

```bash
retireplan ui scenarios/baseline_canonical.yaml --compare scenarios/scenario_high_inflation.yaml
```

This writes the main projection payload to `--out` and reporting artifacts to `--charts`, including:
- `reporting.json`
- `chart_series.json`
- `yearly_overview.csv`
- `cashflow.csv`
- `tax_detail.csv`
- `account_balances.csv`

## Project Structure

```
retireplan/               # Main package
├── __init__.py
├── cli/                  # Command-line interface
│   ├── __init__.py
│   └── main.py
├── core/                 # Projection engine (Stage 2+)
├── reporting/            # Reporting exports (Stage 8)
├── ui/                   # Desktop UI (Stage 9)
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

RetirePlan follows a local-first design with:

- No external financial data integration; all calculations run offline
- Deterministic v1 projections; Monte Carlo remains out of scope for the first release
- Schema-first scenario modeling with YAML as the current system of record
- Clean separation between scenario I/O, timeline/projection logic, CLI, and later tax/Medicare/mortgage modules
- Test-first delivery with scenario validation, behavioral tests, and stage-by-stage engine verification

## Planning Direction

The current planning direction combines the stage roadmap from `AGENTS.md` with the near-term implementation sequence in `plan.md`.

Near-term work already folded into the direction of the app:
- Keep `scenario_loader.py` as the entry point for YAML parsing, schema validation, and clean diagnostics
- Expand validation tests around account references, contribution dates, conversion constraints, and bridge-account rules
- Use `timeline_builder.py` as the transition boundary into later tax, Medicare, mortgage, and strategy modules so age milestones, proration windows, retirement transitions, and start/stop events stay explicit
- Continue engine work in layers rather than mixing domains: balances/contributions/expenses first, then taxes, then mortgage, then conversions, then QCD/RMD/giving

### Build Stages

- Stage 0: project scaffolding, packaging, linting, formatting, and CI workflow
- Stage 1: authoritative schema, scenario loader, YAML validation, and diagnostics
- Stage 2: deterministic annual ledger engine with timeline-based annual periods and current cashflow coverage
- Stage 3: federal bracket-based tax engine plus generic state income tax modeling
- Stage 4: mortgage amortization, extra-principal solver, and housing cashflow detail
- Stage 5: Social Security, VA, and survivor-transition rules
- Stage 6: Medicare premiums, IRMAA tiers, and lookback logic
- Stage 7: withdrawals, Roth conversions, RMDs, QCDs, and charitable giving coordination
- Stage 8: reporting outputs, export-ready tables, and chart data
- Stage 9: PySide6 desktop UI, scenario editing, and later SQLite persistence

See `STAGE_TRACKER.md` for the live stabilization-task status and completion notes.

## License

MIT

# RetirePlan Stage Tracker

This document is the running build tracker for the application. Update it as each stage moves from planned to in progress to complete.

Status legend:
- `Complete`: implemented, tested, and reflected in the active code path
- `In Progress`: partially implemented or wired, but not complete end to end
- `Planned`: defined but not started in code

## Stage Summary

| Stage | Status   | Scope                                                                    | Current Notes                                                                                                                                                                        |
| ----- | -------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0     | Complete | Repo scaffolding, packaging, linting, formatting, pytest, CLI entrypoint | `pyproject.toml`, `Makefile`, lint/format/test flow are active and passing                                                                                                           |
| 1     | Complete | Schema model, YAML loader, validation, diagnostics                       | Loader is wired through the package and CLI; baseline scenario validates                                                                                                             |
| 2     | Complete | Deterministic annual projection engine                                   | Timeline-based annual periods, modular Stage 2 cashflow calculations, reusable timeline events, and golden ledger checkpoints are implemented; later-stage domains are still pending |
| 3     | Planned  | Federal and Missouri tax modeling                                        | YAML tax tables exist; engine integration is still pending                                                                                                                           |
| 4     | Planned  | Mortgage amortization and payoff solver                                  | Mortgage inputs exist; current engine treats mortgage as scheduled payments only                                                                                                     |
| 5     | Planned  | Social Security, VA, and survivor transitions                            | Scenario supports these rules; engine needs fuller transition logic                                                                                                                  |
| 6     | Planned  | Medicare and IRMAA                                                       | YAML inputs exist; lookback and premium application are pending                                                                                                                      |
| 7     | Planned  | Withdrawals, Roth conversions, RMDs, QCDs, giving                        | Strategy schema is present; operational engine logic is pending                                                                                                                      |
| 8     | Planned  | Reporting tables and chart outputs                                       | Run output exists as JSON ledger; reporting layer is still pending                                                                                                                   |
| 9     | Planned  | Desktop UI and later SQLite persistence                                  | UI remains intentionally deferred until core engine stages stabilize                                                                                                                 |

## Stage Detail

### Stage 0

Status: `Complete`

Delivered:
- Package scaffolding and CLI packaging
- Ruff, Black, pytest, and pre-commit tooling
- Basic workspace development commands in `Makefile`

Exit criteria:
- Keep lint, formatting, and tests green as later stages are added

### Stage 1

Status: `Complete`

Delivered:
- Authoritative scenario schema in `retireplan/schema/retirement.py`
- Package-level schema access via `retireplan/scenario.py`
- YAML loading and validation via `retireplan/io/scenario_loader.py`
- Warnings for filename/version mismatch, stale current ages, and incomplete modeled death data

Follow-up notes:
- Narrow contribution-date validation if future percentage-based rules are added that are not employment-linked

### Stage 2

Status: `Complete`

Delivered:
- Annual projection loop through wife age 100
- Timeline builder for annual periods, proration windows, milestone events, and retirement-state transitions
- Modular Stage 2 income, expense, contribution, withdrawal, and return application flow
- Basic earned income, VA, Social Security, pension, expenses, contributions, withdrawals, and end-of-year balances
- Golden-style ledger assertions for first-year, retirement-year, and final-year checkpoints
- Reusable typed timeline events for later tax, Medicare, mortgage, and conversion stages
- JSON run output through the CLI

Exit criteria met:
- Stage 2 projection behavior is covered by passing tests and checkpoint assertions
- The projection loop now acts as orchestration rather than a single monolithic calculation block
- Timeline event hooks are ready for Stage 3 and later modules

Next stage:
- Begin Stage 3 tax modeling with a dedicated federal bracket engine, Missouri effective-rate approximation, and taxable-income composition tests

### Stage 3

Status: `Planned`

Target deliverables:
- Federal bracket-based tax engine using scenario tables
- Missouri effective-rate tax approximation
- Tests for deductions, brackets, filing-status changes, and taxable income composition

### Stage 4

Status: `Planned`

Target deliverables:
- Mortgage amortization schedule
- Extra-principal solver to satisfy payoff-by-age target
- Property tax and homeowners insurance rolled into annual housing outputs

### Stage 5

Status: `Planned`

Target deliverables:
- Social Security claim timing and COLA progression
- VA benefit stop-at-death and survivor-benefit conditions
- Survivor filing-status and expense-stepdown transitions

### Stage 6

Status: `Planned`

Target deliverables:
- Medicare Part B and Part D premiums
- IRMAA tier selection with two-year MAGI lookback
- Warnings when conversions or income changes trigger tier movement

### Stage 7

Status: `Planned`

Target deliverables:
- Withdrawal ordering across account types
- Roth conversion policy execution and tax funding behavior
- RMD calculations, QCD application, and charitable giving coordination

### Stage 8

Status: `Planned`

Target deliverables:
- Engine-level reporting outputs
- Export-ready tables and chart series for balances, taxes, and cashflow

### Stage 9

Status: `Planned`

Target deliverables:
- PySide6 desktop UI over the engine library
- Scenario editing workflow
- SQLite persistence as a later follow-on after YAML-first stability
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
| 3     | Complete | Federal and state tax modeling                                           | Federal and generic state tax modules are integrated into the yearly ledger with withdrawal-aware settlement and tax coverage tests                                                  |
| 4     | Complete | Mortgage amortization and payoff solver                                  | Monthly amortization, payoff-by-age solving, annual mortgage ledger detail, and projection regression coverage are implemented and validated                                         |
| 5     | Complete | Social Security, VA, and survivor transitions                            | Claim timing, COLA progression, survivor filing-status changes, expense stepdown, SS step-up, and VA survivor eligibility are implemented and covered by projection tests            |
| 6     | Complete | Medicare and IRMAA                                                       | Base premiums, 2-year IRMAA lookback, yearly Medicare expense lines, and IRMAA tier alerts are integrated and covered by unit and projection tests                                   |
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
- Begin Stage 4 mortgage amortization, payoff solver, and housing-cashflow integration work

### Stage 3

Status: `Complete`

Plan:
- Create a dedicated `retireplan/tax/` package with pure tax-calculation functions before projection integration
- Compute annual taxable income from currently implemented cashflow components only: earned income, pension, taxable Social Security approximation, and traditional-account withdrawals
- Apply federal standard deduction and scenario-provided bracket tables using current filing status
- Apply state tax through a generic state-tax configuration layer, with `none` and `effective_rate` models in Stage 3
- Integrate tax outputs into each projection ledger row as separate values rather than burying them inside expenses
- Resolve the cashflow/tax feedback loop by iterating withdrawals and taxes until the annual deficit settles

Implementation tickets:
- Ticket S3-1: federal bracket engine and standard-deduction handling
- Ticket S3-2: Social Security taxable-benefit approximation for MFJ and Single
- Ticket S3-3: generic state-tax summary with `none` and `effective_rate` models
- Ticket S3-4: projection integration with iterative withdrawal-aware tax settlement
- Ticket S3-5: unit and projection tests covering deductions, filing-status changes, and taxable-income composition

Delivered:
- Tax package scaffold under `retireplan/tax/`
- Federal bracket calculation using scenario tax tables
- Generic state-tax calculation keyed off the configured current state and model
- Tax summary integration into yearly projection rows
- Projection cashflow settlement updated to account for tax-driven withdrawal feedback
- Dedicated tests for federal tax, taxable Social Security, traditional-withdrawal taxation, and filing-status handling
- Baseline projection regression updated for tax-aware behavior, including current failure-year detection under the baseline assumptions

Exit criteria:
- `ProjectionRow` includes separate federal and state tax outputs
- Taxable income composition is covered by tests for the currently implemented income and withdrawal types
- Filing-status changes affect both standard deduction selection and bracket selection
- Full repo checks remain green after tax integration

Follow-up notes:
- Add Roth conversions, RMDs, and other later-stage taxable flows when those engine stages are implemented

### Stage 4

Status: `Complete`

Plan:
- Create a dedicated `retireplan/mortgage/` package for monthly amortization and payoff solving
- Solve for additional monthly principal required to satisfy the payoff-by-age target without changing the public scenario shape
- Aggregate monthly mortgage activity into annual ledger detail for payment, interest, principal, extra principal, and remaining balance
- Feed annual mortgage cash outflows into Stage 2/3 expense handling while keeping mortgage detail separate in the ledger

Implementation tickets:
- Ticket S4-1: monthly amortization schedule from the scenario mortgage inputs
- Ticket S4-2: payoff-by-age solver for extra principal
- Ticket S4-3: annual mortgage summary integration into the projection ledger
- Ticket S4-4: tests for amortization math, payoff timing, and projection integration

Delivered:
- Mortgage amortization schedule
- Extra-principal solver to satisfy payoff-by-age target
- Projection ledger mortgage detail for scheduled payment, extra principal, interest, principal, and remaining balance
- Property tax and homeowners insurance remain in annual housing outputs alongside mortgage cash flow

Exit criteria:
- Mortgage payoff is enforced by the configured target age when enabled
- Projection rows expose mortgage detail separately from generic expenses
- Full repo checks remain green after mortgage integration

Next stage:
- Begin Stage 5 Social Security, VA, and survivor-transition integration work beyond the current baseline behavior

### Stage 5

Status: `Complete`

Delivered:
- Social Security claim timing and COLA progression in the annual income layer
- Survivor Social Security step-up to the higher benefit after husband death and claim eligibility
- VA disability stop after the modeled death year and conditional VA survivor benefit handling
- Survivor filing-status transition to Single in the year after death
- Survivor expense stepdown using the configured surviving-expense ratio
- Projection tests covering survivor filing status, expense reduction, VA survivor eligibility, and Social Security survivor behavior

Exit criteria:
- Social Security claim timing and COLA progression are reflected in yearly income outputs
- VA stop-at-death and survivor-benefit conditions are covered by tests
- Survivor filing-status and expense-stepdown transitions are covered by tests

Next stage:
- Begin Stage 6 Medicare premiums, IRMAA lookback logic, and premium integration into annual cashflow

### Stage 6

Status: `Complete`

Plan:
- Create a dedicated `retireplan/medicare/` package with pure Medicare premium and IRMAA calculations
- Apply Part B and Part D premiums when each living spouse reaches Medicare age
- Determine IRMAA tier from the configured 2-year MAGI lookback using the filing status from the lookback year
- Feed Medicare premiums into annual expense lines while keeping Medicare detail separate in the ledger

Implementation tickets:
- Ticket S6-1: Medicare premium calculation for covered spouses
- Ticket S6-2: IRMAA tier selection using 2-year lookback MAGI and filing status
- Ticket S6-3: projection integration for yearly Medicare expense lines and ledger detail
- Ticket S6-4: tests for premium onset, lookback logic, and IRMAA tier behavior

Delivered:
- `retireplan/medicare/` package scaffold and premium calculator
- Base Part B and Part D premium integration into projection expenses
- IRMAA tier selection using 2-year MAGI lookback and filing-status threshold tables
- Projection-row Medicare detail and IRMAA tier-change alerts
- Tests for Medicare onset, IRMAA lookback behavior, IRMAA tier changes, and projection-level Medicare expense integration

Exit criteria:
- Medicare premium costs appear in yearly projection output for eligible spouses
- IRMAA tier selection uses the 2-year lookback convention and is covered by tests
- Full repo checks remain green after Medicare integration

Next stage:
- Begin Stage 7 withdrawal ordering, Roth conversions, RMDs, QCDs, and charitable-giving coordination

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
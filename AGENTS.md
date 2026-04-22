# Deterministic Annual Engine Stabilization Work Package

## Objective

Stabilize the project around the **deterministic annual retirement planning engine** as the canonical execution path.

This work package is focused on:
- correctness
- consistency
- testability

NOT new features.

---

## Scope Rules

### In Scope
- Scenario file separation
- Loader behavior and merge semantics
- Strict validation mode
- Execution order enforcement
- Age/date handling for annual modeling
- Bridge account behavior
- Mortgage payoff logic
- Deterministic output contract
- Regression tests

### Out of Scope
- UI redesign
- Monte Carlo
- External integrations
- New planning features
- Broad refactoring of package layout

---

## Mandatory Implementation Principles

- Do not invent new YAML fields
- Do not rename existing YAML fields without migration
- Do not bypass validation
- Do not duplicate logic in UI
- Do not use Car Fund for retirement flows
- Do not treat experimental fields as baseline
- Deterministic annual engine is the default
- Tests must pass before proceeding
- Only one canonical baseline is allowed in the `scenarios/` root directory
- Legacy baselines must be archived or explicitly marked deprecated
- Tests must never depend on `baseline_canonical.yaml`
- Scenario variants must extend the canonical baseline through the repo's supported delta mechanism unless they are explicitly standalone test fixtures
- If flexibility conflicts with deterministic correctness, choose deterministic correctness

---

# Tasks

## Task 1 — Scenario Separation

### Goal
Separate baseline, test fixtures, and scenarios.

### Create
- `scenarios/baseline_canonical.yaml`
- `scenarios/test_baseline_minimal.yaml`
- `scenarios/scenario_*.yaml`

### Requirements
- Tests must NOT depend on baseline file
- Add `scenarios/README.md`

### Acceptance Criteria
- Baseline loads cleanly
- Test fixture is stable
- Tests pass independently of baseline

---

## Task 2 — Deterministic Engine Mode

### Goal
Make deterministic annual the default engine.

### Requirements
- Default execution mode: `deterministic_annual`
- CLI `run` uses this mode
- Historical analysis is optional, not primary

### Acceptance Criteria
- No ambiguity in execution path
- Docs reflect deterministic-first design

---

## Task 3 — Merge Behavior

### Goal
Align loader behavior with schema merge rules.

### Requirements
- Deep merge objects
- Replace lists (unless explicitly supported otherwise)

### Tests
- Object merge works
- List replacement works

### Acceptance Criteria
- Merge behavior matches documentation

---

## Task 4 — Strict Validation Mode

### Goal
Enable production-grade validation.

### Add
- CLI flag: `--strict-validation`

### Fail on
- Age/date inconsistencies
- Invalid account references
- Bad contribution timing
- Death model inconsistencies
- Unsupported fields

### Acceptance Criteria
- Strict mode fails hard
- Non-strict mode allows warnings

---

## Task 5 — Execution Order Contract

### Goal
Prevent sequencing bugs.

### Define Order
1. Build timeline
2. Apply proration
3. Compute income
4. Compute expenses
5. Apply contributions
6. Execute strategy
7. Compute taxes
8. Settle surplus/deficit
9. Apply returns
10. Write ledger

### Requirements
- Document in `docs/execution_order.md`
- Align code with order
- Add integration test

---

## Task 6 — Field Classification

### Goal
Separate core vs advanced features.

### Categories
- Core deterministic
- Advanced supported
- Experimental

### Requirements
- Remove experimental fields from baseline
- Keep them in scenario variants

---

## Task 7 — Account Integrity

### Goal
Eliminate reference errors.

### Validate
- All accounts exist
- All destinations valid
- Bridge account present if used
- QCD requires IRA account
- Restricted accounts never used

### Acceptance Criteria
- Invalid configs fail validation

---

## Task 8 — Age/Date Semantics

### Goal
Remove ambiguity in age handling.

### Requirements
- Age derived from DOB + date
- `current_age` is informational only

### Tests
- SS claim timing
- Medicare start
- QCD start
- Proration correctness

---

## Task 9 — Bridge Account Behavior

### Goal
Make bridge usage deterministic.

### Rules

**Before age 70**
- Primary: conversion taxes
- Secondary: living expenses (only if needed)

**After age 70**
- Growth and liquidity account

### Tests
- Tax-first usage
- Controlled fallback usage
- Post-70 behavior change

---

## Task 10 — Mortgage Logic

### Goal
Make payoff deterministic.

### Requirements
- Compute payment if null
- Compute extra principal for payoff target
- Handle proration

### Tests
- Standard amortization
- Target payoff logic

---

## Task 11 — Output Contract

### Required Outputs
- Yearly ledger
- Account balances
- Taxes
- Conversion totals
- RMD/QCD/giving
- Failure year
- Net worth
- Total taxes
- Total conversions
- IRA balance at 70

### Acceptance Criteria
- Always produced
- Verified in tests

---

## Task 12 — Regression Suite

### Goal
Prevent silent breakage.

### Tests
- Baseline runs
- Retirement transition
- Proration correctness
- SS timing
- Conversion tax sourcing
- Bridge usage rules
- Car Fund unused
- Spending guardrails
- Survivor logic
- QCD behavior

---

# Implementation Order

1. Task 1 — Scenario separation  
2. Task 3 — Merge behavior  
3. Task 4 — Strict validation  
4. Task 5 — Execution order  
5. Task 8 — Age/date semantics  
6. Task 7 — Account integrity  
7. Task 9 — Bridge behavior  
8. Task 10 — Mortgage logic  
9. Task 11 — Output contract  
10. Task 12 — Regression suite  
11. Task 6 — Field classification  
12. Task 2 — Engine mode cleanup  

---

# Development Rules

## Do
- Keep changes small
- Update tests continuously
- Prefer explicit logic
- Preserve deterministic assumptions

## Do Not
- Add Monte Carlo
- Redesign UI
- Add new features
- Refactor structure broadly
- Invent YAML fields
- Hide errors behind warnings

---

# Deliverables

- Clean canonical baseline YAML
- Stable test scenario YAML
- Deterministic engine as default
- Strict validation mode
- Execution order documentation
- Hardened bridge and mortgage logic
- Regression test suite

---

# Final Instruction

Favor **deterministic correctness over flexibility**.

If forced to choose:
- choose correctness
- reject ambiguity
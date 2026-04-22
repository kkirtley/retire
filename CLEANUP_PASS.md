# Final Alignment Pass — Deterministic Annual Engine

## Objective

Complete the remaining alignment work so the public repo, docs, schema, loader, and tests all agree.

This pass is small in scope but important for correctness and maintainability.

---

## Task 1 — Fix scenario root layout in the committed repo

### Goal
Ensure the public repo reflects the documented scenario layout.

### Required action
- Remove `baseline_v1.0.1.yaml` and `baseline_v1.0.2.yaml` from the root of `scenarios/`
- Keep them only in `scenarios/archive/`

### Acceptance criteria
- `scenarios/` root contains only:
  - `baseline_canonical.yaml`
  - `test_baseline_minimal.yaml`
  - `scenario_*.yaml`
  - `README.md`
  - optional `archive/` directory
- public repo tree matches `scenarios/README.md`

---

## Task 2 — Use the committed test fixture directly

### Goal
Make `test_baseline_minimal.yaml` the actual committed fixture used by tests.

### Required action
- Add tests that load `scenarios/test_baseline_minimal.yaml` directly
- Keep temp-file inline fixtures only for malformed-input tests or merge-mechanics tests
- Do not use `baseline_canonical.yaml` in regression tests

### Acceptance criteria
- at least one loader test explicitly uses `test_baseline_minimal.yaml`
- fixture usage is obvious from the test file

---

## Task 3 — Add explicit strict-validation tests

### Goal
Prove strict mode works, not just that it is documented.

### Required tests
Add tests that verify strict validation fails on:
- stale `current_age`
- filename/version mismatch
- enabled modeled death with incomplete death data
- invalid account references
- unsupported scenario-delta structure

### Acceptance criteria
- loader-level strict-validation tests exist
- tests fail without strict-validation handling and pass after it
- strict mode is no longer just a documented path

---

## Task 4 — Reconcile account_rollovers docs vs schema

### Goal
Eliminate README/schema drift.

### Required action
Choose one:
1. Add `strategy.account_rollovers` to the schema, validation, and tests
2. Remove or downgrade the README claim until it is fully supported

### Rule
A feature must not be documented as supported unless:
- schema supports it
- loader accepts it
- engine uses it
- tests cover it

### Acceptance criteria
- README and schema agree on account rollovers

---

## Task 5 — Add a scenario-layout regression test

### Goal
Prevent scenario drift from returning.

### Required test
Add a test that asserts:
- `baseline_canonical.yaml` exists
- `test_baseline_minimal.yaml` exists
- archived baselines are not treated as active root baselines
- scenario root contains only approved active file patterns

### Acceptance criteria
- scenario layout becomes regression-protected

---

## Task 6 — Final README cleanup

### Goal
Ensure README describes only what the current repo actually does.

### Required action
Re-audit README and remove any claim not backed by:
- schema
- loader
- engine
- tests

### Acceptance criteria
- README is truthful and current
- no “planned” or “partial” feature is described as fully supported

---

## Implementation order

1. Task 1 — scenario root cleanup
2. Task 2 — committed test fixture usage
3. Task 3 — strict-validation tests
4. Task 4 — account_rollovers reconciliation
5. Task 5 — scenario-layout regression test
6. Task 6 — final README cleanup

---

## Final instruction

Prefer repo truth over optimistic documentation.

If a feature is only partially implemented:
- do not describe it as complete
- either implement it fully or reduce the claim
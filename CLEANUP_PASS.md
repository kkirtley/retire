# Final Deterministic Annual Engine Alignment Pass

## Objective

Complete the remaining alignment work for the deterministic annual retirement engine.

This pass is focused on:
- repo consistency
- loader / schema / README alignment
- strict-validation usability
- test-fixture discipline
- removal of docs-to-code drift

This is **not** a feature-expansion pass.

---

## In Scope

- scenario-root consistency checks
- README and CLI documentation cleanup
- strict-validation surface polish
- committed test-fixture usage
- schema/docs reconciliation for optional features
- merge-policy clarification
- deterministic regression reinforcement

## Out of Scope

- Monte Carlo
- UI redesign
- new planning features
- new YAML concepts
- broad refactors unrelated to deterministic annual correctness

---

## Mandatory Rules

- Do not invent new YAML fields.
- Do not loosen strict validation.
- Do not add new optional features in this pass.
- Do not let README claim support for behavior not present in schema and code.
- Do not let tests depend on the live household baseline.
- Deterministic annual remains the canonical engine path.

---

# Task 1 — Verify Scenario Root Matches Intended Layout

## Goal
Confirm the committed repo state matches the documented scenario layout.

## Required Checks
- `scenarios/` root should contain only:
  - `baseline_canonical.yaml`
  - `test_baseline_minimal.yaml`
  - `scenario_*.yaml`
  - `README.md`
  - optional `archive/` folder
- Legacy baseline files must not remain in root if they are archived.

## Required Action
- If legacy baselines still exist in root, remove or relocate them.
- If they are already archived, ensure no remaining docs/tests reference them as active root files.

## Acceptance Criteria
- Scenario root layout matches `scenarios/README.md`
- No ambiguity remains about active vs archived baselines

---

# Task 2 — Make Strict Validation a First-Class CLI Workflow

## Goal
Surface strict validation clearly to users and tests.

## Required Changes
- Confirm CLI supports a strict-validation flag end-to-end.
- Document strict-validation usage in `README.md`.

## README must include examples like:
- `retireplan validate scenarios/baseline_canonical.yaml --strict-validation`
- `retireplan run scenarios/baseline_canonical.yaml --strict-validation --out ...`

## Acceptance Criteria
- README documents strict-validation explicitly
- CLI help and docs match actual behavior
- strict-validation is not only an internal loader option

---

# Task 3 — Add Direct Tests for Strict Validation

## Goal
Prove strict mode actually hard-fails where expected.

## Required Tests
Add tests that verify strict mode fails on:
- stale `current_age`
- filename/version mismatch
- death-model enabled with null death year
- invalid references
- unsupported scenario-delta keys

## Acceptance Criteria
- loader-level strict-validation tests exist
- CLI-level strict-validation tests exist if CLI surface supports it
- strict mode behavior is not implicit or untested

---

# Task 4 — Use the Committed Test Fixture Intentionally

## Goal
Make `test_baseline_minimal.yaml` the actual committed fixture, not just a file that exists.

## Required Changes
- Add tests that explicitly load `scenarios/test_baseline_minimal.yaml`
- Keep inline temporary fixtures only where they are testing merge mechanics or malformed inputs
- Do not use `baseline_canonical.yaml` in automated regression tests

## Acceptance Criteria
- committed test fixture is actually used by tests
- test strategy is obvious from repo structure
- real household baseline is not part of test stability

---

# Task 5 — Reconcile README with Schema on Optional Features

## Goal
Eliminate docs-to-schema drift.

## Required Audit
Specifically verify the following documented feature:
- `strategy.account_rollovers`

## Required Action
Choose one:
1. Add `account_rollovers` to schema + validation + code + tests
2. Remove or downgrade the README claim until it is truly supported

## Rule
No feature may be documented as supported unless:
- schema supports it
- loader accepts it
- engine uses it
- tests cover it

## Acceptance Criteria
- README and schema agree
- optional-feature claims are truthful

---

# Task 6 — Clarify Merge Policy in Docs and Code

## Goal
Stop ambiguity around inheritance behavior.

## Current Behavior to Preserve Unless Fully Reworked
- scenario delta files may only define:
  - `metadata`
  - `overrides`
- loader auto-loads sibling `baseline_canonical.yaml`
- object values deep merge
- list values replace entirely

## Required Changes
- Make sure README and `scenarios/README.md` both describe exactly this behavior
- If schema still implies broader merge configurability than code actually supports, either:
  - remove that implication
  - or mark it as future/unsupported

## Acceptance Criteria
- merge policy is described once and consistently
- no “declared but not implemented” merge flexibility remains

---

# Task 7 — Add a Repo Consistency Test for Scenario Layout

## Goal
Prevent scenario-folder drift from returning later.

## Required Test
Add a test that asserts:
- `baseline_canonical.yaml` exists
- `test_baseline_minimal.yaml` exists
- `scenario_*.yaml` files exist or are optional
- archived legacy baselines are not treated as active baselines
- no test depends on archived baseline files

## Acceptance Criteria
- scenario layout becomes regression-protected

---

# Task 8 — Tighten Deterministic Documentation

## Goal
Make deterministic annual behavior explicit and primary.

## Required Changes
Update README and any stage tracker text so they state clearly:
- `run` executes deterministic annual mode by default
- historical analysis is secondary
- scenario inheritance is filename-based and baseline-relative
- strict validation is available and recommended for real household runs

## Acceptance Criteria
- docs reflect actual current architecture
- no stale “maybe” language remains around deterministic path

---

# Task 9 — Regression Audit for Current Deterministic Behavior

## Goal
Lock the current deterministic annual behavior before further changes.

## Required Regression Coverage
Ensure tests cover:
- canonical baseline load
- minimal test baseline load
- scenario delta inheritance
- strict-validation failures
- deterministic `run` path
- bridge-tax-first behavior
- car fund never used
- proration from `2026-07-01`
- retirement transition on `2033-01-01`

## Acceptance Criteria
- deterministic annual path is protected from drift
- cleanup pass leaves repo more stable than before

---

# Implementation Order

1. Task 1 — Verify scenario root layout
2. Task 2 — Document strict validation
3. Task 3 — Add strict-validation tests
4. Task 4 — Use committed test fixture intentionally
5. Task 5 — Reconcile README vs schema for optional features
6. Task 6 — Clarify merge policy
7. Task 7 — Add scenario-layout consistency test
8. Task 8 — Tighten deterministic docs
9. Task 9 — Final regression audit

---

# Deliverables

At the end of this pass, the repo should have:
- fully consistent scenario layout
- strict-validation documented and tested
- committed test fixture actually used
- no README/schema drift on optional features
- one clearly documented merge policy
- stronger deterministic annual regression protection

---

# Final Instruction

Choose **truthful documentation and deterministic correctness** over convenience.

If a feature is only partially supported:
- do not document it as complete
- either implement it fully or downgrade the claim
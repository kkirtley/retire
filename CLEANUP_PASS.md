# Deterministic Annual Engine Cleanup and Alignment Pass

## Objective

Perform a focused cleanup and alignment pass on the retirement-planning repo to make the **deterministic annual engine** coherent, predictable, and safe for continued development.

This pass is about:
- scenario hygiene
- schema/loader/docs alignment
- strict validation wiring
- deterministic execution integrity

This pass is **not** for adding new features.

---

## Scope

### In Scope
- scenario file cleanup and inheritance consistency
- README and `scenarios/README.md` alignment
- AGENTS.md guardrails
- strict validation wiring and tests
- merge-behavior clarification
- schema/docs reconciliation
- deterministic annual regression hardening

### Out of Scope
- Monte Carlo
- UI enhancements
- new scenario concepts
- major package refactors
- new planning features

---

## Mandatory Rules

- Do not invent new YAML fields.
- Do not silently rename YAML fields.
- Do not broaden feature scope.
- Do not weaken strict validation.
- Do not use legacy baseline files as active scenario sources.
- Do not let tests depend on the real household baseline.
- Deterministic annual remains the canonical execution path.

---

# Task 1 — Scenario Directory Hygiene

## Goal
Make the scenario directory unambiguous and safe.

## Required Changes
1. Keep only **one canonical baseline** in the root of `scenarios/`:
   - `baseline_canonical.yaml`

2. Keep only **one minimal test fixture** in the root of `scenarios/`:
   - `test_baseline_minimal.yaml`

3. Move legacy baseline files out of the root:
   - `baseline_v1.0.1.yaml`
   - `baseline_v1.0.2.yaml`

### Move them to:
- `scenarios/archive/`

or rename them clearly as deprecated if archiving is not used.

## Acceptance Criteria
- `scenarios/` root contains one canonical baseline only
- legacy baseline files are not co-located with canonical baseline
- no docs or tests reference archived/deprecated baselines as active files

---

# Task 2 — Enforce Scenario Inheritance Pattern

## Goal
Make scenario variants extend the canonical baseline rather than duplicate it.

## Required Changes
For every `scenario_*.yaml` file:
- ensure it uses the existing inheritance / override mechanism
- ensure it references:
  - `extends: baseline_canonical.yaml`
  if that is the repo’s chosen inheritance syntax

If the current loader uses a different inheritance field name, standardize all scenario files to the actual supported field name.

## Acceptance Criteria
- every `scenario_*.yaml` extends the canonical baseline
- no scenario variant fully duplicates baseline content unless explicitly documented as standalone
- scenario inheritance works in loader tests

---

# Task 3 — Update scenarios/README.md

## Goal
Document scenario roles clearly so humans and Copilot stop drifting.

## Required Content
Document these categories explicitly:

### `baseline_canonical.yaml`
- single source of truth for real household baseline
- deterministic annual compatible
- schema-clean

### `test_baseline_minimal.yaml`
- used only for automated tests
- stable and intentionally small
- not a planning baseline

### `scenario_*.yaml`
- variants / experiments
- should extend canonical baseline unless specifically testing standalone behavior

### `archive/`
- deprecated or historical baseline files
- not to be used in tests or as active baselines

## Acceptance Criteria
- `scenarios/README.md` exists and reflects actual repo behavior
- README examples match actual file names

---

# Task 4 — Update AGENTS.md with Scenario Guardrails

## Goal
Prevent future drift.

## Add These Rules
- Only one canonical baseline is allowed in the `scenarios/` root directory.
- Legacy baselines must be archived or explicitly marked deprecated.
- Tests must never depend on `baseline_canonical.yaml`.
- Scenario variants must extend the canonical baseline unless explicitly designed as standalone tests.
- If there is any conflict between flexibility and deterministic correctness, choose deterministic correctness.

## Acceptance Criteria
- AGENTS.md reflects these rules clearly
- no ambiguity remains around scenario roles

---

# Task 5 — Reconcile README with Actual Repo State

## Goal
Remove doc/code drift.

## Required Changes
Audit README and fix any examples, references, or claims that do not match committed files and actual code behavior.

Specifically verify:
- referenced scenario filenames actually exist
- strict-validation usage is documented if implemented
- deterministic annual is documented as the canonical path
- optional features documented in README are actually supported by schema and code

## Acceptance Criteria
- README file references only real files and real supported behavior
- no unsupported optional feature is documented as if it is fully implemented

---

# Task 6 — Finish Strict Validation Wiring

## Goal
Make strict validation a real surfaced behavior, not just internal plumbing.

## Required Changes
1. Confirm CLI supports a strict-validation flag.
2. Document strict-validation usage in README.
3. Add tests for strict-validation behavior.

## Strict Mode Must Fail On
- unknown / unsupported fields
- stale age inconsistent with DOB and simulation start
- invalid account references
- contribution dates after retirement date
- critical death-model inconsistencies
- scenario inheritance / merge errors

## Acceptance Criteria
- strict-validation is callable from CLI
- README documents it
- tests prove hard-fail behavior

---

# Task 7 — Resolve Merge-Behavior Ambiguity

## Goal
Stop mismatch between declared merge policy and implemented behavior.

## Required Changes
Choose one of these paths and implement/document it clearly:

### Option A (preferred if simplicity is the goal)
- Make merge behavior global and fixed:
  - objects = deep merge
  - lists = replace
- Remove any implication that scenario-defined merge policy changes runtime behavior

### Option B
- Actually honor merge-policy config from schema

If Option B is not fully implemented, do Option A.

## Acceptance Criteria
- schema, loader, tests, and docs all agree on merge behavior
- no “declared but not implemented” merge flexibility remains

---

# Task 8 — Reconcile Schema vs Documented Optional Features

## Goal
Make sure documented features are truly schema-backed and code-backed.

## Required Audit
Check these specifically:
- `account_rollovers`
- advanced QCD fields
- any optional scenario field mentioned in README but absent from schema
- any field supported in schema but not actually consumed by deterministic annual engine

## Required Outcome
For each feature:
- either keep it and ensure schema + loader + engine + tests support it
- or remove/de-document it until properly implemented

## Acceptance Criteria
- no feature is documented as supported unless schema and code both support it
- no schema field remains effectively dead without explanation

---

# Task 9 — Strengthen Deterministic Annual Regression Coverage

## Goal
Protect the deterministic annual engine from future drift.

## Required Tests
Ensure regression coverage includes:
- canonical baseline loads
- test baseline loads
- scenario inheritance works
- retirement transition on `2033-01-01`
- proration from `2026-07-01`
- husband SS starts at 70
- wife SS starts at 65
- conversion taxes source from bridge first
- bridge only funds living when necessary
- Car Fund is never used
- spending floor can drop to `$60,000`
- survivor transition behavior
- QCD satisfies RMD where applicable

## Acceptance Criteria
- deterministic annual regressions run green
- tests do not rely on the real baseline file
- scenario inheritance and strict-validation are both covered

---

# Task 10 — Naming Consistency Pass

## Goal
Reduce scenario-name drift and improve clarity.

## Required Changes
Normalize `scenario_*.yaml` naming to a consistent pattern.

Examples:
- `scenario_high_inflation.yaml`
- `scenario_historical_analysis.yaml`
- `scenario_experimental_analytics.yaml`

Choose a consistent convention and apply it across all scenario files.

## Acceptance Criteria
- scenario filenames follow one naming pattern
- docs use the same pattern

---

# Implementation Order

1. Task 1 — Scenario directory hygiene
2. Task 2 — Scenario inheritance enforcement
3. Task 3 — Update `scenarios/README.md`
4. Task 4 — Update AGENTS.md guardrails
5. Task 5 — README reconciliation
6. Task 6 — Strict validation wiring
7. Task 7 — Merge-behavior clarification
8. Task 8 — Schema/docs feature reconciliation
9. Task 9 — Deterministic regression coverage
10. Task 10 — Naming consistency pass

---

# Deliverables

At the end of this pass, the repo should have:

- one canonical baseline in `scenarios/`
- one minimal committed test fixture
- scenario variants extending canonical baseline
- archived legacy baseline files
- aligned README, `scenarios/README.md`, and AGENTS.md
- strict-validation documented and tested
- merge behavior clearly implemented and documented
- deterministic annual regression suite hardened

---

# Final Instruction

Favor **deterministic correctness over convenience**.

If there is a conflict between:
- flexibility
- backward compatibility
- or strict deterministic behavior

choose strict deterministic behavior.
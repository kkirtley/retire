# Deterministic Stabilization Tracker

This file is the authoritative progress tracker for the deterministic annual engine stabilization work described in `AGENTS.md`.

It replaces the earlier stage-by-stage build tracker so the repo has one persistent source of truth for implementation progress.

Status legend:
- `Not Started`: scoped but not yet being changed in code
- `In Progress`: active implementation or test work is underway
- `Blocked`: cannot proceed without resolving a concrete dependency or ambiguity
- `Complete`: implemented, verified, and aligned with the deterministic contract

## Tracking Rules

- Track progress here at the task level, not the historical build-stage level.
- Prefer small status changes with short factual notes.
- Deterministic correctness wins over flexibility when those goals conflict.
- A task is not `Complete` until code and relevant tests agree.

## Current Focus

- Active now: none
- Next queued: none
- Tracking method: this file is the persistent repo tracker; chat todo state is the short-lived execution queue

## Decision Log

- Canonical baseline source of truth: create a new curated `scenarios/baseline_canonical.yaml` derived from `baseline_v1.0.2.yaml`, removing experimental fields and keeping deterministic plus intentionally supported advanced features.
- Scenario structure: use inheritance through overrides; baseline is the foundation and scenario files are deltas.
- Scenario inheritance is implicit through `scenario_*.yaml` plus `overrides`; there is no supported `extends` field.
- Merge semantics: enforce globally in code; objects deep-merge and lists replace. Ignore YAML-defined merge rules for now.
- Strict validation: CLI `--strict-validation` overrides scenario settings and forces strict behavior.
- Strict validation failures: fail on structural and logical issues, including unknown fields, invalid references, bad dates, stale `current_age`, version mismatch, and inconsistent modeling assumptions.
- Unknown fields: reject all unknown fields in strict mode.
- Execution order: the order defined in `AGENTS.md` is the runtime contract and code must be refactored to match it.
- Age semantics: use attained age during the year based on actual birthday timing.
- Bridge age anchor: use husband's age only.
- Restricted accounts: defined only by `restriction: "never_use_for_retirement_model_cashflows"` in YAML.
- Mortgage proration: use full prorated interest, principal, and payoff timing.
- Output contract: align internal projection result, CLI JSON output, and reporting export.
- Regression scope: deterministic annual is required; historical analysis remains secondary.

## Task Status

| Task | Status   | Scope                     | Notes                                                                                                                                                                                                                                                                |
| ---- | -------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Complete | Scenario separation       | Added `baseline_canonical.yaml`, `test_baseline_minimal.yaml`, scenario delta files, and `scenarios/README.md`. Focused tests now use the standalone test baseline rather than the live household baseline.                                                          |
| 2    | Complete | Deterministic engine mode | CLI `run` now explicitly reports and emits `execution_mode: deterministic_annual`, executes the deterministic annual projection as the primary path, and only appends historical analysis when a scenario opts into it.                                              |
| 3    | Complete | Merge behavior            | Loader now enforces global object deep-merge and list replacement for scenario inheritance, with tests covering both behaviors.                                                                                                                                      |
| 4    | Complete | Strict validation mode    | Added CLI `--strict-validation` override and promoted loader diagnostics like stale ages, filename/version mismatch, and incomplete modeled death data to hard failures in strict mode.                                                                              |
| 5    | Complete | Execution order contract  | Projection orchestration now records and enforces the runtime step contract, `docs/execution_order.md` defines the order, and focused projection tests verify the sequence.                                                                                          |
| 6    | Complete | Field classification      | Canonical baseline no longer carries experimental analytics tracking; core analytics outputs now default in schema, and a dedicated scenario delta preserves experimental analytics as opt-in behavior.                                                              |
| 7    | Complete | Account integrity         | Loader now rejects missing account references, invalid destinations, missing required bridge accounts, invalid QCD owner IRA paths, and restricted-account use in retirement cashflow sources.                                                                       |
| 8    | Complete | Age and date semantics    | DOB-derived milestone dates now drive SS, Medicare, QCD eligibility, proration, and `current_age` is treated as informational loader data rather than execution input.                                                                                               |
| 9    | Complete | Bridge account behavior   | Deficit settlement now preserves the bridge for pre-70 conversion-tax funding before falling back to it for living expenses, while post-70 years treat the bridge as a normal liquidity bucket again.                                                                |
| 10   | Complete | Mortgage logic            | Mortgage schedules now separate standard amortized payments from computed extra principal for payoff targets, derive payoff targets from date or husband's age, and keep annual interest, principal, and payoff timing deterministic.                                |
| 11   | Complete | Output contract           | Projection results now publish a canonical `output_contract`, and the CLI plus reporting export expose the same required ledger, per-year, and summary outputs without breaking legacy summary consumers.                                                            |
| 12   | Complete | Regression suite          | Added explicit regressions for retirement transition, Car Fund non-usage, analytics defaults, bridge rules, SS timing, survivor logic, QCD behavior, mortgage/output/reporting flows, repo scenario deltas, and deterministic resource-pressure spending guardrails. |

## Work Log

- 2026-04-20: Replaced the old stage tracker with this stabilization tracker to avoid split progress state.
- 2026-04-20: Locked implementation decisions for baseline curation, inheritance, merge semantics, strict validation, age semantics, bridge rules, mortgage proration, and output alignment.
- 2026-04-20: Completed Task 1 by separating canonical, test, and scenario-delta YAML files and documenting the scenario layout.
- 2026-04-20: Completed Task 3 by making scenario delta inheritance use global object deep-merge and list replacement semantics in code, with focused regression coverage.
- 2026-04-20: Added repo-level Task 3 coverage for real scenario delta files and the orphan-delta failure path; focused loader and CLI tests are green.
- 2026-04-20: Completed Task 4 by wiring loader-level strict warning escalation and CLI `--strict-validation` support for `validate` and `run`, with focused loader and CLI regression coverage.
- 2026-04-20: Completed Task 5 by making the projection execution phases explicit in code, documenting the contract in `docs/execution_order.md`, and adding a runtime sequence test for the yearly orchestration order.
- 2026-04-20: Completed Task 8 by replacing year-only age gates with DOB-plus-birth-month milestone dates for Social Security, Medicare, QCD timing, and first-year proration, while making `current_age` informational-only and updating focused regressions to the new deterministic outputs.
- 2026-04-21: Completed Task 7 by tightening loader-side account integrity checks for required bridge-account references, QCD depletion-owner validation, and restricted retirement cashflow sources, with focused loader and CLI validation tests green.
- 2026-04-21: Completed Task 9 by deferring pre-70 bridge withdrawals for living-expense deficits until non-bridge sources are exhausted, keeping conversion-tax funding first, restoring bridge-first liquidity behavior after age 70, and validating the change with 89 passing deterministic regression tests.
- 2026-04-21: Completed Task 10 by separating scheduled mortgage amortization from computed extra principal, supporting explicit target dates and husband-age-derived payoff targets, and validating the updated mortgage, projection, reporting, and UI outputs with 90 passing deterministic regression tests.
- 2026-04-21: Completed Task 11 by adding a canonical `output_contract` to projection results, surfacing the same contract through CLI JSON and reporting exports, and validating the contract with focused projection/reporting/CLI tests plus a full 90-test regression pass.
- 2026-04-21: Completed Task 12 by adding focused deterministic regressions for retirement transition, Car Fund non-usage, analytics defaults, the experimental-analytics scenario delta, and deterministic resource-pressure spending guardrails, then validating the full suite with `make pre`.
- 2026-04-21: Completed Task 6 by defaulting core analytics outputs in schema, removing experimental analytics tracking from the canonical baseline and test fixture, and preserving those experimental fields in `scenario_experimental_analytics.yaml` as an opt-in variant.
- 2026-04-21: Completed Task 2 by making `deterministic_annual` the explicit CLI execution mode, surfacing it in the run payload and console output, gating historical analysis behind scenario opt-in, and updating README wording to document the deterministic-first execution path.
- 2026-04-21: Closed the remaining spending-guardrail gap by making `resource_pressure` reduce base living expenses toward the configured floor during yearly cashflow settlement before declaring failure, with focused projection coverage.
- 2026-04-21: Completed the cleanup alignment pass by archiving legacy baseline YAMLs under `scenarios/archive/`, switching the Makefile default scenario to `baseline_canonical.yaml`, documenting implicit scenario inheritance and fixed merge semantics, adding AGENTS guardrails for scenario roles, and extending strict-validation and scenario-hygiene regression coverage.
# Scenario Layout

This directory now has three distinct scenario roles:

- `baseline_canonical.yaml`: curated source of truth for deterministic annual planning
- `test_baseline_minimal.yaml`: stable standalone scenario for tests and fixture-style validation
- `scenario_*.yaml`: scenario deltas that inherit from `baseline_canonical.yaml`
- `archive/`: deprecated or historical baselines that are not active scenario sources

## Rules

- `baseline_canonical.yaml` is a full scenario document.
- `test_baseline_minimal.yaml` is also a full scenario document.
- `scenario_*.yaml` files are not full standalone scenarios. They may define only:
  - `metadata`
  - `overrides`
- Scenario inheritance is implicit by filename pattern and sibling location. There is no supported `extends` field.
- The loader automatically merges `overrides` from a `scenario_*.yaml` file onto the sibling `baseline_canonical.yaml`.
- Merge behavior is global and fixed in code:
  - objects deep-merge
  - lists replace the baseline list entirely
- `validation.override_merge_rules` remains schema data for compatibility, but it does not change runtime merge behavior.
- Files in `archive/` are historical only. Tests and active docs must not use them as current baselines.

## Why This Layout Exists

- The household baseline remains curated and deterministic.
- Tests do not depend on the live household baseline.
- Scenario variants stay small and avoid copy-paste drift.
- Deprecated baselines stay available for reference without being mistaken for active scenarios.

## Current Files

- `baseline_canonical.yaml`: canonical deterministic baseline
- `test_baseline_minimal.yaml`: stable test fixture scenario
- `scenario_high_inflation.yaml`: inflation stress delta
- `scenario_historical_analysis.yaml`: historical-analysis opt-in delta
- `scenario_experimental_analytics.yaml`: experimental analytics opt-in delta
- `archive/baseline_v1.0.1.yaml`: archived legacy baseline
- `archive/baseline_v1.0.2.yaml`: archived legacy baseline
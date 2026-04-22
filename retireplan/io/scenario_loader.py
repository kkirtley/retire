"""Load and validate retirement scenarios from YAML files."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from retireplan.scenario import RetirementScenario

_CANONICAL_BASELINE_FILENAME = "baseline_canonical.yaml"
_SCENARIO_DELTA_PREFIX = "scenario_"
_VERSION_SUFFIX_PATTERN = re.compile(r"_v(?P<version>\d+\.\d+\.\d+)$")


@dataclass(frozen=True)
class ScenarioLoadResult:
    path: Path
    scenario: RetirementScenario
    warnings: list[str]


def load_scenario(
    path: str | Path,
    strict_validation: bool | None = None,
) -> ScenarioLoadResult:
    """Load a YAML scenario file, validate it, and return non-fatal diagnostics."""

    scenario_path = Path(path).expanduser().resolve()
    with scenario_path.open("r", encoding="utf-8") as handle:
        text = handle.read()

    return load_scenario_text(
        text,
        path_hint=scenario_path,
        strict_validation=strict_validation,
    )


def load_scenario_text(
    text: str,
    path_hint: str | Path | None = None,
    strict_validation: bool | None = None,
) -> ScenarioLoadResult:
    """Load a scenario from raw YAML text using the standard validation pipeline."""

    payload = yaml.safe_load(text)
    return load_scenario_payload(
        payload,
        path_hint=path_hint,
        strict_validation=strict_validation,
    )


def load_scenario_payload(
    payload: Any,
    path_hint: str | Path | None = None,
    strict_validation: bool | None = None,
) -> ScenarioLoadResult:
    """Validate an already-parsed scenario payload and return diagnostics."""

    if not isinstance(payload, dict):
        raise ValueError("scenario YAML must contain a mapping at the document root")

    scenario_path = _normalize_path_hint(path_hint)
    payload = _resolve_scenario_inheritance(payload, scenario_path)
    payload = _apply_shared_defaults(payload)

    scenario = RetirementScenario.model_validate(payload)
    warnings = _build_warnings(scenario_path, scenario)
    _raise_for_strict_validation_warnings(
        warnings,
        scenario_path=scenario_path,
        scenario=scenario,
        strict_validation=strict_validation,
    )
    return ScenarioLoadResult(path=scenario_path, scenario=scenario, warnings=warnings)


def _normalize_path_hint(path_hint: str | Path | None) -> Path:
    if path_hint is None:
        return Path("untitled_scenario.yaml")
    return Path(path_hint).expanduser().resolve()


def _resolve_scenario_inheritance(payload: dict, scenario_path: Path) -> dict:
    if not scenario_path.stem.startswith(_SCENARIO_DELTA_PREFIX):
        return deepcopy(payload)

    unsupported_keys = set(payload) - {"metadata", "overrides"}
    if unsupported_keys:
        unsupported = ", ".join(sorted(unsupported_keys))
        raise ValueError(
            f"scenario delta files may only define metadata and overrides; found: {unsupported}"
        )

    base_path = scenario_path.parent / _CANONICAL_BASELINE_FILENAME
    if not base_path.exists():
        raise ValueError(
            f"scenario delta file requires sibling {_CANONICAL_BASELINE_FILENAME}: {scenario_path.name}"
        )

    base_payload = _load_yaml_mapping(base_path)
    overrides = deepcopy(payload.get("overrides", {}))
    if not isinstance(overrides, dict):
        raise ValueError("scenario overrides must be a mapping")

    merged = _deep_merge(base_payload, overrides)

    metadata_override = deepcopy(payload.get("metadata", {}))
    if metadata_override:
        if not isinstance(metadata_override, dict):
            raise ValueError("scenario metadata override must be a mapping")
        merged["metadata"] = _deep_merge(base_payload.get("metadata", {}), metadata_override)

    merged["overrides"] = overrides
    return merged


def _load_yaml_mapping(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if payload is None:
        raise ValueError(f"scenario YAML must contain a mapping at the document root: {path}")
    if not isinstance(payload, dict):
        raise ValueError(f"scenario YAML must contain a mapping at the document root: {path}")
    return payload


def _apply_shared_defaults(payload: dict) -> dict:
    defaults_path = files("retireplan").joinpath("defaults/policy_defaults.yaml")
    with defaults_path.open("r", encoding="utf-8") as handle:
        defaults = yaml.safe_load(handle)

    if defaults is None:
        return payload
    if not isinstance(defaults, dict):
        raise ValueError("shared defaults YAML must contain a mapping at the document root")
    return _deep_merge(defaults, payload)


def _deep_merge(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _build_warnings(path: Path, scenario: RetirementScenario) -> list[str]:
    warnings: list[str] = []

    suffix_match = _VERSION_SUFFIX_PATTERN.search(path.stem)
    if suffix_match and suffix_match.group("version") != scenario.metadata.version:
        warnings.append(
            "Scenario filename version does not match metadata.version: "
            f"{path.name} vs {scenario.metadata.version}."
        )

    for role, person in (
        ("husband", scenario.household.husband),
        ("wife", scenario.household.wife),
    ):
        expected_ages = _expected_current_age_values(
            person.birth_year, person.birth_month, scenario.simulation.start_date
        )
        if person.current_age not in expected_ages:
            warnings.append(
                f"household.{role}.current_age={person.current_age} is inconsistent with "
                f"birth_year={person.birth_year}, birth_month={person.birth_month}, "
                f"and simulation.start_date={scenario.simulation.start_date}."
            )
        if person.modeled_death.enabled and person.modeled_death.death_year is None:
            warnings.append(
                f"household.{role}.modeled_death is enabled but death_year is null; "
                "survivor transitions will not activate until a death year is supplied."
            )

    return warnings


def _raise_for_strict_validation_warnings(
    warnings: list[str],
    *,
    scenario_path: Path,
    scenario: RetirementScenario,
    strict_validation: bool | None,
) -> None:
    if not warnings:
        return

    strict_enabled = scenario.validation.strict if strict_validation is None else strict_validation
    if not strict_enabled:
        return

    formatted_warnings = "\n".join(f"- {warning}" for warning in warnings)
    raise ValueError(
        "Strict validation failed for "
        f"{scenario_path.name} ({scenario.metadata.scenario_name} v{scenario.metadata.version}):\n"
        f"{formatted_warnings}"
    )


def _expected_current_age_values(birth_year: int, birth_month: int, start_date: date) -> set[int]:
    younger_age = start_date.year - birth_year - 1
    older_age = start_date.year - birth_year
    if start_date.month < birth_month:
        return {younger_age}
    if start_date.month > birth_month:
        return {older_age}
    return {younger_age, older_age}

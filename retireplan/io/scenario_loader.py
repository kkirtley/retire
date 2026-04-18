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

_VERSION_SUFFIX_PATTERN = re.compile(r"_v(?P<version>\d+\.\d+\.\d+)$")


@dataclass(frozen=True)
class ScenarioLoadResult:
    path: Path
    scenario: RetirementScenario
    warnings: list[str]


def load_scenario(path: str | Path) -> ScenarioLoadResult:
    """Load a YAML scenario file, validate it, and return non-fatal diagnostics."""

    scenario_path = Path(path).expanduser().resolve()
    with scenario_path.open("r", encoding="utf-8") as handle:
        text = handle.read()

    return load_scenario_text(text, path_hint=scenario_path)


def load_scenario_text(text: str, path_hint: str | Path | None = None) -> ScenarioLoadResult:
    """Load a scenario from raw YAML text using the standard validation pipeline."""

    payload = yaml.safe_load(text)
    return load_scenario_payload(payload, path_hint=path_hint)


def load_scenario_payload(
    payload: Any,
    path_hint: str | Path | None = None,
) -> ScenarioLoadResult:
    """Validate an already-parsed scenario payload and return diagnostics."""

    if not isinstance(payload, dict):
        raise ValueError("scenario YAML must contain a mapping at the document root")

    payload = _apply_shared_defaults(payload)

    scenario = RetirementScenario.model_validate(payload)
    scenario_path = _normalize_path_hint(path_hint)
    warnings = _build_warnings(scenario_path, scenario)
    return ScenarioLoadResult(path=scenario_path, scenario=scenario, warnings=warnings)


def _normalize_path_hint(path_hint: str | Path | None) -> Path:
    if path_hint is None:
        return Path("untitled_scenario.yaml")
    return Path(path_hint).expanduser().resolve()


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


def _expected_current_age_values(birth_year: int, birth_month: int, start_date: date) -> set[int]:
    younger_age = start_date.year - birth_year - 1
    older_age = start_date.year - birth_year
    if start_date.month < birth_month:
        return {younger_age}
    if start_date.month > birth_month:
        return {older_age}
    return {younger_age, older_age}

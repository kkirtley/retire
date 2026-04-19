"""Shared test fixtures owned by the test suite, not by live scenario data."""

from pathlib import Path

import pytest
import yaml

from retireplan.io import load_scenario

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TEST_SCENARIO_PATH = FIXTURES_DIR / "golden_baseline_v1.0.1.yaml"


@pytest.fixture
def golden_scenario_path() -> Path:
    return TEST_SCENARIO_PATH


@pytest.fixture
def golden_loaded(golden_scenario_path: Path):
    return load_scenario(golden_scenario_path)


@pytest.fixture
def golden_scenario(golden_loaded):
    return golden_loaded.scenario


@pytest.fixture
def golden_payload(golden_scenario_path: Path) -> dict:
    return yaml.safe_load(golden_scenario_path.read_text(encoding="utf-8"))

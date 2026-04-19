import json
from copy import deepcopy

import pytest
import yaml
from typer.testing import CliRunner

from retireplan.cli.main import app
from retireplan.core import analyze_historical_cohorts, build_timeline, project_scenario
from retireplan.core.market_history import account_type_return_for_period
from retireplan.core.strategy import _apply_market_adjustments
from retireplan.io import load_scenario_text
from retireplan.reporting import build_reporting_bundle
from retireplan.scenario import AccountType, MarketAdjustmentBand

runner = CliRunner()


def test_historical_account_type_return_uses_glide_path_for_actual_history(golden_scenario):
    scenario = golden_scenario
    scenario.historical_analysis.enabled = True
    scenario.historical_analysis.selected_start_year = 2008

    period = build_timeline(scenario)[0]
    annual_return = account_type_return_for_period(AccountType.TRADITIONAL_IRA, period, scenario)

    assert annual_return == pytest.approx(-0.2049, abs=0.0001)


def test_banded_conversion_policy_uses_account_type_market_signal(golden_scenario):
    scenario = golden_scenario
    scenario.historical_analysis.enabled = True
    scenario.historical_analysis.selected_start_year = 2008
    scenario.strategy.roth_conversions.market_adjustments.enabled = True
    scenario.strategy.roth_conversions.market_adjustments.rules = []
    scenario.strategy.roth_conversions.market_adjustments.signal_account_type = "traditional_ira"
    scenario.strategy.roth_conversions.market_adjustments.bands = [
        MarketAdjustmentBand(upper_return=-0.10, multiplier=1.25),
        MarketAdjustmentBand(lower_return=-0.10, upper_return=0.10, multiplier=1.0),
        MarketAdjustmentBand(lower_return=0.10, multiplier=0.80),
    ]

    period = build_timeline(scenario)[0]

    assert _apply_market_adjustments(scenario, period, 100000.0) == pytest.approx(125000.0)


def test_market_adjustment_bands_allow_touching_thresholds(golden_payload):
    payload = deepcopy(golden_payload)
    payload["historical_analysis"] = {
        "enabled": True,
        "selected_start_year": 2008,
    }
    payload["strategy"]["roth_conversions"]["market_adjustments"] = {
        "enabled": True,
        "signal_account_type": "traditional_ira",
        "rules": [],
        "bands": [
            {"upper_return": -0.15, "multiplier": 1.25},
            {"lower_return": -0.15, "upper_return": 0.12, "multiplier": 1.0},
            {"lower_return": 0.12, "multiplier": 0.85},
        ],
    }

    scenario = load_scenario_text(yaml.safe_dump(payload, sort_keys=False)).scenario
    period = build_timeline(scenario)[0]

    assert _apply_market_adjustments(scenario, period, 100000.0) == pytest.approx(125000.0)


def test_historical_cohort_analysis_uses_modern_weighting_and_reports_cohorts(golden_payload):
    payload = deepcopy(golden_payload)
    payload["historical_analysis"] = {
        "enabled": True,
        "weighting": {
            "method": "modern_heavier",
            "modern_start_year": 1990,
            "modern_weight_multiplier": 3.0,
        },
    }
    scenario = load_scenario_text(yaml.safe_dump(payload, sort_keys=False)).scenario

    analysis = analyze_historical_cohorts(scenario)

    assert analysis is not None
    assert analysis.cohort_count == 25
    assert analysis.projection_years == 32
    assert analysis.cohorts[0].start_year == 1970
    assert analysis.cohorts[0].weight == 1.0
    assert analysis.cohorts[-1].start_year == 1994
    assert analysis.cohorts[-1].weight == 3.0
    assert 0.0 <= analysis.weighted_success_rate <= 1.0
    assert analysis.target_success_rate == 0.9


def test_reporting_and_cli_include_historical_analysis_when_enabled(tmp_path, golden_payload):
    payload = deepcopy(golden_payload)
    payload["historical_analysis"] = {"enabled": True}
    scenario_path = tmp_path / "historical.yaml"
    scenario_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    loaded = load_scenario_text(yaml.safe_dump(payload, sort_keys=False), path_hint=scenario_path)
    analysis = analyze_historical_cohorts(loaded.scenario, loaded.warnings)
    projection = project_scenario(loaded.scenario, loaded.warnings)
    reporting = build_reporting_bundle(projection, loaded.scenario, analysis)

    assert analysis is not None
    assert "historical_cohorts" in reporting["tables"]
    assert "historical_terminal_net_worth" in reporting["charts"]

    output_path = tmp_path / "run.json"
    charts_path = tmp_path / "charts"
    result = runner.invoke(
        app,
        ["run", str(scenario_path), "--out", str(output_path), "--charts", str(charts_path)],
    )

    assert result.exit_code == 0
    payload_out = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload_out["historical_analysis"] is not None
    assert payload_out["historical_analysis"]["cohort_count"] == 25
    assert "historical_cohorts" in payload_out["reporting"]["tables"]

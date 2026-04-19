import pytest
import yaml

from retireplan.core import build_timeline, project_scenario
from retireplan.core.expenses import build_expenses
from retireplan.io import load_scenario, load_scenario_text


def test_base_living_adjustment_applies_with_own_year_window_and_inflation(golden_payload):
    payload = golden_payload
    payload["expenses"]["base_living"]["adjustments"] = [
        {"start_year": 2033, "end_year": 2034, "amount_annual": 50000.0}
    ]
    scenario = load_scenario_text(yaml.safe_dump(payload, sort_keys=False)).scenario

    periods = {period.year: period for period in build_timeline(scenario)}

    expenses_2032 = build_expenses(scenario, periods[2032])
    expenses_2033 = build_expenses(scenario, periods[2033])
    expenses_2034 = build_expenses(scenario, periods[2034])
    expenses_2035 = build_expenses(scenario, periods[2035])

    assert expenses_2032["base_living"] == 81178.54
    assert expenses_2033["base_living"] == 50000.0
    assert expenses_2034["base_living"] == 51250.0
    assert expenses_2035["base_living"] == 87420.41


def test_projection_uses_base_living_adjustment_for_retirement_year_gap(golden_payload):
    payload = golden_payload
    payload["expenses"]["base_living"]["adjustments"] = [
        {"start_year": 2033, "end_year": 2036, "amount_annual": 60000.0}
    ]
    scenario = load_scenario_text(yaml.safe_dump(payload, sort_keys=False)).scenario

    result = project_scenario(scenario)
    row_2033 = next(row for row in result.ledger if row.year == 2033)

    assert row_2033.expenses["base_living"] == 60000.0
    assert row_2033.withdrawals["Taxable Bridge Account"] < 48226.01


def test_loader_rejects_overlapping_expense_adjustments(tmp_path, golden_payload):
    payload = golden_payload
    payload["expenses"]["base_living"]["adjustments"] = [
        {"start_year": 2033, "end_year": 2035, "amount_annual": 50000.0},
        {"start_year": 2035, "end_year": 2037, "amount_annual": 55000.0},
    ]

    temp_path = tmp_path / "overlapping-expense-adjustments.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="expense adjustments may not overlap"):
        load_scenario(temp_path)


def test_loader_accepts_travel_adjustment_with_custom_inflation(golden_payload):
    payload = golden_payload
    payload["expenses"]["travel"]["adjustments"] = [
        {
            "start_year": 2033,
            "end_year": 2034,
            "amount_annual": 3000.0,
            "inflation_rate": 0.10,
        }
    ]

    loaded = load_scenario_text(yaml.safe_dump(payload, sort_keys=False))
    periods = {period.year: period for period in build_timeline(loaded.scenario)}
    expenses_2033 = build_expenses(loaded.scenario, periods[2033])
    expenses_2034 = build_expenses(loaded.scenario, periods[2034])

    assert expenses_2033["travel"] == 3000.0
    assert expenses_2034["travel"] == 3300.0

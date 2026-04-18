from pathlib import Path

from retireplan.core import project_scenario
from retireplan.io import load_scenario


def test_projection_runs_with_rich_scenario_shape():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)

    result = project_scenario(loaded.scenario, loaded.warnings)

    assert result.ledger
    assert result.ledger[0].year == 2026
    assert result.ledger[-1].wife_age == 100
    assert "earned_income_husband" in result.ledger[0].income
    assert "federal" in result.ledger[0].taxes
    assert "state" in result.ledger[0].taxes
    assert "mortgage_payment" in result.ledger[0].expenses
    assert result.ledger[0].income["earned_income_husband"] < 195000.0
    assert result.ledger[0].expenses["base_living"] < 120000.0
    assert any("Stage 3 tax modeling" in warning for warning in result.warnings)


def test_projection_matches_stage_3_baseline_checkpoints():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)

    result = project_scenario(loaded.scenario, loaded.warnings)
    rows = {row.year: row for row in result.ledger}

    first_year = rows[2026]
    retirement_year = rows[2033]
    failure_year = rows[2059]

    assert first_year.taxes == {"federal": 12698.66, "state": 4015.21, "total": 16713.87}
    assert first_year.net_cash_flow == 0.0
    assert first_year.withdrawals == {"Taxable Bridge Account": 4146.0}
    assert first_year.liquid_resources_end == 777499.64
    assert first_year.account_balances_end["Taxable Bridge Account"] == 20354.5

    assert retirement_year.taxes == {"federal": 0.0, "state": 0.0, "total": 0.0}
    assert retirement_year.net_cash_flow == 0.0 or retirement_year.net_cash_flow == -0.0
    assert retirement_year.withdrawals == {"Taxable Bridge Account": 146972.77}
    assert retirement_year.liquid_resources_end == 1307760.93

    assert failure_year.year == 2059
    assert failure_year.taxes == {"federal": 0.0, "state": 0.0, "total": 0.0}
    assert failure_year.withdrawals == {"Wife Roth IRA": 27168.01}
    assert failure_year.net_cash_flow == -36785.17
    assert failure_year.liquid_resources_end == 0.0
    assert result.failure_year == 2059
    assert result.success is False

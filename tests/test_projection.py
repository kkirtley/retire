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
    assert "mortgage_payment" in result.ledger[0].expenses
    assert result.ledger[0].income["earned_income_husband"] < 195000.0
    assert result.ledger[0].expenses["base_living"] < 120000.0
    assert any("Stage 2" in warning for warning in result.warnings)


def test_projection_matches_stage_2_baseline_checkpoints():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)

    result = project_scenario(loaded.scenario, loaded.warnings)
    rows = {row.year: row for row in result.ledger}

    first_year = rows[2026]
    retirement_year = rows[2033]
    final_year = rows[result.ledger[-1].year]

    assert first_year.net_cash_flow == 12567.87
    assert first_year.liquid_resources_end == 794466.28
    assert first_year.account_balances_end["Taxable Bridge Account"] == 37321.14

    assert retirement_year.net_cash_flow == 0.0
    assert retirement_year.withdrawals == {"Taxable Bridge Account": 146972.77}
    assert retirement_year.liquid_resources_end == 1716469.38

    assert final_year.year == 2067
    assert final_year.withdrawals == {"Husband Roth IRA": 84488.34}
    assert final_year.liquid_resources_end == 2195200.7
    assert result.failure_year is None
    assert result.success is True

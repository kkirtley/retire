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
    assert "remaining_balance" in result.ledger[0].mortgage
    assert result.ledger[0].income["earned_income_husband"] < 195000.0
    assert result.ledger[0].expenses["base_living"] < 120000.0
    assert any(
        "Stage 5 income, survivor, mortgage, and tax modeling" in warning
        for warning in result.warnings
    )


def test_projection_matches_stage_4_baseline_checkpoints():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)

    result = project_scenario(loaded.scenario, loaded.warnings)
    rows = {row.year: row for row in result.ledger}

    first_year = rows[2026]
    retirement_year = rows[2033]
    payoff_year = rows[2032]
    final_year = rows[result.ledger[-1].year]

    assert first_year.taxes == {"federal": 12698.66, "state": 4015.21, "total": 16713.87}
    assert first_year.net_cash_flow == 0.0 or first_year.net_cash_flow == -0.0
    assert first_year.withdrawals == {"Taxable Bridge Account": 13777.2}
    assert first_year.mortgage == {
        "scheduled_payment": 34200.0,
        "extra_principal": 9912.3,
        "total_payment": 44112.3,
        "interest": 12009.11,
        "principal": 32103.18,
        "remaining_balance": 417896.82,
    }
    assert first_year.expenses["mortgage_payment"] == 44112.3
    assert first_year.liquid_resources_end == 767722.79

    assert payoff_year.taxes == {"federal": 53065.49, "state": 11044.25, "total": 64109.74}
    assert payoff_year.mortgage == {
        "scheduled_payment": 34200.0,
        "extra_principal": 9912.3,
        "total_payment": 44112.3,
        "interest": 699.07,
        "principal": 43413.22,
        "remaining_balance": 0.0,
    }
    assert payoff_year.expenses["mortgage_payment"] == 44112.3
    assert payoff_year.net_cash_flow == 19309.31

    assert retirement_year.mortgage == {
        "scheduled_payment": 0.0,
        "extra_principal": 0.0,
        "total_payment": 0.0,
        "interest": 0.0,
        "principal": 0.0,
        "remaining_balance": 0.0,
    }
    assert retirement_year.expenses["mortgage_payment"] == 0.0
    assert retirement_year.net_cash_flow == 0.0
    assert retirement_year.withdrawals == {"Taxable Bridge Account": 78572.77}
    assert retirement_year.liquid_resources_end == 1276944.37

    assert final_year.year == 2067
    assert final_year.taxes == {"federal": 683.17, "state": 273.27, "total": 956.44}
    assert final_year.mortgage["remaining_balance"] == 0.0
    assert final_year.withdrawals == {"Husband Roth IRA": 85444.78}
    assert final_year.net_cash_flow == 0.0
    assert final_year.liquid_resources_end == 1233082.12
    assert result.failure_year is None
    assert result.success is True

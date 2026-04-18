from pathlib import Path

from retireplan.core import project_scenario
from retireplan.io import load_scenario


def test_projection_runs_with_rich_scenario_shape():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)

    result = project_scenario(loaded.scenario, loaded.warnings)

    assert result.ledger
    assert result.summary["total_taxes_paid"] > 0.0
    assert result.summary["failure_year_if_any"] is None
    assert result.ledger[0].year == 2026
    assert result.ledger[-1].wife_age == 100
    assert "earned_income_husband" in result.ledger[0].income
    assert "federal" in result.ledger[0].taxes
    assert "state" in result.ledger[0].taxes
    assert "total" in result.ledger[0].medicare
    assert "roth_conversion_total" in result.ledger[0].strategy
    assert "mortgage_payment" in result.ledger[0].expenses
    assert "remaining_balance" in result.ledger[0].mortgage
    assert result.ledger[0].income["earned_income_husband"] < 195000.0
    assert result.ledger[0].expenses["base_living"] < 120000.0
    assert any("Stage 8 engine reporting outputs" in warning for warning in result.warnings)


def test_projection_matches_stage_7_baseline_checkpoints():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    loaded = load_scenario(scenario_path)

    result = project_scenario(loaded.scenario, loaded.warnings)
    rows = {row.year: row for row in result.ledger}

    first_year = rows[2026]
    retirement_year = rows[2033]
    payoff_year = rows[2032]
    final_year = rows[result.ledger[-1].year]

    assert first_year.medicare == {
        "part_b_base": 0.0,
        "part_d_base": 0.0,
        "irmaa_part_b": 0.0,
        "irmaa_part_d": 0.0,
        "total": 0.0,
        "covered_people": 0.0,
        "irmaa_tier": 0.0,
    }
    assert first_year.taxes == {"federal": 12698.66, "state": 4015.21, "total": 16713.87}
    assert first_year.strategy == {
        "roth_conversion_total": 0.0,
        "conversion_tax_impact": 0.0,
        "conversion_tax_payment": 0.0,
        "conversion_tax_shortfall": 0.0,
        "rmd_total": 0.0,
        "qcd_total": 0.0,
        "taxable_rmd_total": 0.0,
        "charitable_giving_total": 0.0,
        "taxable_giving": 0.0,
    }
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

    assert payoff_year.medicare["covered_people"] == 2.0
    assert payoff_year.medicare == {
        "part_b_base": 4192.8,
        "part_d_base": 832.8,
        "irmaa_part_b": 4192.8,
        "irmaa_part_d": 756.0,
        "total": 9974.4,
        "covered_people": 2.0,
        "irmaa_tier": 2.0,
    }
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
    assert payoff_year.expenses["medicare_part_b"] > 0.0
    assert payoff_year.expenses["medicare_part_d"] > 0.0
    assert payoff_year.strategy == {
        "roth_conversion_total": 0.0,
        "conversion_tax_impact": 0.0,
        "conversion_tax_payment": 0.0,
        "conversion_tax_shortfall": 0.0,
        "rmd_total": 0.0,
        "qcd_total": 0.0,
        "taxable_rmd_total": 0.0,
        "charitable_giving_total": 0.0,
        "taxable_giving": 0.0,
    }
    assert payoff_year.alerts == (
        "IRMAA tier changed from 0 to 2 based on 2030 MAGI.",
        "Skipped 7949.89 of charitable giving because QCD-eligible IRA capacity was insufficient.",
        "Reduced Roth conversion from 175000.00 to 0.00 because of tax or IRMAA guardrails.",
    )
    assert payoff_year.net_cash_flow == 9334.91
    assert payoff_year.liquid_resources_end == 1285120.09

    assert retirement_year.medicare == {
        "part_b_base": 4192.8,
        "part_d_base": 832.8,
        "irmaa_part_b": 4192.8,
        "irmaa_part_d": 756.0,
        "total": 9974.4,
        "covered_people": 2.0,
        "irmaa_tier": 2.0,
    }
    assert retirement_year.strategy == {
        "roth_conversion_total": 162500.0,
        "conversion_tax_impact": 35132.96,
        "conversion_tax_payment": 30067.61,
        "conversion_tax_shortfall": 0.0,
        "rmd_total": 0.0,
        "qcd_total": 0.0,
        "taxable_rmd_total": 0.0,
        "charitable_giving_total": 0.0,
        "taxable_giving": 0.0,
    }
    assert retirement_year.taxes == {"federal": 28284.04, "state": 6848.92, "total": 35132.96}
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
    assert retirement_year.withdrawals == {
        "Taxable Bridge Account": 104180.87,
        "Husband Traditional IRA": 19499.26,
    }
    assert retirement_year.liquid_resources_end == 1219511.96

    assert final_year.year == 2067
    assert final_year.medicare == {
        "part_b_base": 4192.8,
        "part_d_base": 832.8,
        "irmaa_part_b": 0.0,
        "irmaa_part_d": 0.0,
        "total": 5025.6,
        "covered_people": 2.0,
        "irmaa_tier": 0.0,
    }
    assert final_year.strategy == {
        "roth_conversion_total": 0.0,
        "conversion_tax_impact": 0.0,
        "conversion_tax_payment": 0.0,
        "conversion_tax_shortfall": 0.0,
        "rmd_total": 0.0,
        "qcd_total": 0.0,
        "taxable_rmd_total": 0.0,
        "charitable_giving_total": 0.0,
        "taxable_giving": 0.0,
    }
    assert final_year.taxes == {"federal": 683.17, "state": 273.27, "total": 956.44}
    assert final_year.mortgage["remaining_balance"] == 0.0
    assert final_year.withdrawals == {"Husband Roth IRA": 90470.38}
    assert final_year.net_cash_flow == 0.0
    assert final_year.liquid_resources_end == 619964.64
    assert final_year.alerts == (
        "Skipped 28568.13 of charitable giving because QCD-eligible IRA capacity was insufficient.",
    )
    assert result.summary == {
        "terminal_net_worth": 619964.64,
        "total_taxes_paid": 524410.22,
        "total_roth_converted": 428063.79,
        "projected_rmds_by_year_total": 0.0,
        "total_qcd": 0.0,
        "total_given": 0.0,
        "traditional_balance_at_husband_age_70": 0.0,
        "failure_year_if_any": None,
    }
    assert result.failure_year is None
    assert result.success is True

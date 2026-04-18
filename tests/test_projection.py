from copy import deepcopy
from pathlib import Path

import pytest

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
    assert any("Stage 9 desktop UI workflow" in warning for warning in result.warnings)


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
    assert first_year.net_cash_flow == 53452.35
    assert first_year.withdrawals == {}
    assert first_year.mortgage == {
        "scheduled_payment": 34200.0,
        "extra_principal": 0.0,
        "total_payment": 34200.0,
        "interest": 6404.58,
        "principal": 27795.42,
        "remaining_balance": 197204.58,
    }
    assert first_year.expenses["mortgage_payment"] == 34200.0
    assert first_year.liquid_resources_end == 835969.07
    assert first_year.alerts == (
        "Skipped 2698.54 of charitable giving because QCD-eligible IRA capacity was insufficient.",
    )

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
    assert payoff_year.taxes == {"federal": 53204.8, "state": 11067.47, "total": 64272.27}
    assert payoff_year.mortgage == {
        "scheduled_payment": 0.0,
        "extra_principal": 0.0,
        "total_payment": 0.0,
        "interest": 0.0,
        "principal": 0.0,
        "remaining_balance": 0.0,
    }
    assert payoff_year.expenses["mortgage_payment"] == 0.0
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
        "Skipped 8007.93 of charitable giving because QCD-eligible IRA capacity was insufficient.",
        "Reduced Roth conversion from 175000.00 to 0.00 because of tax or IRMAA guardrails.",
    )
    assert payoff_year.net_cash_flow == 175613.71
    assert payoff_year.liquid_resources_end == 2446997.78

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
        "conversion_tax_impact": 30265.82,
        "conversion_tax_payment": 30265.82,
        "conversion_tax_shortfall": 0.0,
        "rmd_total": 0,
        "qcd_total": 0.0,
        "taxable_rmd_total": 0.0,
        "charitable_giving_total": 0.0,
        "taxable_giving": 0.0,
    }
    assert retirement_year.taxes == {"federal": 24165.69, "state": 6100.13, "total": 30265.82}
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
    assert retirement_year.withdrawals == {"Taxable Bridge Account": 78430.53}
    assert retirement_year.liquid_resources_end == 2463243.05

    assert final_year.year == 2067
    assert final_year.medicare == {
        "part_b_base": 2096.4,
        "part_d_base": 416.4,
        "irmaa_part_b": 0.0,
        "irmaa_part_d": 0.0,
        "total": 2512.8,
        "covered_people": 1.0,
        "irmaa_tier": 0.0,
    }
    assert final_year.strategy == {
        "roth_conversion_total": 0.0,
        "conversion_tax_impact": 0.0,
        "conversion_tax_payment": 0.0,
        "conversion_tax_shortfall": 0.0,
        "rmd_total": 3757.85,
        "qcd_total": 3757.85,
        "taxable_rmd_total": 0.0,
        "charitable_giving_total": 3757.85,
        "taxable_giving": 0.0,
    }
    assert final_year.taxes == {"federal": 3693.94, "state": 1304.65, "total": 4998.59}
    assert final_year.mortgage["remaining_balance"] == 0.0
    assert final_year.withdrawals == {"Taxable Bridge Account": 26381.49}
    assert final_year.net_cash_flow == -0.0
    assert final_year.liquid_resources_end == 8369380.21
    assert final_year.alerts == (
        "Skipped 9832.96 of charitable giving because QCD-eligible IRA capacity was insufficient.",
    )
    assert result.summary == {
        "terminal_net_worth": 8369380.21,
        "total_taxes_paid": 510613.17,
        "total_roth_converted": 556250.0,
        "projected_rmds_by_year_total": 89958.81,
        "total_qcd": 89958.81,
        "total_given": 89958.81,
        "traditional_balance_at_husband_age_70": 279713.34,
        "failure_year_if_any": None,
    }
    assert result.failure_year is None
    assert result.success is True


def test_projection_can_roll_401k_balances_into_iras_at_retirement():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    base_scenario = load_scenario(scenario_path).scenario
    base_scenario.strategy.roth_conversions.enabled = False
    for account in base_scenario.accounts:
        if account.name == "Husband Roth 401k":
            account.starting_balance = 10000.0

    rollover_scenario = deepcopy(base_scenario)
    rollover_scenario.strategy.account_rollovers.enabled = True

    without_rollover = project_scenario(base_scenario)
    with_rollover = project_scenario(rollover_scenario)

    without_rollover_2033 = next(row for row in without_rollover.ledger if row.year == 2033)
    with_rollover_2033 = next(row for row in with_rollover.ledger if row.year == 2033)

    assert with_rollover_2033.account_balances_end["Husband Traditional 401k"] == 0.0
    assert with_rollover_2033.account_balances_end["Wife Traditional 401k"] == 0.0
    assert with_rollover_2033.account_balances_end["Husband Roth 401k"] == 0.0
    assert with_rollover_2033.rollovers == {
        "Husband Traditional 401k -> Husband Traditional IRA": 170678.22,
        "Husband Roth 401k -> Husband Roth IRA": 13738.73,
        "Wife Traditional 401k -> Wife Traditional IRA": 21569.81,
    }
    assert with_rollover_2033.account_balances_end["Husband Traditional IRA"] == pytest.approx(
        without_rollover_2033.account_balances_end["Husband Traditional IRA"]
        + without_rollover_2033.account_balances_end["Husband Traditional 401k"],
        abs=0.02,
    )
    assert with_rollover_2033.account_balances_end["Wife Traditional IRA"] == pytest.approx(
        without_rollover_2033.account_balances_end["Wife Traditional IRA"]
        + without_rollover_2033.account_balances_end["Wife Traditional 401k"],
        abs=0.02,
    )
    assert with_rollover_2033.account_balances_end["Husband Roth IRA"] == pytest.approx(
        without_rollover_2033.account_balances_end["Husband Roth IRA"]
        + without_rollover_2033.account_balances_end["Husband Roth 401k"],
        abs=0.02,
    )
    assert any(
        "Rolled Husband traditional 401k balances into Husband Traditional IRA at retirement."
        == alert
        for alert in with_rollover_2033.alerts
    )
    assert any(
        "Rolled Wife traditional 401k balances into Wife Traditional IRA at retirement." == alert
        for alert in with_rollover_2033.alerts
    )
    assert any(
        "Rolled Husband roth 401k balances into Husband Roth IRA at retirement." == alert
        for alert in with_rollover_2033.alerts
    )

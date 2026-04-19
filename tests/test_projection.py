from copy import deepcopy

import pytest

from retireplan.core import project_scenario


def test_projection_runs_with_rich_scenario_shape(golden_loaded):
    loaded = golden_loaded

    result = project_scenario(loaded.scenario, loaded.warnings)

    assert result.ledger
    assert result.summary["total_taxes_paid"] > 0.0
    assert result.summary["failure_year_if_any"] is None
    assert result.ledger[0].year == 2026
    assert result.ledger[-1].wife_age == loaded.scenario.simulation.end_condition.wife_age
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


def test_projection_matches_stage_7_baseline_checkpoints(golden_loaded):
    loaded = golden_loaded

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
    assert first_year.net_cash_flow == 77576.0
    assert first_year.withdrawals == {}
    assert first_year.mortgage == {
        "scheduled_payment": 21166.76,
        "extra_principal": 0.0,
        "total_payment": 21166.76,
        "interest": 6568.58,
        "principal": 14598.17,
        "remaining_balance": 210401.83,
    }
    assert first_year.expenses["mortgage_payment"] == 21166.76
    assert first_year.liquid_resources_end == 796111.09
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
    assert payoff_year.taxes == {"federal": 52436.8, "state": 10939.47, "total": 63376.27}
    assert payoff_year.mortgage == {
        "scheduled_payment": 38805.72,
        "extra_principal": 0.0,
        "total_payment": 38805.72,
        "interest": 1139.38,
        "principal": 37666.34,
        "remaining_balance": 0.0,
    }
    assert payoff_year.expenses["mortgage_payment"] == 38805.72
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
        "Reduced Roth conversion from 160000.00 to 0.00 because of tax or IRMAA guardrails.",
    )
    assert payoff_year.net_cash_flow == 163217.25
    assert payoff_year.liquid_resources_end == 1600922.18

    assert retirement_year.medicare == {
        "part_b_base": 4192.8,
        "part_d_base": 832.8,
        "irmaa_part_b": 0.0,
        "irmaa_part_d": 0.0,
        "total": 5025.6,
        "covered_people": 2.0,
        "irmaa_tier": 0.0,
    }
    assert retirement_year.strategy == {
        "roth_conversion_total": 160000.0,
        "conversion_tax_impact": 28783.82,
        "conversion_tax_payment": 28783.82,
        "conversion_tax_shortfall": 0.0,
        "rmd_total": 0,
        "qcd_total": 0.0,
        "taxable_rmd_total": 0.0,
        "charitable_giving_total": 0.0,
        "taxable_giving": 0.0,
    }
    assert retirement_year.taxes == {"federal": 22911.69, "state": 5872.13, "total": 28783.82}
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
    assert retirement_year.withdrawals == {"Taxable Bridge Account": 45848.64}
    assert retirement_year.surplus_allocations == {}
    assert retirement_year.rollovers == {
        "Husband Traditional 401k -> Husband Traditional IRA": 170678.22,
        "Husband Roth 401k -> Husband Roth IRA": 8243.24,
        "Wife Traditional 401k -> Wife Traditional IRA": 21569.81,
    }
    assert retirement_year.liquid_resources_end == 1639053.19

    assert final_year.year == 2057
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
        "rmd_total": 0.0,
        "qcd_total": 0.0,
        "taxable_rmd_total": 0.0,
        "charitable_giving_total": 0.0,
        "taxable_giving": 0.0,
    }
    assert final_year.taxes == {"federal": 1563.07, "state": 594.36, "total": 2157.43}
    assert final_year.mortgage["remaining_balance"] == 0.0
    assert final_year.withdrawals == {}
    assert final_year.surplus_allocations == {"Taxable Bridge Account": 4734.5}
    assert final_year.net_cash_flow == 4734.5
    assert final_year.liquid_resources_end == 7781387.68
    assert final_year.alerts == (
        "Skipped 10617.11 of charitable giving because QCD-eligible IRA capacity was insufficient.",
    )
    assert result.summary == {
        "terminal_net_worth": 7781387.68,
        "total_taxes_paid": 475692.8,
        "total_roth_converted": 640000.0,
        "projected_rmds_by_year_total": 71209.97,
        "total_qcd": 275572.89,
        "total_given": 275572.89,
        "traditional_balance_at_husband_age_70": 184047.69,
        "failure_year_if_any": None,
    }
    assert result.failure_year is None
    assert result.success is True


def test_projection_can_roll_401k_balances_into_iras_at_retirement(golden_scenario):
    base_scenario = golden_scenario
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


def test_bridge_account_uses_only_explicit_modeled_contributions_before_retirement(golden_loaded):
    loaded = golden_loaded

    result = project_scenario(loaded.scenario, loaded.warnings)
    rows = {row.year: row for row in result.ledger}

    pre_retirement = rows[2032]
    bridge_spending_phase = rows[2033]
    post_transition = rows[2037]
    final_year = rows[result.ledger[-1].year]

    assert pre_retirement.contributions["Taxable Bridge Account"] == 48000.0
    assert pre_retirement.surplus_allocations == {}
    assert bridge_spending_phase.contributions.get("Taxable Bridge Account", 0.0) == 0.0
    assert bridge_spending_phase.surplus_allocations == {}
    assert bridge_spending_phase.withdrawals["Taxable Bridge Account"] == 45848.64
    assert post_transition.surplus_allocations == {"Taxable Bridge Account": 43788.74}
    assert final_year.surplus_allocations == {"Taxable Bridge Account": 4734.5}

from copy import deepcopy
from pathlib import Path

from retireplan.core import project_scenario
from retireplan.io import load_scenario
from retireplan.tax import calculate_tax_summary


def _baseline_scenario():
    scenario_path = Path(__file__).resolve().parents[1] / "scenarios" / "baseline_v1.0.1.yaml"
    return load_scenario(scenario_path).scenario


def test_tax_summary_counts_extra_ordinary_income_for_conversions():
    scenario = _baseline_scenario()

    baseline = calculate_tax_summary(
        scenario,
        filing_status="mfj",
        income={
            "earned_income_husband": 0.0,
            "earned_income_wife": 0.0,
            "pension_income": 12000.0,
            "social_security_husband": 24000.0,
            "social_security_wife": 18000.0,
        },
        withdrawals={},
    )
    with_conversion = calculate_tax_summary(
        scenario,
        filing_status="mfj",
        income={
            "earned_income_husband": 0.0,
            "earned_income_wife": 0.0,
            "pension_income": 12000.0,
            "social_security_husband": 24000.0,
            "social_security_wife": 18000.0,
        },
        withdrawals={},
        extra_ordinary_income=100000.0,
    )

    assert with_conversion.ordinary_income == baseline.ordinary_income + 100000.0
    assert with_conversion.adjusted_gross_income > baseline.adjusted_gross_income
    assert with_conversion.total_tax > baseline.total_tax


def test_projection_executes_roth_conversions_in_active_years():
    scenario = _baseline_scenario()

    result = project_scenario(scenario)
    by_year = {row.year: row for row in result.ledger}
    conversion_year = by_year[2033]

    assert conversion_year.strategy["roth_conversion_total"] == 162500.0
    assert conversion_year.strategy["conversion_tax_impact"] == 30265.82
    assert conversion_year.account_balances_end["Husband Roth IRA"] == 610607.95
    assert conversion_year.account_balances_end["Husband Traditional IRA"] == 569223.18


def test_qcd_can_satisfy_rmd_before_taxable_distribution_when_conversions_disabled():
    scenario = _baseline_scenario()
    scenario.strategy.roth_conversions.enabled = False

    baseline = project_scenario(scenario)
    comparison = deepcopy(scenario)
    comparison.strategy.charitable_giving.qcd.enabled = False
    no_qcd = project_scenario(comparison)

    baseline_row = next(row for row in baseline.ledger if row.year == 2042)
    no_qcd_row = next(row for row in no_qcd.ledger if row.year == 2042)

    assert baseline_row.strategy["rmd_total"] == 2226.63
    assert baseline_row.strategy["qcd_total"] == 2226.63
    assert baseline_row.strategy["taxable_rmd_total"] == 0.0
    assert no_qcd_row.strategy["qcd_total"] == 0.0
    assert no_qcd_row.strategy["taxable_rmd_total"] == 2226.63
    assert no_qcd_row.withdrawals["Wife Traditional IRA"] > baseline_row.withdrawals.get(
        "Wife Traditional IRA", 0.0
    )


def test_charitable_giving_can_spill_into_standard_cashflow_when_allowed():
    scenario = _baseline_scenario()
    scenario.strategy.roth_conversions.enabled = False
    scenario.strategy.charitable_giving.coordination_rules.prohibit_other_accounts_for_giving = (
        False
    )
    scenario.strategy.charitable_giving.qcd.annual_limit = 5000.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2042)

    assert row.strategy["qcd_total"] == 2226.63
    assert row.strategy["taxable_giving"] > 0.0
    assert row.strategy["charitable_giving_total"] > row.strategy["taxable_giving"]
    assert row.expenses["charitable_giving"] == row.strategy["taxable_giving"]
    assert any("Funded" in alert and "charitable giving" in alert for alert in row.alerts)


def test_conversion_can_drop_below_minimum_to_preserve_age_seventy_target():
    scenario = _baseline_scenario()
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.base_policy.base_conversion_amounts[65] = 150000.0
    scenario.strategy.roth_conversions.base_policy.base_conversion_amounts[66] = 150000.0
    scenario.strategy.roth_conversions.base_policy.base_conversion_amounts[67] = 150000.0
    scenario.strategy.roth_conversions.base_policy.base_conversion_amounts[68] = 150000.0
    scenario.strategy.roth_conversions.base_policy.base_conversion_amounts[69] = 150000.0
    scenario.strategy.roth_conversions.balance_targets.traditional_ira_target_at_70 = 800000.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2032)

    assert 0.0 < row.strategy["roth_conversion_total"] < 100000.0
    assert any("preserve the traditional balance target at age 70" in alert for alert in row.alerts)
    assert any("below the configured minimum" in alert for alert in row.alerts)


def test_conversion_can_be_blocked_when_minimum_cannot_be_met_and_reduction_is_disallowed():
    scenario = _baseline_scenario()
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.10
    scenario.strategy.roth_conversions.tax_constraints.allow_partial_bracket_fill = True
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.safety_limits.min_conversion.reduce_if_exceeds_bracket = (
        False
    )
    scenario.strategy.roth_conversions.balance_targets.enabled = False

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2032)

    assert row.strategy["roth_conversion_total"] == 0.0
    assert any("Reduced Roth conversion" in alert for alert in row.alerts)


def test_conversion_tax_payment_uses_configured_source_order_before_general_withdrawals():
    scenario = _baseline_scenario()
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.tax_payment.source_order = ["household_operating_cash"]
    for account in scenario.accounts:
        if account.name == "Household Operating Cash":
            account.starting_balance = 200000.0
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2033)

    assert row.strategy["conversion_tax_payment"] == 30265.82
    assert row.strategy["conversion_tax_shortfall"] == 0.0
    assert row.withdrawals == {"Household Operating Cash": 30265.82}


def test_conversion_tax_payment_shortfall_is_tracked_when_configured_sources_are_empty():
    scenario = _baseline_scenario()
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.tax_payment.source_order = ["household_operating_cash"]
    for account in scenario.accounts:
        if account.name == "Household Operating Cash":
            account.starting_balance = 0.0
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2033)

    assert row.strategy["conversion_tax_payment"] == 0.0
    assert row.strategy["conversion_tax_shortfall"] == 30265.82
    assert row.withdrawals == {}
    assert any("Unable to pre-fund" in alert for alert in row.alerts)


def test_conversion_tax_payment_can_use_roth_assets_when_enabled():
    scenario = _baseline_scenario()
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.tax_payment.source_order = ["household_operating_cash"]
    scenario.strategy.roth_conversions.tax_payment.allow_roth_for_conversion_taxes = True
    for account in scenario.accounts:
        if account.name == "Household Operating Cash":
            account.starting_balance = 0.0
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2033)

    assert row.strategy["conversion_tax_payment"] == 30265.82
    assert row.strategy["conversion_tax_shortfall"] == 0.0
    assert row.withdrawals == {"Husband Roth IRA": 30265.82}
    assert any("from Roth assets" in alert for alert in row.alerts)


def test_conversion_tax_payment_can_gross_up_from_traditional_distribution():
    scenario = _baseline_scenario()
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.tax_payment.source_order = ["household_operating_cash"]
    scenario.strategy.roth_conversions.tax_payment.gross_up_conversion_if_needed = True
    for account in scenario.accounts:
        if account.name == "Household Operating Cash":
            account.starting_balance = 0.0
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2033)

    assert row.strategy["conversion_tax_payment"] > 30067.61
    assert row.strategy["conversion_tax_shortfall"] == 0.0
    assert row.withdrawals == {"Husband Traditional IRA": row.strategy["conversion_tax_payment"]}
    assert any("Grossed up conversion-tax funding" in alert for alert in row.alerts)


def test_conversion_only_tax_method_skips_tax_on_tax_feedback():
    incremental = _baseline_scenario()
    incremental.mortgage.enabled = False
    incremental.expenses.base_living.amount_annual = 0.0
    incremental.expenses.travel.amount_annual = 0.0
    incremental.expenses.housing.property_tax.amount_annual = 0.0
    incremental.expenses.housing.homeowners_insurance.amount_annual = 0.0
    incremental.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    incremental.strategy.roth_conversions.irmaa_controls.enabled = False
    incremental.strategy.roth_conversions.tax_payment.source_order = ["traditional_distribution"]
    for account in incremental.accounts:
        if account.name == "Household Operating Cash":
            account.starting_balance = 0.0
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    conversion_only = deepcopy(incremental)
    conversion_only.strategy.roth_conversions.tax_payment.estimated_tax_method = "conversion_only"

    incremental_result = project_scenario(incremental)
    conversion_only_result = project_scenario(conversion_only)
    incremental_row = next(item for item in incremental_result.ledger if item.year == 2033)
    conversion_only_row = next(item for item in conversion_only_result.ledger if item.year == 2033)

    assert incremental_row.strategy["conversion_tax_shortfall"] == 0.0
    assert conversion_only_row.strategy["conversion_tax_shortfall"] == 0.0
    assert (
        incremental_row.strategy["conversion_tax_payment"]
        > conversion_only_row.strategy["conversion_tax_payment"]
    )
    assert (
        incremental_row.withdrawals["Husband Traditional IRA"]
        > conversion_only_row.withdrawals["Husband Traditional IRA"]
    )

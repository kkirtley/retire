from copy import deepcopy
from datetime import date

from retireplan.core import project_scenario
from retireplan.scenario import Account, AccountOwner, AccountType
from retireplan.tax import calculate_tax_summary


def _ensure_household_operating_cash_account(scenario, starting_balance: float) -> None:
    for account in scenario.accounts:
        if account.name == "Household Operating Cash":
            account.starting_balance = starting_balance
            account.return_rate = 0.03
            account.withdrawals_enabled = True
            account.contributions_enabled = True
            return
    scenario.accounts.append(
        Account(
            name="Household Operating Cash",
            type=AccountType.CASH,
            owner=AccountOwner.HOUSEHOLD,
            starting_balance=starting_balance,
            return_rate=0.03,
            withdrawals_enabled=True,
            contributions_enabled=True,
        )
    )


def test_tax_summary_counts_extra_ordinary_income_for_conversions(golden_scenario):
    scenario = golden_scenario

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


def test_projection_executes_roth_conversions_in_active_years(golden_scenario):
    scenario = golden_scenario

    result = project_scenario(scenario)
    by_year = {row.year: row for row in result.ledger}
    conversion_year = by_year[2033]

    assert conversion_year.strategy["roth_conversion_total"] == 160000.0
    assert conversion_year.strategy["conversion_tax_impact"] == 34089.7
    assert conversion_year.account_balances_end["Husband Roth IRA"] == 657598.31
    assert conversion_year.account_balances_end["Wife Roth IRA"] == 60155.05
    assert conversion_year.account_balances_end["Husband Traditional IRA"] == 584294.6
    assert conversion_year.account_balances_end["Wife Traditional IRA"] == 0.0


def test_qcd_can_satisfy_rmd_before_taxable_distribution_when_conversions_disabled(golden_scenario):
    scenario = golden_scenario
    scenario.strategy.roth_conversions.enabled = False

    baseline = project_scenario(scenario)
    comparison = deepcopy(scenario)
    comparison.strategy.charitable_giving.qcd.enabled = False
    no_qcd = project_scenario(comparison)

    baseline_row = next(row for row in baseline.ledger if row.year == 2042)
    no_qcd_row = next(row for row in no_qcd.ledger if row.year == 2042)

    assert baseline_row.strategy["rmd_total"] == 30683.68
    assert baseline_row.strategy["qcd_total"] == 64232.18
    assert baseline_row.strategy["taxable_rmd_total"] == 2226.63
    assert round(sum(baseline_row.qcd_distributions.values()), 2) == 64232.18
    assert no_qcd_row.strategy["qcd_total"] == 0.0
    assert no_qcd_row.strategy["taxable_rmd_total"] == 42500.4
    assert no_qcd_row.qcd_distributions == {}
    assert no_qcd_row.withdrawals["Husband Traditional IRA"] > baseline_row.withdrawals.get(
        "Husband Traditional IRA", 0.0
    )


def test_charitable_giving_can_spill_into_standard_cashflow_when_allowed(golden_scenario):
    scenario = golden_scenario
    scenario.strategy.roth_conversions.enabled = False
    scenario.strategy.charitable_giving.coordination_rules.prohibit_other_accounts_for_giving = (
        False
    )
    scenario.strategy.charitable_giving.qcd.annual_limit = 5000.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2042)

    assert row.strategy["qcd_total"] == 5000.0
    assert sum(row.qcd_distributions.values()) == 5000.0
    assert row.strategy["charitable_giving_total"] == 39514.48
    assert row.strategy["taxable_giving"] == 34514.48
    assert row.strategy["taxable_giving"] > 0.0
    assert row.strategy["charitable_giving_total"] > row.strategy["taxable_giving"]
    assert row.expenses["charitable_giving"] == row.strategy["taxable_giving"]
    assert any("Funded" in alert and "charitable giving" in alert for alert in row.alerts)


def test_qcd_depletion_target_zeros_traditional_balances_by_wife_age_ninety(golden_scenario):
    scenario = golden_scenario

    result = project_scenario(scenario)
    wife_age_ninety_row = next(item for item in result.ledger if item.wife_age == 90)

    assert wife_age_ninety_row.account_balances_end["Husband Traditional IRA"] == 0.01
    assert wife_age_ninety_row.account_balances_end["Wife Traditional IRA"] == 0.0
    assert wife_age_ninety_row.strategy["qcd_total"] == 0.0


def test_conversion_can_drop_below_minimum_to_preserve_age_seventy_target(golden_scenario):
    scenario = golden_scenario
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


def test_conversion_can_be_blocked_when_minimum_cannot_be_met_and_reduction_is_disallowed(
    golden_scenario,
):
    scenario = golden_scenario
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


def test_conversion_tax_payment_uses_configured_source_order_before_general_withdrawals(
    golden_scenario,
):
    scenario = golden_scenario
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.safety_limits.max_conversion = 200000.0
    scenario.strategy.roth_conversions.tax_payment.source_order = ["household_operating_cash"]
    _ensure_household_operating_cash_account(scenario, 200000.0)
    for account in scenario.accounts:
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2033)

    assert row.strategy["conversion_tax_payment"] == 38396.82
    assert row.strategy["conversion_tax_shortfall"] == 0.0
    assert row.withdrawals == {"Household Operating Cash": 38396.82}


def test_conversion_tax_payment_shortfall_is_tracked_when_configured_sources_are_empty(
    golden_scenario,
):
    scenario = golden_scenario
    scenario.simulation.start_date = date(2033, 1, 1)
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.safety_limits.max_conversion = 200000.0
    scenario.strategy.roth_conversions.tax_payment.source_order = ["household_operating_cash"]
    _ensure_household_operating_cash_account(scenario, 0.0)
    for account in scenario.accounts:
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2033)

    assert row.strategy["conversion_tax_payment"] == 0.0
    assert row.strategy["conversion_tax_shortfall"] == 38396.82
    assert row.withdrawals == {}
    assert any("Unable to pre-fund" in alert for alert in row.alerts)


def test_conversion_tax_payment_can_use_roth_assets_when_enabled(golden_scenario):
    scenario = golden_scenario
    scenario.simulation.start_date = date(2033, 1, 1)
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.safety_limits.max_conversion = 200000.0
    scenario.strategy.roth_conversions.tax_payment.source_order = ["household_operating_cash"]
    scenario.strategy.roth_conversions.tax_payment.allow_roth_for_conversion_taxes = True
    _ensure_household_operating_cash_account(scenario, 0.0)
    for account in scenario.accounts:
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2033)

    assert row.strategy["conversion_tax_payment"] == 38396.82
    assert row.strategy["conversion_tax_shortfall"] == 0.0
    assert row.withdrawals == {"Husband Roth IRA": 38396.82}
    assert any("from Roth assets" in alert for alert in row.alerts)


def test_conversion_tax_payment_can_gross_up_from_traditional_distribution(golden_scenario):
    scenario = golden_scenario
    scenario.simulation.start_date = date(2033, 1, 1)
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = False
    scenario.strategy.roth_conversions.safety_limits.max_conversion = 200000.0
    scenario.strategy.roth_conversions.tax_payment.source_order = ["household_operating_cash"]
    scenario.strategy.roth_conversions.tax_payment.gross_up_conversion_if_needed = True
    _ensure_household_operating_cash_account(scenario, 0.0)
    for account in scenario.accounts:
        if account.name == "Taxable Bridge Account":
            account.starting_balance = 0.0

    result = project_scenario(scenario)
    row = next(item for item in result.ledger if item.year == 2033)

    assert row.strategy["conversion_tax_payment"] > 30067.61
    assert row.strategy["conversion_tax_shortfall"] == 0.1
    assert row.withdrawals == {"Husband Traditional IRA": row.strategy["conversion_tax_payment"]}
    assert any("Grossed up conversion-tax funding" in alert for alert in row.alerts)


def test_conversion_only_tax_method_skips_tax_on_tax_feedback(golden_scenario):
    incremental = golden_scenario
    incremental.mortgage.enabled = False
    incremental.expenses.base_living.amount_annual = 0.0
    incremental.expenses.travel.amount_annual = 0.0
    incremental.expenses.housing.property_tax.amount_annual = 0.0
    incremental.expenses.housing.homeowners_insurance.amount_annual = 0.0
    incremental.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    incremental.strategy.roth_conversions.irmaa_controls.enabled = False
    incremental.strategy.roth_conversions.safety_limits.max_conversion = 200000.0
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

    assert incremental_row.strategy["conversion_tax_shortfall"] == 0.1
    assert conversion_only_row.strategy["conversion_tax_shortfall"] == 0.0
    assert (
        incremental_row.strategy["conversion_tax_payment"]
        > conversion_only_row.strategy["conversion_tax_payment"]
    )
    assert (
        incremental_row.withdrawals["Husband Traditional IRA"]
        > conversion_only_row.withdrawals["Husband Traditional IRA"]
    )


def test_retirement_irmaa_override_can_relax_conversion_guardrails(golden_scenario):
    scenario = golden_scenario
    scenario.simulation.start_date = date(2033, 1, 1)
    scenario.mortgage.enabled = False
    scenario.expenses.base_living.amount_annual = 0.0
    scenario.expenses.travel.amount_annual = 0.0
    scenario.expenses.housing.property_tax.amount_annual = 0.0
    scenario.expenses.housing.homeowners_insurance.amount_annual = 0.0
    scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket = 0.37
    scenario.strategy.roth_conversions.irmaa_controls.enabled = True
    scenario.strategy.roth_conversions.irmaa_controls.reduce_if_exceeded = True
    scenario.strategy.roth_conversions.irmaa_controls.max_tier = 0
    scenario.strategy.roth_conversions.safety_limits.max_conversion = 200000.0

    without_override = deepcopy(scenario)
    without_override.medicare.irmaa.reconsideration.override_conversion_guardrails = False
    with_override = deepcopy(scenario)
    with_override.medicare.irmaa.reconsideration.override_conversion_guardrails = True

    without_override_result = project_scenario(without_override)
    with_override_result = project_scenario(with_override)
    without_override_row = next(
        item for item in without_override_result.ledger if item.year == 2033
    )
    with_override_row = next(item for item in with_override_result.ledger if item.year == 2033)

    assert without_override_row.strategy["roth_conversion_total"] == 191996.87
    assert with_override_row.strategy["roth_conversion_total"] == 200000.0
    assert any("Reduced Roth conversion" in alert for alert in without_override_row.alerts)
    assert not any("Reduced Roth conversion" in alert for alert in with_override_row.alerts)

from copy import deepcopy

from retireplan.tax import calculate_tax_summary


def test_federal_tax_applies_standard_deduction_and_brackets_for_mfj(golden_scenario):
    scenario = golden_scenario

    summary = calculate_tax_summary(
        scenario,
        filing_status="mfj",
        income={
            "earned_income_husband": 100000.0,
            "earned_income_wife": 50000.0,
            "pension_income": 0.0,
            "social_security_husband": 0.0,
            "social_security_wife": 0.0,
        },
        withdrawals={},
    )

    assert summary.standard_deduction == 30000.0
    assert summary.federal_taxable_income == 120000.0
    assert summary.federal_tax == 16228.0
    assert summary.state_tax == 4800.0


def test_standard_deduction_adds_age_sixty_five_amounts_for_2025(golden_scenario):
    scenario = golden_scenario

    summary_mfj = calculate_tax_summary(
        scenario,
        filing_status="mfj",
        income={
            "earned_income_husband": 40000.0,
            "earned_income_wife": 0.0,
            "pension_income": 0.0,
            "social_security_husband": 0.0,
            "social_security_wife": 0.0,
        },
        withdrawals={},
        senior_standard_deduction_count=2,
    )
    summary_single = calculate_tax_summary(
        scenario,
        filing_status="single",
        income={
            "earned_income_husband": 0.0,
            "earned_income_wife": 40000.0,
            "pension_income": 0.0,
            "social_security_husband": 0.0,
            "social_security_wife": 0.0,
        },
        withdrawals={},
        senior_standard_deduction_count=1,
    )

    assert summary_mfj.standard_deduction == 33200.0
    assert summary_mfj.federal_taxable_income == 6800.0
    assert summary_single.standard_deduction == 17000.0
    assert summary_single.federal_taxable_income == 23000.0


def test_taxable_social_security_is_capped_at_eighty_five_percent(golden_scenario):
    scenario = golden_scenario

    summary = calculate_tax_summary(
        scenario,
        filing_status="single",
        income={
            "earned_income_husband": 0.0,
            "earned_income_wife": 30000.0,
            "pension_income": 0.0,
            "social_security_husband": 0.0,
            "social_security_wife": 24000.0,
        },
        withdrawals={},
    )

    assert summary.social_security_benefits == 24000.0
    assert summary.taxable_social_security == 11300.0
    assert summary.adjusted_gross_income == 41300.0
    assert summary.state_taxable_income == 26300.0


def test_traditional_withdrawals_become_ordinary_income(golden_scenario):
    scenario = golden_scenario

    summary = calculate_tax_summary(
        scenario,
        filing_status="single",
        income={
            "earned_income_husband": 0.0,
            "earned_income_wife": 0.0,
            "pension_income": 12000.0,
            "social_security_husband": 0.0,
            "social_security_wife": 18000.0,
        },
        withdrawals={
            "Wife Traditional IRA": 20000.0,
            "Household Operating Cash": 5000.0,
        },
    )

    assert summary.ordinary_income == 32000.0
    assert summary.taxable_social_security == 10450.0
    assert summary.federal_taxable_income == 27450.0
    assert summary.federal_tax == 3055.5
    assert summary.state_tax == 1098.0


def test_projection_switches_to_single_filing_status_for_tax_math_after_death_year(golden_scenario):
    scenario = golden_scenario
    scenario.household.husband.modeled_death.enabled = True
    scenario.household.husband.modeled_death.death_year = 2034

    summary = calculate_tax_summary(
        scenario,
        filing_status="single",
        income={
            "earned_income_husband": 0.0,
            "earned_income_wife": 50000.0,
            "pension_income": 10000.0,
            "social_security_husband": 0.0,
            "social_security_wife": 18000.0,
        },
        withdrawals={},
    )

    assert summary.standard_deduction == 15000.0
    assert summary.federal_taxable_income == 60300.0
    assert summary.state_tax == 2412.0


def test_state_tax_none_model_produces_zero_tax_for_any_state(golden_scenario):
    scenario = deepcopy(golden_scenario)
    scenario.household.state_of_residence = "Texas"
    scenario.state_tax.model = "none"
    scenario.state_tax.effective_rate = None

    summary = calculate_tax_summary(
        scenario,
        filing_status="single",
        income={
            "earned_income_husband": 0.0,
            "earned_income_wife": 70000.0,
            "pension_income": 0.0,
            "social_security_husband": 0.0,
            "social_security_wife": 0.0,
        },
        withdrawals={},
    )

    assert summary.federal_tax > 0.0
    assert summary.state_taxable_income == 55000.0
    assert summary.state_tax == 0.0


def test_state_tax_effective_rate_is_generic_to_current_state(golden_scenario):
    scenario = deepcopy(golden_scenario)
    scenario.household.state_of_residence = "Illinois"
    scenario.state_tax.model = "effective_rate"
    scenario.state_tax.effective_rate = 0.0495

    summary = calculate_tax_summary(
        scenario,
        filing_status="single",
        income={
            "earned_income_husband": 0.0,
            "earned_income_wife": 80000.0,
            "pension_income": 0.0,
            "social_security_husband": 0.0,
            "social_security_wife": 0.0,
        },
        withdrawals={},
    )

    assert summary.federal_taxable_income == 65000.0
    assert summary.state_taxable_income == 65000.0
    assert summary.state_tax == 3217.5

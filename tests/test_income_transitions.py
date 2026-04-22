from copy import deepcopy

from retireplan.core import build_timeline, project_scenario
from retireplan.core.timeline_builder import milestone_date_for_age, year_fraction_for_dates


def test_survivor_transition_applies_single_status_expense_stepdown_and_ss_step_up(golden_scenario):
    scenario = deepcopy(golden_scenario)
    scenario.household.husband.modeled_death.enabled = True
    scenario.household.husband.modeled_death.death_year = 2040

    result = project_scenario(scenario)
    rows = {row.year: row for row in result.ledger}

    pre_survivor = rows[2040]
    survivor = rows[2041]

    assert pre_survivor.filing_status == "mfj"
    assert survivor.filing_status == "single"
    assert survivor.husband_alive is False
    assert survivor.wife_alive is True

    assert survivor.income["va_disability"] == 0.0
    assert survivor.income["va_survivor_benefit"] > 0.0
    assert survivor.income["social_security_husband"] == 0.0
    assert survivor.income["social_security_wife"] > pre_survivor.income["social_security_wife"]

    assert survivor.expenses["base_living"] < pre_survivor.expenses["base_living"]
    expected_survivor_base_living = round(
        pre_survivor.expenses["base_living"]
        * (1 + scenario.expenses.base_living.inflation_rate)
        * scenario.household.expense_stepdown_after_husband_death.surviving_expense_ratio,
        2,
    )
    assert survivor.expenses["base_living"] == expected_survivor_base_living


def test_va_survivor_benefit_does_not_start_when_death_precedes_eligibility_rule(golden_scenario):
    scenario = deepcopy(golden_scenario)
    scenario.household.husband.modeled_death.enabled = True
    scenario.household.husband.modeled_death.death_year = 2034

    result = project_scenario(scenario)
    rows = {row.year: row for row in result.ledger}

    survivor = rows[2035]

    assert survivor.filing_status == "single"
    assert survivor.income["va_disability"] == 0.0
    assert survivor.income["va_survivor_benefit"] == 0.0
    assert survivor.income["social_security_husband"] == 0.0
    assert survivor.income["social_security_wife"] > 0.0


def test_social_security_claims_start_in_birthday_month_with_proration(golden_scenario):
    scenario = deepcopy(golden_scenario)

    result = project_scenario(scenario)
    rows = {row.year: row for row in result.ledger}
    periods = {period.year: period for period in build_timeline(scenario)}

    wife_claim_date = milestone_date_for_age(
        scenario.household.wife.birth_year,
        scenario.household.wife.birth_month,
        scenario.income.social_security.wife.claim_age,
    )
    husband_claim_date = milestone_date_for_age(
        scenario.household.husband.birth_year,
        scenario.household.husband.birth_month,
        scenario.income.social_security.husband.claim_age,
    )
    wife_claim_fraction = year_fraction_for_dates(periods[2032], wife_claim_date, None, scenario)
    husband_claim_fraction = year_fraction_for_dates(
        periods[2037], husband_claim_date, None, scenario
    )

    assert rows[2031].income["social_security_wife"] == 0.0
    assert rows[2032].income["social_security_wife"] == round(1500.0 * 12 * wife_claim_fraction, 2)
    assert rows[2032].income["social_security_wife"] < 1500.0 * 12
    assert rows[2036].income["social_security_husband"] == 0.0
    assert rows[2037].income["social_security_husband"] == round(
        5002.0 * 12 * husband_claim_fraction, 2
    )
    assert rows[2037].income["social_security_husband"] < 5002.0 * 12

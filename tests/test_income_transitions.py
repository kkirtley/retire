from copy import deepcopy

from retireplan.core import project_scenario


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

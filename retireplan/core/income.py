"""Stage 2 income calculations for annual projection periods."""

from __future__ import annotations

from datetime import date

from retireplan.core.market_history import compound_growth_factor
from retireplan.core.timeline_builder import TimelinePeriod, year_fraction_for_dates
from retireplan.scenario import EarnedIncomePerson, RetirementScenario


def build_income(scenario: RetirementScenario, period: TimelinePeriod) -> dict[str, float]:
    earned_income = {
        "husband": earned_income_for_period(
            scenario.income.earned_income.husband,
            period,
            scenario,
        ),
        "wife": earned_income_for_period(
            scenario.income.earned_income.wife,
            period,
            scenario,
        ),
    }

    husband_ss = 0.0
    wife_ss = 0.0
    if period.husband_alive:
        husband_ss = social_security_for_year(
            scenario.income.social_security.husband.amount_monthly_at_claim,
            scenario.income.social_security.husband.cola_rate,
            scenario.household.husband.birth_year,
            scenario.income.social_security.husband.claim_age,
            period.year,
            scenario,
        )

    own_wife_ss = 0.0
    if period.wife_alive:
        own_wife_ss = social_security_for_year(
            scenario.income.social_security.wife.amount_monthly_at_claim,
            scenario.income.social_security.wife.cola_rate,
            scenario.household.wife.birth_year,
            scenario.income.social_security.wife.claim_age,
            period.year,
            scenario,
        )
        own_wife_ss *= period.fraction_of_year
        if period.survivor_phase and scenario.income.social_security.survivor_rule.enabled:
            survivor_benefit = social_security_for_year(
                scenario.income.social_security.husband.amount_monthly_at_claim,
                scenario.income.social_security.husband.cola_rate,
                scenario.household.husband.birth_year,
                scenario.income.social_security.husband.claim_age,
                period.year,
                scenario,
            )
            survivor_benefit *= period.fraction_of_year
            wife_ss = max(own_wife_ss, survivor_benefit)
        else:
            wife_ss = own_wife_ss

    return {
        "earned_income_husband": earned_income["husband"],
        "earned_income_wife": earned_income["wife"],
        "va_disability": va_disability_for_period(scenario, period),
        "va_survivor_benefit": va_survivor_for_period(scenario, period),
        "social_security_husband": round(husband_ss * period.fraction_of_year, 2),
        "social_security_wife": round(wife_ss, 2),
        "pension_income": pension_for_period(scenario, period),
    }


def earned_income_for_period(
    config: EarnedIncomePerson,
    period: TimelinePeriod,
    scenario: RetirementScenario,
) -> float:
    if (
        not config.enabled
        or period.year < config.start_date.year
        or period.year > config.end_date.year
    ):
        return 0.0
    active_fraction = year_fraction_for_dates(period, config.start_date, config.end_date, scenario)
    if active_fraction <= 0:
        return 0.0
    years_since_start = period.year - config.start_date.year
    return round(
        config.annual_gross_salary_start
        * ((1 + config.annual_raise_rate) ** years_since_start)
        * active_fraction,
        2,
    )


def social_security_for_year(
    monthly_amount_at_claim: float,
    cola_rate: float,
    birth_year: int,
    claim_age: float,
    year: int,
    scenario: RetirementScenario,
) -> float:
    claim_year = birth_year + int(claim_age)
    if year < claim_year:
        return 0.0
    growth_factor = compound_growth_factor(
        scenario,
        claim_year,
        year,
        cola_rate,
        use_historical_inflation=scenario.historical_analysis.use_historical_inflation_for_income_cola,
    )
    return round(monthly_amount_at_claim * 12 * growth_factor, 2)


def va_disability_for_period(scenario: RetirementScenario, period: TimelinePeriod) -> float:
    benefit = scenario.income.va_disability
    if not period.husband_alive or period.year < benefit.start_date.year:
        return 0.0
    growth_factor = compound_growth_factor(
        scenario,
        benefit.start_date.year,
        period.year,
        benefit.cola_rate,
        use_historical_inflation=scenario.historical_analysis.use_historical_inflation_for_income_cola,
    )
    return round(
        benefit.amount_monthly
        * 12
        * growth_factor
        * year_fraction_for_dates(period, benefit.start_date, None, scenario),
        2,
    )


def va_survivor_for_period(scenario: RetirementScenario, period: TimelinePeriod) -> float:
    benefit = scenario.income.va_survivor_benefit
    death_year = scenario.household.husband.modeled_death.death_year
    if not benefit.enabled or death_year is None or period.year <= death_year:
        return 0.0
    death_cutoff = date(death_year, 12, 31)
    if death_cutoff < benefit.conditional_start.husband_death_after:
        return 0.0
    benefit_start = date(death_year + 1, 1, 1)
    growth_factor = compound_growth_factor(
        scenario,
        benefit_start.year,
        period.year,
        benefit.cola_rate,
        use_historical_inflation=scenario.historical_analysis.use_historical_inflation_for_income_cola,
    )
    return round(
        benefit.amount_monthly
        * 12
        * growth_factor
        * year_fraction_for_dates(period, benefit_start, None, scenario),
        2,
    )


def pension_for_period(scenario: RetirementScenario, period: TimelinePeriod) -> float:
    pension = scenario.income.pension_income.wife_imrf
    if not pension.enabled or not period.wife_alive or period.year < pension.start_date.year:
        return 0.0
    growth_factor = compound_growth_factor(
        scenario,
        pension.start_date.year,
        period.year,
        pension.cola_rate,
        use_historical_inflation=scenario.historical_analysis.use_historical_inflation_for_income_cola,
    )
    return round(
        pension.amount_monthly
        * 12
        * growth_factor
        * year_fraction_for_dates(period, pension.start_date, None, scenario),
        2,
    )

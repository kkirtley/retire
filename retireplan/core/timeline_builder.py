"""Build annual timeline periods for staged retirement projections."""

from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass
from datetime import date
from enum import Enum

from retireplan.scenario import RetirementScenario


class TimelineEvent(str, Enum):
    SCENARIO_START = "scenario_start"
    HOUSEHOLD_RETIREMENT_TRANSITION = "household_retirement_transition"
    HUSBAND_REACHES_RETIREMENT_AGE = "husband_reaches_retirement_age"
    WIFE_REACHES_RETIREMENT_AGE = "wife_reaches_retirement_age"
    HUSBAND_EARNED_INCOME_ACTIVE = "husband_earned_income_active"
    WIFE_EARNED_INCOME_ACTIVE = "wife_earned_income_active"
    WIFE_PENSION_STARTS = "wife_pension_starts"
    HUSBAND_SOCIAL_SECURITY_CLAIM_YEAR = "husband_social_security_claim_year"
    WIFE_SOCIAL_SECURITY_CLAIM_YEAR = "wife_social_security_claim_year"
    HUSBAND_MEDICARE_AGE = "husband_medicare_age"
    WIFE_MEDICARE_AGE = "wife_medicare_age"
    SURVIVOR_PHASE = "survivor_phase"


@dataclass(frozen=True)
class TimelinePeriod:
    year: int
    period_start: date
    period_end: date
    fraction_of_year: float
    days_in_year: int
    husband_age: int
    wife_age: int
    husband_alive: bool
    wife_alive: bool
    husband_retired: bool
    wife_retired: bool
    survivor_phase: bool
    filing_status: str
    events: tuple[TimelineEvent, ...]

    def has_event(self, event: TimelineEvent) -> bool:
        return event in self.events


def build_timeline(scenario: RetirementScenario) -> list[TimelinePeriod]:
    """Build annual periods from scenario start through wife age 100."""

    end_year = scenario.household.wife.birth_year + scenario.simulation.end_condition.wife_age
    periods: list[TimelinePeriod] = []
    for year in range(scenario.simulation.start_date.year, end_year + 1):
        period_start = (
            scenario.simulation.start_date
            if year == scenario.simulation.start_date.year
            else date(year, 1, 1)
        )
        period_end = date(year, 12, 31)
        husband_age = attained_age_on(
            scenario.household.husband.birth_year,
            scenario.household.husband.birth_month,
            period_end,
        )
        wife_age = attained_age_on(
            scenario.household.wife.birth_year,
            scenario.household.wife.birth_month,
            period_end,
        )
        husband_alive = _is_alive(scenario.household.husband.modeled_death.death_year, year)
        wife_alive = _is_alive(scenario.household.wife.modeled_death.death_year, year)
        survivor_phase = _survivor_phase(scenario, year)
        days_in_year = 366 if isleap(year) else 365

        periods.append(
            TimelinePeriod(
                year=year,
                period_start=period_start,
                period_end=period_end,
                fraction_of_year=_year_fraction(period_start, period_end, days_in_year, scenario),
                days_in_year=days_in_year,
                husband_age=husband_age,
                wife_age=wife_age,
                husband_alive=husband_alive,
                wife_alive=wife_alive,
                husband_retired=_retired_for_year(
                    scenario.household.husband.retirement_age, husband_age, scenario, year
                ),
                wife_retired=_retired_for_year(
                    scenario.household.wife.retirement_age, wife_age, scenario, year
                ),
                survivor_phase=survivor_phase,
                filing_status=_filing_status_for_year(scenario, year),
                events=_build_period_events(
                    scenario,
                    year,
                    period_start,
                    period_end,
                    husband_age,
                    wife_age,
                    survivor_phase,
                ),
            )
        )

    return periods


def year_fraction_for_dates(
    period: TimelinePeriod,
    start_date: date,
    end_date: date | None,
    scenario: RetirementScenario,
) -> float:
    """Return the fraction of the calendar year where the given date span overlaps the period."""

    overlap_start = max(period.period_start, start_date)
    overlap_end = period.period_end if end_date is None else min(period.period_end, end_date)
    if overlap_end < overlap_start:
        return 0.0

    if scenario.simulation.proration.enabled:
        if scenario.simulation.proration.method == "monthly":
            return _monthly_fraction(overlap_start, overlap_end)
        return _daily_fraction(overlap_start, overlap_end, period.days_in_year)

    return 1.0 if overlap_start <= period.period_start and overlap_end >= period.period_end else 0.0


def _year_fraction(
    period_start: date,
    period_end: date,
    days_in_year: int,
    scenario: RetirementScenario,
) -> float:
    if not scenario.simulation.proration.enabled:
        return 1.0
    if scenario.simulation.proration.method == "monthly":
        return _monthly_fraction(period_start, period_end)
    return _daily_fraction(period_start, period_end, days_in_year)


def _daily_fraction(start_date: date, end_date: date, days_in_year: int) -> float:
    return _inclusive_days(start_date, end_date) / days_in_year


def _monthly_fraction(start_date: date, end_date: date) -> float:
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
    return months / 12


def _inclusive_days(start_date: date, end_date: date) -> int:
    return (end_date - start_date).days + 1


def _is_alive(death_year: int | None, year: int) -> bool:
    return death_year is None or year <= death_year


def _survivor_phase(scenario: RetirementScenario, year: int) -> bool:
    death_year = scenario.household.husband.modeled_death.death_year
    return death_year is not None and year > death_year


def _retired_for_year(
    retirement_age: int,
    current_age: int,
    scenario: RetirementScenario,
    year: int,
) -> bool:
    retirement_year = scenario.simulation.retirement_date.year
    if year > retirement_year:
        return True
    if year == retirement_year and scenario.simulation.retirement_date == date(year, 1, 1):
        return True
    return current_age >= retirement_age and year >= retirement_year


def _filing_status_for_year(scenario: RetirementScenario, year: int) -> str:
    death_year = scenario.household.husband.modeled_death.death_year
    if death_year is not None and year > death_year:
        return "single"
    return str(scenario.household.filing_status_initial)


def _build_period_events(
    scenario: RetirementScenario,
    year: int,
    period_start: date,
    period_end: date,
    husband_age: int,
    wife_age: int,
    survivor_phase: bool,
) -> tuple[TimelineEvent, ...]:
    event_conditions = (
        (year == scenario.simulation.start_date.year, TimelineEvent.SCENARIO_START),
        (
            year == scenario.simulation.retirement_date.year,
            TimelineEvent.HOUSEHOLD_RETIREMENT_TRANSITION,
        ),
        (
            milestone_occurs_within_period(
                period_start,
                period_end,
                scenario.household.husband.birth_year,
                scenario.household.husband.birth_month,
                float(scenario.household.husband.retirement_age),
            ),
            TimelineEvent.HUSBAND_REACHES_RETIREMENT_AGE,
        ),
        (
            milestone_occurs_within_period(
                period_start,
                period_end,
                scenario.household.wife.birth_year,
                scenario.household.wife.birth_month,
                float(scenario.household.wife.retirement_age),
            ),
            TimelineEvent.WIFE_REACHES_RETIREMENT_AGE,
        ),
        (
            year == scenario.income.earned_income.husband.start_date.year,
            TimelineEvent.HUSBAND_EARNED_INCOME_ACTIVE,
        ),
        (
            year == scenario.income.earned_income.wife.start_date.year,
            TimelineEvent.WIFE_EARNED_INCOME_ACTIVE,
        ),
        (
            year == scenario.income.pension_income.wife_imrf.start_date.year,
            TimelineEvent.WIFE_PENSION_STARTS,
        ),
        (
            milestone_occurs_within_period(
                period_start,
                period_end,
                scenario.household.husband.birth_year,
                scenario.household.husband.birth_month,
                scenario.income.social_security.husband.claim_age,
            ),
            TimelineEvent.HUSBAND_SOCIAL_SECURITY_CLAIM_YEAR,
        ),
        (
            milestone_occurs_within_period(
                period_start,
                period_end,
                scenario.household.wife.birth_year,
                scenario.household.wife.birth_month,
                scenario.income.social_security.wife.claim_age,
            ),
            TimelineEvent.WIFE_SOCIAL_SECURITY_CLAIM_YEAR,
        ),
        (
            milestone_occurs_within_period(
                period_start,
                period_end,
                scenario.household.husband.birth_year,
                scenario.household.husband.birth_month,
                float(scenario.medicare.start_age),
            ),
            TimelineEvent.HUSBAND_MEDICARE_AGE,
        ),
        (
            milestone_occurs_within_period(
                period_start,
                period_end,
                scenario.household.wife.birth_year,
                scenario.household.wife.birth_month,
                float(scenario.medicare.start_age),
            ),
            TimelineEvent.WIFE_MEDICARE_AGE,
        ),
        (survivor_phase, TimelineEvent.SURVIVOR_PHASE),
    )
    return tuple(event for condition, event in event_conditions if condition)


def milestone_date_for_age(birth_year: int, birth_month: int, age: float) -> date:
    months_after_birth = int(round(age * 12))
    year_offset, zero_based_month = divmod((birth_month - 1) + months_after_birth, 12)
    return date(birth_year + year_offset, zero_based_month + 1, 1)


def attained_age_on(birth_year: int, birth_month: int, on_date: date) -> int:
    age = on_date.year - birth_year
    if (on_date.month, on_date.day) < (birth_month, 1):
        age -= 1
    return age


def milestone_occurs_within_period(
    period_start: date,
    period_end: date,
    birth_year: int,
    birth_month: int,
    age: float,
) -> bool:
    milestone_date = milestone_date_for_age(birth_year, birth_month, age)
    return period_start <= milestone_date <= period_end


def fraction_after_age_milestone(
    period: TimelinePeriod,
    birth_year: int,
    birth_month: int,
    age: float,
    scenario: RetirementScenario,
) -> float:
    milestone_date = milestone_date_for_age(birth_year, birth_month, age)
    return year_fraction_for_dates(period, milestone_date, None, scenario)

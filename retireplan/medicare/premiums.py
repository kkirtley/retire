"""Stage 6 Medicare premiums and IRMAA calculations."""

from __future__ import annotations

from dataclasses import dataclass

from retireplan.core.timeline_builder import TimelinePeriod
from retireplan.scenario import IRMAATier, RetirementScenario


@dataclass(frozen=True)
class MedicareSummary:
    part_b_base: float
    part_d_base: float
    irmaa_part_b: float
    irmaa_part_d: float
    total: float
    covered_people: int
    irmaa_tier: int
    lookback_year: int | None
    alerts: tuple[str, ...]

    def ledger_values(self) -> dict[str, float]:
        return {
            "part_b_base": round(self.part_b_base, 2),
            "part_d_base": round(self.part_d_base, 2),
            "irmaa_part_b": round(self.irmaa_part_b, 2),
            "irmaa_part_d": round(self.irmaa_part_d, 2),
            "total": round(self.total, 2),
            "covered_people": float(self.covered_people),
            "irmaa_tier": float(self.irmaa_tier),
        }


def calculate_medicare_summary(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    lookback_magi: float | None,
    lookback_filing_status: str | None,
    current_year_magi: float | None = None,
    current_year_filing_status: str | None = None,
    previous_irmaa_tier: int | None = None,
) -> MedicareSummary:
    covered_people = _covered_people(scenario, period)
    if covered_people == 0:
        return MedicareSummary(
            part_b_base=0.0,
            part_d_base=0.0,
            irmaa_part_b=0.0,
            irmaa_part_d=0.0,
            total=0.0,
            covered_people=0,
            irmaa_tier=0,
            lookback_year=None,
            alerts=(),
        )

    tier_index, tier, determination_year, determination_label = effective_irmaa_tier(
        scenario,
        period,
        lookback_magi,
        lookback_filing_status,
        current_year_magi=current_year_magi,
        current_year_filing_status=current_year_filing_status,
    )
    part_b_base = float(scenario.medicare.part_b.base_premium_monthly) * 12 * covered_people
    part_d_base = float(scenario.medicare.part_d.base_premium_monthly) * 12 * covered_people
    irmaa_part_b = float(tier.part_b_add) * 12 * covered_people
    irmaa_part_d = float(tier.part_d_add) * 12 * covered_people
    total = part_b_base + part_d_base + irmaa_part_b + irmaa_part_d

    alerts: list[str] = []
    if previous_irmaa_tier is not None and tier_index != previous_irmaa_tier:
        alerts.append(
            f"IRMAA tier changed from {previous_irmaa_tier} to {tier_index} based on {determination_label}."
        )

    return MedicareSummary(
        part_b_base=round(part_b_base, 2),
        part_d_base=round(part_d_base, 2),
        irmaa_part_b=round(irmaa_part_b, 2),
        irmaa_part_d=round(irmaa_part_d, 2),
        total=round(total, 2),
        covered_people=covered_people,
        irmaa_tier=tier_index,
        lookback_year=determination_year,
        alerts=tuple(alerts),
    )


def effective_irmaa_tier(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    lookback_magi: float | None,
    lookback_filing_status: str | None,
    current_year_magi: float | None = None,
    current_year_filing_status: str | None = None,
) -> tuple[int, IRMAATier, int | None, str]:
    effective_magi = lookback_magi
    effective_filing_status = lookback_filing_status
    determination_year = period.year - scenario.medicare.irmaa.lookback_years
    determination_label = f"{determination_year} MAGI"

    if _use_irmaa_reconsideration(scenario, period, current_year_magi):
        effective_magi = current_year_magi
        effective_filing_status = current_year_filing_status or period.filing_status
        determination_year = period.year
        determination_label = (
            "current-year MAGI via "
            f"{scenario.medicare.irmaa.reconsideration.event} reconsideration"
        )

    tier_index, tier = _irmaa_tier(scenario, effective_magi, effective_filing_status)
    return tier_index, tier, determination_year, determination_label


def should_override_irmaa_conversion_guardrails(
    scenario: RetirementScenario,
    period: TimelinePeriod,
) -> bool:
    reconsideration = scenario.medicare.irmaa.reconsideration
    return _is_irmaa_reconsideration_active(scenario, period) and bool(
        reconsideration.override_conversion_guardrails
    )


def _use_irmaa_reconsideration(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    current_year_magi: float | None,
) -> bool:
    reconsideration = scenario.medicare.irmaa.reconsideration
    return (
        _is_irmaa_reconsideration_active(scenario, period)
        and reconsideration.use_current_year_magi
        and current_year_magi is not None
    )


def _is_irmaa_reconsideration_active(
    scenario: RetirementScenario,
    period: TimelinePeriod,
) -> bool:
    reconsideration = scenario.medicare.irmaa.reconsideration
    if not reconsideration.enabled:
        return False
    if reconsideration.apply_after_retirement:
        return period.husband_retired or period.wife_retired
    return False


def _covered_people(scenario: RetirementScenario, period: TimelinePeriod) -> int:
    start_age = scenario.medicare.start_age
    count = 0
    if period.husband_alive and period.husband_age >= start_age:
        count += 1
    if period.wife_alive and period.wife_age >= start_age:
        count += 1
    return count


def _irmaa_tier(
    scenario: RetirementScenario,
    lookback_magi: float | None,
    lookback_filing_status: str | None,
) -> tuple[int, IRMAATier]:
    tiers = (
        scenario.medicare.irmaa.single
        if lookback_filing_status == "single"
        else scenario.medicare.irmaa.mfj
    )
    if lookback_magi is None:
        return 0, tiers[0]

    for index, tier in enumerate(tiers):
        if tier.magi_up_to is None or lookback_magi <= tier.magi_up_to:
            return index, tier
    return len(tiers) - 1, tiers[-1]

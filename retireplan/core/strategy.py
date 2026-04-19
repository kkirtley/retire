"""Stage 7 planned withdrawals, conversions, RMDs, and QCD execution."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from retireplan.core.market_history import (
    account_type_return_for_period,
    fixed_account_return_for_year,
)
from retireplan.core.timeline_builder import TimelinePeriod
from retireplan.medicare.premiums import should_override_irmaa_conversion_guardrails
from retireplan.scenario import Account, AccountOwner, AccountType, RetirementScenario
from retireplan.tax import TaxSummary, calculate_tax_summary, senior_standard_deduction_count


@dataclass(frozen=True)
class StrategyExecution:
    cash_withdrawals: dict[str, float]
    qcd_distributions: dict[str, float]
    roth_conversion_total: float
    conversion_tax_payment: float
    conversion_tax_shortfall: float
    rmd_total: float
    qcd_total: float
    taxable_rmd_total: float
    taxable_giving: float
    charitable_giving_total: float
    conversion_ordinary_income: float
    alerts: tuple[str, ...]

    def ledger_values(self, conversion_tax_impact: float) -> dict[str, float]:
        return {
            "roth_conversion_total": round(self.roth_conversion_total, 2),
            "conversion_tax_impact": round(conversion_tax_impact, 2),
            "conversion_tax_payment": round(self.conversion_tax_payment, 2),
            "conversion_tax_shortfall": round(self.conversion_tax_shortfall, 2),
            "rmd_total": round(self.rmd_total, 2),
            "qcd_total": round(self.qcd_total, 2),
            "taxable_rmd_total": round(self.taxable_rmd_total, 2),
            "charitable_giving_total": round(self.charitable_giving_total, 2),
            "taxable_giving": round(self.taxable_giving, 2),
        }


@dataclass(frozen=True)
class QCDDepletionOwnerProgress:
    owner: str
    target_age: int
    current_balance: float
    annual_qcd_required: float
    actual_qcd: float
    projected_balance_at_target_age: float
    on_pace: bool
    constrained: bool


def execute_strategy(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    income: dict[str, float],
    filing_status: str,
    balances: dict[str, float],
) -> StrategyExecution:
    alerts: list[str] = []
    cash_withdrawals: dict[str, float] = {}
    qcd_distributions: dict[str, float] = {}

    rmd_targets = _rmd_targets(scenario, period, balances)
    total_rmd = round(sum(rmd_targets.values()), 2)

    giving_target = _charitable_giving_target(scenario, income, total_rmd)
    qcd_total, qcd_distributions, qcd_alerts = _apply_qcd(
        scenario,
        period,
        balances,
        rmd_targets,
        giving_target,
    )
    alerts.extend(qcd_alerts)
    remaining_giving = round(max(giving_target - qcd_total, 0.0), 2)

    taxable_rmd_total = 0.0
    if (
        scenario.strategy.withdrawals.rmd_handling.enforce
        and scenario.strategy.withdrawals.rmd_handling.withdraw_remaining_rmd_if_needed
    ):
        for owner in (AccountOwner.HUSBAND, AccountOwner.WIFE):
            owner_rmd = rmd_targets.get(owner.value, 0.0)
            if owner_rmd <= 0:
                continue
            owner_withdrawals = _withdraw_from_accounts(
                _traditional_accounts_for_owner(scenario, owner),
                balances,
                owner_rmd,
            )
            if owner_withdrawals:
                _merge_amounts(cash_withdrawals, owner_withdrawals)
                taxable_rmd_total += sum(owner_withdrawals.values())

    taxable_giving = 0.0
    charitable_giving_total = qcd_total
    if remaining_giving > 0:
        if (
            scenario.strategy.charitable_giving.coordination_rules.prohibit_other_accounts_for_giving
        ):
            alerts.append(
                f"Skipped {remaining_giving:.2f} of charitable giving because QCD-eligible IRA capacity was insufficient."
            )
        else:
            taxable_giving = remaining_giving
            charitable_giving_total += taxable_giving
            alerts.append(
                f"Funded {taxable_giving:.2f} of charitable giving from standard cashflow after QCD capacity was exhausted."
            )

    roth_conversion_total = _execute_roth_conversions(
        scenario,
        period,
        income,
        filing_status,
        balances,
        cash_withdrawals,
        alerts,
    )
    conversion_tax_payment, conversion_tax_shortfall = _fund_conversion_tax_payment(
        scenario,
        period,
        filing_status,
        income,
        roth_conversion_total,
        balances,
        cash_withdrawals,
        alerts,
    )

    return StrategyExecution(
        cash_withdrawals=_rounded_values(cash_withdrawals),
        qcd_distributions=_rounded_values(qcd_distributions),
        roth_conversion_total=round(roth_conversion_total, 2),
        conversion_tax_payment=round(conversion_tax_payment, 2),
        conversion_tax_shortfall=round(conversion_tax_shortfall, 2),
        rmd_total=round(total_rmd, 2),
        qcd_total=round(qcd_total, 2),
        taxable_rmd_total=round(taxable_rmd_total, 2),
        taxable_giving=round(taxable_giving, 2),
        charitable_giving_total=round(charitable_giving_total, 2),
        conversion_ordinary_income=round(roth_conversion_total, 2),
        alerts=tuple(alerts),
    )


def conversion_tax_impact(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    filing_status: str,
    income: dict[str, float],
    withdrawals: dict[str, float],
    total_tax_summary: TaxSummary,
    strategy_execution: StrategyExecution,
) -> float:
    if strategy_execution.roth_conversion_total <= 0:
        return 0.0

    baseline = calculate_tax_summary(
        scenario,
        filing_status,
        income,
        withdrawals,
        extra_ordinary_income=0.0,
        senior_standard_deduction_count=senior_standard_deduction_count(
            filing_status,
            husband_age=period.husband_age,
            wife_age=period.wife_age,
            husband_alive=period.husband_alive,
            wife_alive=period.wife_alive,
        ),
    )
    return round(total_tax_summary.total_tax - baseline.total_tax, 2)


def _rmd_targets(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    balances: dict[str, float],
) -> dict[str, float]:
    if not scenario.strategy.withdrawals.rmd_handling.enforce:
        return {}

    owner_targets: dict[str, float] = {}
    for owner, age, alive in (
        (AccountOwner.HUSBAND, period.husband_age, period.husband_alive),
        (AccountOwner.WIFE, period.wife_age, period.wife_alive),
    ):
        if not alive or age < scenario.assumptions.rmd_start_age:
            continue
        factor = scenario.assumptions.rmd_uniform_lifetime_table.get(age)
        if factor is None:
            continue
        owner_balance = sum(
            balances.get(account.name, 0.0)
            for account in _traditional_accounts_for_owner(scenario, owner)
        )
        if owner_balance <= 0:
            continue
        owner_targets[owner.value] = round(min(owner_balance / factor, owner_balance), 2)
    return owner_targets


def _charitable_giving_target(
    scenario: RetirementScenario,
    income: dict[str, float],
    total_rmd: float,
) -> float:
    if not scenario.strategy.charitable_giving.enabled:
        return 0.0

    recurring_income = 0.0
    for source in scenario.strategy.charitable_giving.policy.recurring_sources:
        if source == "social_security":
            recurring_income += income.get("social_security_husband", 0.0)
            recurring_income += income.get("social_security_wife", 0.0)
            continue
        recurring_income += income.get(source, 0.0)

    percent_target = recurring_income * float(
        scenario.strategy.charitable_giving.policy.percent_of_income
    )
    if scenario.strategy.charitable_giving.policy.compare_to == "rmd":
        return round(max(percent_target, total_rmd), 2)
    return round(percent_target, 2)


def _apply_qcd(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    balances: dict[str, float],
    rmd_targets: dict[str, float],
    giving_target: float,
) -> tuple[float, dict[str, float], tuple[str, ...]]:
    qcd = scenario.strategy.charitable_giving.qcd
    if not scenario.strategy.charitable_giving.enabled or not qcd.enabled:
        return 0.0, {}, ()

    qcd_age = ceil(float(qcd.start_age))
    depletion_enabled = qcd.depletion_target.enabled
    depletion_targets = _qcd_depletion_targets(scenario, period, balances, qcd_age)
    owner_floor_targets = _owner_qcd_floor_targets(qcd, depletion_targets, balances, scenario)
    depletion_goal_total = round(sum(owner_floor_targets.values()), 2)
    remaining_limit = round(max(float(qcd.annual_limit) - depletion_goal_total, 0.0), 2)
    remaining_extra_target = 0.0
    if not depletion_enabled:
        remaining_extra_target = min(
            max(giving_target - depletion_goal_total, 0.0), remaining_limit
        )
    total_qcd = 0.0
    qcd_distributions: dict[str, float] = {}
    alerts: list[str] = []
    for owner, age, alive in (
        (AccountOwner.HUSBAND, period.husband_age, period.husband_alive),
        (AccountOwner.WIFE, period.wife_age, period.wife_alive),
    ):
        if not alive or age < qcd_age:
            continue
        applicable_accounts = _qcd_applicable_accounts(scenario, owner)
        owner_available = round(
            sum(balances.get(account.name, 0.0) for account in applicable_accounts),
            2,
        )
        owner_qcd, remaining_extra_target, remaining_limit = _owner_qcd_target(
            qcd,
            owner.value,
            owner_available,
            rmd_targets.get(owner.value, 0.0),
            owner_floor_targets,
            remaining_extra_target,
            remaining_limit,
        )
        if owner_qcd <= 0:
            continue
        owner_qcd_total = _apply_owner_qcd(
            scenario,
            owner,
            balances,
            applicable_accounts,
            owner_qcd,
            rmd_targets,
            qcd,
            qcd_distributions,
        )
        if owner_qcd_total <= 0:
            continue
        total_qcd += owner_qcd_total
    if depletion_goal_total > total_qcd:
        alerts.append(
            f"QCD depletion target fell short by {depletion_goal_total - total_qcd:.2f} this year because annual-limit or IRA-balance constraints prevented staying on the age-{qcd.depletion_target.target_age} giving glidepath."
        )
    return round(total_qcd, 2), _rounded_values(qcd_distributions), tuple(alerts)


def _qcd_applicable_accounts(scenario: RetirementScenario, owner: AccountOwner) -> list[Account]:
    qcd_types = set(scenario.strategy.charitable_giving.qcd.applies_to)
    return [
        account
        for account in _traditional_accounts_for_owner(scenario, owner)
        if account.type in qcd_types
    ]


def _owner_qcd_target(
    qcd,
    owner_key: str,
    owner_available: float,
    owner_rmd: float,
    owner_floor_targets: dict[str, float],
    remaining_extra_target: float,
    remaining_limit: float,
) -> tuple[float, float, float]:
    if owner_available <= 0:
        return 0.0, remaining_extra_target, remaining_limit

    owner_floor = min(owner_floor_targets.get(owner_key, 0.0), owner_available)
    owner_cap = owner_available if qcd.allow_above_rmd else owner_rmd
    if owner_cap <= 0 and owner_floor <= 0:
        return 0.0, remaining_extra_target, remaining_limit

    owner_qcd = owner_floor
    additional_capacity = round(max(min(owner_cap, owner_available) - owner_floor, 0.0), 2)
    if additional_capacity <= 0 or remaining_extra_target <= 0 or remaining_limit <= 0:
        return owner_qcd, remaining_extra_target, remaining_limit

    additional_qcd = min(additional_capacity, remaining_extra_target, remaining_limit)
    owner_qcd = round(owner_qcd + additional_qcd, 2)
    remaining_extra_target = round(max(remaining_extra_target - additional_qcd, 0.0), 2)
    remaining_limit = round(max(remaining_limit - additional_qcd, 0.0), 2)
    return owner_qcd, remaining_extra_target, remaining_limit


def _owner_qcd_floor_targets(
    qcd,
    depletion_targets: dict[str, float],
    balances: dict[str, float],
    scenario: RetirementScenario,
) -> dict[str, float]:
    if not depletion_targets:
        return {}

    capped_targets = {
        owner_key: min(
            target_amount,
            sum(
                balances.get(account.name, 0.0)
                for account in _qcd_applicable_accounts(scenario, AccountOwner(owner_key))
            ),
        )
        for owner_key, target_amount in depletion_targets.items()
    }
    total_target = round(sum(capped_targets.values()), 2)
    annual_limit = float(qcd.annual_limit)
    if total_target <= annual_limit or total_target <= 0:
        return {key: round(value, 2) for key, value in capped_targets.items()}

    scale = annual_limit / total_target
    return {key: round(value * scale, 2) for key, value in capped_targets.items()}


def _apply_owner_qcd(
    scenario: RetirementScenario,
    owner: AccountOwner,
    balances: dict[str, float],
    applicable_accounts: list[Account],
    owner_qcd: float,
    rmd_targets: dict[str, float],
    qcd,
    qcd_distributions: dict[str, float],
) -> float:
    owner_rmd = rmd_targets.get(owner.value, 0.0)
    qcd_withdrawals = _withdraw_from_accounts(
        applicable_accounts,
        balances,
        owner_qcd,
    )
    owner_qcd_total = round(sum(qcd_withdrawals.values()), 2)
    if owner_qcd_total <= 0:
        return 0.0

    _merge_amounts(qcd_distributions, qcd_withdrawals)
    if (
        qcd.tax_treatment.reduces_rmd
        and scenario.strategy.withdrawals.rmd_handling.allow_qcd_to_satisfy_rmd
    ):
        rmd_targets[owner.value] = round(max(owner_rmd - owner_qcd_total, 0.0), 2)
    return owner_qcd_total


def _qcd_depletion_targets(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    balances: dict[str, float],
    qcd_age: int,
) -> dict[str, float]:
    config = scenario.strategy.charitable_giving.qcd.depletion_target
    if not config.enabled:
        return {}

    targets: dict[str, float] = {}
    for owner, age, alive in (
        (AccountOwner.HUSBAND, period.husband_age, period.husband_alive),
        (AccountOwner.WIFE, period.wife_age, period.wife_alive),
    ):
        if owner not in config.owners or not alive or age < qcd_age:
            continue
        applicable_accounts = [
            account
            for account in _traditional_accounts_for_owner(scenario, owner)
            if account.type in set(scenario.strategy.charitable_giving.qcd.applies_to)
        ]
        owner_balance = round(
            sum(balances.get(account.name, 0.0) for account in applicable_accounts), 2
        )
        if owner_balance <= config.target_balance:
            continue

        owner_target_age = _qcd_owner_target_age(scenario, owner, int(config.target_age))
        periods_remaining = max(owner_target_age - age + 1, 1)
        expected_return = _weighted_expected_return(
            scenario,
            period.year,
            balances,
            applicable_accounts,
        )
        target_amount = _level_annual_beginning_withdrawal(
            owner_balance,
            float(config.target_balance),
            expected_return,
            periods_remaining,
        )
        targets[owner.value] = round(min(owner_balance, target_amount), 2)
    return targets


def _qcd_owner_target_age(
    scenario: RetirementScenario,
    owner: AccountOwner,
    configured_target_age: int,
) -> int:
    if owner == AccountOwner.HUSBAND:
        person = scenario.household.husband
    elif owner == AccountOwner.WIFE:
        person = scenario.household.wife
    else:
        return configured_target_age

    modeled_death = person.modeled_death
    if not modeled_death.enabled or modeled_death.death_year is None:
        return configured_target_age

    death_age = modeled_death.death_year - person.birth_year
    return min(configured_target_age, death_age)


def _weighted_expected_return(
    scenario: RetirementScenario,
    year: int,
    balances: dict[str, float],
    accounts: list[Account],
) -> float:
    total_balance = sum(balances.get(account.name, 0.0) for account in accounts)
    if total_balance <= 0:
        return float(scenario.assumptions.investment_return_default)

    weighted_return = 0.0
    for account in accounts:
        balance = balances.get(account.name, 0.0)
        if balance <= 0:
            continue
        weighted_return += (balance / total_balance) * fixed_account_return_for_year(
            account, year, scenario
        )
    return weighted_return


def _level_annual_beginning_withdrawal(
    present_value: float,
    target_value: float,
    annual_return: float,
    periods: int,
) -> float:
    if periods <= 0:
        return max(present_value - target_value, 0.0)
    if annual_return == 0:
        return max((present_value - target_value) / periods, 0.0)

    growth_factor = (1.0 + annual_return) ** periods
    annuity_due_factor = (1.0 + annual_return) * ((growth_factor - 1.0) / annual_return)
    if annuity_due_factor <= 0:
        return max(present_value - target_value, 0.0)
    return max((present_value * growth_factor - target_value) / annuity_due_factor, 0.0)


def project_qcd_depletion_progress(
    scenario: RetirementScenario,
    *,
    year: int,
    husband_age: int,
    wife_age: int,
    husband_alive: bool,
    wife_alive: bool,
    account_balances_end: dict[str, float],
    qcd_distributions: dict[str, float],
    alerts: tuple[str, ...],
) -> tuple[QCDDepletionOwnerProgress, ...]:
    qcd = scenario.strategy.charitable_giving.qcd
    if not qcd.enabled or not qcd.depletion_target.enabled:
        return ()

    qcd_age = ceil(float(qcd.start_age))
    constrained = any("QCD depletion target fell short" in alert for alert in alerts)
    owner_rows: list[QCDDepletionOwnerProgress] = []
    for owner, age, alive in (
        (AccountOwner.HUSBAND, husband_age, husband_alive),
        (AccountOwner.WIFE, wife_age, wife_alive),
    ):
        if owner not in qcd.depletion_target.owners:
            continue

        applicable_accounts = _qcd_applicable_accounts(scenario, owner)
        current_balance = round(
            sum(account_balances_end.get(account.name, 0.0) for account in applicable_accounts),
            2,
        )
        actual_qcd = round(
            sum(qcd_distributions.get(account.name, 0.0) for account in applicable_accounts),
            2,
        )
        owner_target_age = _qcd_owner_target_age(
            scenario,
            owner,
            int(qcd.depletion_target.target_age),
        )
        if not alive:
            owner_rows.append(
                QCDDepletionOwnerProgress(
                    owner=owner.value,
                    target_age=owner_target_age,
                    current_balance=current_balance,
                    annual_qcd_required=0.0,
                    actual_qcd=actual_qcd,
                    projected_balance_at_target_age=0.0,
                    on_pace=True,
                    constrained=constrained,
                )
            )
            continue

        periods_remaining = max(owner_target_age - age, 0)
        annual_qcd_required = 0.0
        projected_balance = current_balance
        if (
            age >= qcd_age
            and periods_remaining > 0
            and current_balance > qcd.depletion_target.target_balance
        ):
            expected_return = _weighted_expected_return(
                scenario,
                year,
                account_balances_end,
                applicable_accounts,
            )
            annual_qcd_required = _level_annual_beginning_withdrawal(
                current_balance,
                float(qcd.depletion_target.target_balance),
                expected_return,
                periods_remaining,
            )
            projected_balance = _project_balance_after_beginning_withdrawals(
                current_balance,
                actual_qcd,
                expected_return,
                periods_remaining,
            )

        projected_balance = round(max(projected_balance, 0.0), 2)
        owner_rows.append(
            QCDDepletionOwnerProgress(
                owner=owner.value,
                target_age=owner_target_age,
                current_balance=round(current_balance, 2),
                annual_qcd_required=round(annual_qcd_required, 2),
                actual_qcd=actual_qcd,
                projected_balance_at_target_age=projected_balance,
                on_pace=projected_balance <= float(qcd.depletion_target.target_balance) + 1.0,
                constrained=constrained,
            )
        )

    return tuple(owner_rows)


def _project_balance_after_beginning_withdrawals(
    present_value: float,
    annual_withdrawal: float,
    annual_return: float,
    periods: int,
) -> float:
    balance = present_value
    for _ in range(periods):
        balance = max(balance - annual_withdrawal, 0.0)
        balance *= 1.0 + annual_return
    return balance


def _execute_roth_conversions(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    income: dict[str, float],
    filing_status: str,
    balances: dict[str, float],
    cash_withdrawals: dict[str, float],
    alerts: list[str],
) -> float:
    config = scenario.strategy.roth_conversions
    if not config.enabled or not period.husband_alive:
        return 0.0
    if period.husband_age not in config.base_policy.active_ages:
        return 0.0

    available = _available_traditional_balance(scenario, balances)
    candidate = _initial_conversion_candidate(scenario, period, income, balances, available)
    if candidate <= 0:
        return 0.0

    candidate, minimum_floor = _apply_conversion_target_controls(
        scenario,
        period,
        available,
        candidate,
        alerts,
    )
    if candidate <= 0:
        return 0.0

    constrained = _cap_conversion_by_constraints(
        scenario,
        period,
        filing_status,
        income,
        cash_withdrawals,
        candidate,
        minimum_floor,
    )
    if constrained < candidate:
        alerts.append(
            f"Reduced Roth conversion from {candidate:.2f} to {constrained:.2f} because of tax or IRMAA guardrails."
        )
    if constrained <= 0:
        return 0.0

    moved_total = _execute_household_roth_conversion(scenario, balances, constrained)
    if moved_total <= 0:
        return 0.0

    return moved_total


def _fund_conversion_tax_payment(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    filing_status: str,
    income: dict[str, float],
    roth_conversion_total: float,
    balances: dict[str, float],
    cash_withdrawals: dict[str, float],
    alerts: list[str],
) -> tuple[float, float]:
    config = scenario.strategy.roth_conversions.tax_payment
    if roth_conversion_total <= 0 or not config.enabled or not config.prioritize_tax_use_first:
        return 0.0, 0.0

    funding_withdrawals: dict[str, float] = {}
    required_tax_payment, _ = _fund_conversion_taxes_from_accounts(
        scenario,
        period,
        filing_status,
        income,
        roth_conversion_total,
        balances,
        cash_withdrawals,
        funding_withdrawals,
        _configured_conversion_tax_payment_accounts(scenario),
    )

    if config.allow_roth_for_conversion_taxes:
        required_tax_payment, roth_funding = _fund_conversion_taxes_from_accounts(
            scenario,
            period,
            filing_status,
            income,
            roth_conversion_total,
            balances,
            cash_withdrawals,
            funding_withdrawals,
            _roth_tax_payment_accounts(scenario),
        )
        roth_total = round(sum(roth_funding.values()), 2)
        if roth_total > 0:
            alerts.append(
                f"Funded {roth_total:.2f} of conversion taxes from Roth assets after configured tax-payment sources were exhausted."
            )

    if config.gross_up_conversion_if_needed:
        required_tax_payment, gross_up_funding = _fund_conversion_taxes_from_accounts(
            scenario,
            period,
            filing_status,
            income,
            roth_conversion_total,
            balances,
            cash_withdrawals,
            funding_withdrawals,
            _traditional_gross_up_tax_payment_accounts(scenario),
        )
        gross_up_total = round(sum(gross_up_funding.values()), 2)
        if gross_up_total > 0:
            alerts.append(
                f"Grossed up conversion-tax funding with {gross_up_total:.2f} of traditional distributions after configured tax-payment sources were exhausted."
            )

    _merge_amounts(cash_withdrawals, funding_withdrawals)
    funded_total = round(sum(funding_withdrawals.values()), 2)
    shortfall = round(max(required_tax_payment - funded_total, 0.0), 2)
    if shortfall > 0:
        alerts.append(
            f"Unable to pre-fund {shortfall:.2f} of conversion taxes from configured source order."
        )
    return funded_total, shortfall


def _fund_conversion_taxes_from_accounts(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    filing_status: str,
    income: dict[str, float],
    roth_conversion_total: float,
    balances: dict[str, float],
    cash_withdrawals: dict[str, float],
    funding_withdrawals: dict[str, float],
    accounts: list[Account],
) -> tuple[float, dict[str, float]]:
    used_withdrawals: dict[str, float] = {}
    required_tax_payment = _required_conversion_tax_payment(
        scenario,
        period,
        filing_status,
        income,
        cash_withdrawals,
        funding_withdrawals,
        roth_conversion_total,
    )

    for _ in range(6):
        funded_so_far = round(sum(funding_withdrawals.values()), 2)
        additional_need = round(required_tax_payment - funded_so_far, 2)
        if additional_need <= 0.01:
            break

        next_funding = _withdraw_for_amount(accounts, balances, additional_need)
        if not next_funding:
            break
        _merge_amounts(funding_withdrawals, next_funding)
        _merge_amounts(used_withdrawals, next_funding)
        required_tax_payment = _required_conversion_tax_payment(
            scenario,
            period,
            filing_status,
            income,
            cash_withdrawals,
            funding_withdrawals,
            roth_conversion_total,
        )

    return required_tax_payment, used_withdrawals


def _required_conversion_tax_payment(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    filing_status: str,
    income: dict[str, float],
    cash_withdrawals: dict[str, float],
    funding_withdrawals: dict[str, float],
    roth_conversion_total: float,
) -> float:
    method = scenario.strategy.roth_conversions.tax_payment.estimated_tax_method
    projected_withdrawals = dict(cash_withdrawals)
    if method == "incremental":
        _merge_amounts(projected_withdrawals, funding_withdrawals)
        return _estimate_incremental_conversion_tax(
            scenario,
            period,
            filing_status,
            income,
            projected_withdrawals,
            roth_conversion_total,
        )
    return _estimate_conversion_only_tax(
        scenario,
        period,
        filing_status,
        income,
        projected_withdrawals,
        roth_conversion_total,
    )


def _estimate_incremental_conversion_tax(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    filing_status: str,
    income: dict[str, float],
    withdrawals: dict[str, float],
    roth_conversion_total: float,
) -> float:
    with_conversion = calculate_tax_summary(
        scenario,
        filing_status,
        income,
        withdrawals,
        extra_ordinary_income=roth_conversion_total,
        senior_standard_deduction_count=senior_standard_deduction_count(
            filing_status,
            husband_age=period.husband_age,
            wife_age=period.wife_age,
            husband_alive=period.husband_alive,
            wife_alive=period.wife_alive,
        ),
    )
    without_conversion = calculate_tax_summary(
        scenario,
        filing_status,
        income,
        withdrawals,
        extra_ordinary_income=0.0,
        senior_standard_deduction_count=senior_standard_deduction_count(
            filing_status,
            husband_age=period.husband_age,
            wife_age=period.wife_age,
            husband_alive=period.husband_alive,
            wife_alive=period.wife_alive,
        ),
    )
    return round(max(with_conversion.total_tax - without_conversion.total_tax, 0.0), 2)


def _estimate_conversion_only_tax(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    filing_status: str,
    income: dict[str, float],
    withdrawals: dict[str, float],
    roth_conversion_total: float,
) -> float:
    return _estimate_incremental_conversion_tax(
        scenario,
        period,
        filing_status,
        income,
        withdrawals,
        roth_conversion_total,
    )


def _withdraw_for_amount(
    accounts: list[Account],
    balances: dict[str, float],
    required_amount: float,
) -> dict[str, float]:
    funding: dict[str, float] = {}
    remaining = required_amount
    for account in accounts:
        available = balances.get(account.name, 0.0)
        if available <= 0:
            continue
        amount = min(available, remaining)
        balances[account.name] = round(available - amount, 10)
        funding[account.name] = round(funding.get(account.name, 0.0) + amount, 2)
        remaining = round(remaining - amount, 10)
        if remaining <= 0:
            return funding
    return funding


def _configured_conversion_tax_payment_accounts(
    scenario: RetirementScenario,
) -> list[Account]:
    ordered: list[Account] = []
    for source in scenario.strategy.roth_conversions.tax_payment.source_order:
        ordered.extend(_accounts_for_conversion_tax_source(scenario, source))
    return _dedupe_accounts(ordered)


def _accounts_for_conversion_tax_source(
    scenario: RetirementScenario,
    source: str,
) -> list[Account]:
    config = scenario.strategy.roth_conversions.tax_payment
    if source == "taxable_bridge_account":
        return [
            account for account in scenario.accounts if account.name == config.source_account_name
        ]
    if source == "household_operating_cash":
        return [
            account for account in scenario.accounts if account.name == "Household Operating Cash"
        ]
    if source == "taxable":
        return [
            account
            for account in scenario.accounts
            if account.type == AccountType.TAXABLE and account.name != config.source_account_name
        ]
    if source == "cash":
        return [
            account
            for account in scenario.accounts
            if account.type == AccountType.CASH and account.name != "Household Operating Cash"
        ]
    if source == "traditional_distribution":
        return [
            account
            for account in scenario.accounts
            if account.type in {AccountType.TRADITIONAL_IRA, AccountType.TRADITIONAL_401K}
        ]
    return []


def _roth_tax_payment_accounts(scenario: RetirementScenario) -> list[Account]:
    ordered = [
        account
        for account in scenario.accounts
        if account.type in {AccountType.ROTH_IRA, AccountType.ROTH_401K}
        and not _account_unavailable_for_tax_payment(scenario, account)
    ]
    return _dedupe_accounts(ordered)


def _traditional_gross_up_tax_payment_accounts(
    scenario: RetirementScenario,
) -> list[Account]:
    ordered = [
        account
        for account in _traditional_accounts_for_owner(scenario, AccountOwner.HUSBAND)
        if not _account_unavailable_for_tax_payment(scenario, account)
    ]
    return _dedupe_accounts(ordered)


def _account_unavailable_for_tax_payment(
    scenario: RetirementScenario,
    account: Account,
) -> bool:
    restricted_accounts = set(scenario.strategy.withdrawals.restrictions.never_use_accounts)
    return account.name in restricted_accounts or account.withdrawals_enabled is False


def _available_traditional_balance(
    scenario: RetirementScenario,
    balances: dict[str, float],
) -> float:
    return sum(
        balances.get(account.name, 0.0)
        for account in _traditional_accounts_for_owner(scenario, AccountOwner.HUSBAND)
    )


def _initial_conversion_candidate(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    income: dict[str, float],
    balances: dict[str, float],
    available: float,
) -> float:
    config = scenario.strategy.roth_conversions
    candidate = float(config.base_policy.base_conversion_amounts[period.husband_age])
    candidate = _apply_market_adjustments(scenario, period, candidate)
    candidate = _apply_balance_target_adjustments(scenario, candidate, balances)
    if (
        config.social_security_interaction.reduce_after_husband_claim
        and income.get("social_security_husband", 0.0) > 0
    ):
        candidate *= 1.0 - float(config.social_security_interaction.reduction_percent)
    return min(candidate, float(config.safety_limits.max_conversion), available)


def _apply_conversion_target_controls(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    available: float,
    candidate: float,
    alerts: list[str],
) -> tuple[float, float]:
    target_preserving_cap = _target_preserving_conversion_cap(scenario, period, available)
    target_attaining_floor = _target_attaining_conversion_floor(scenario, period, available)
    target_at_risk = target_preserving_cap < float(
        scenario.strategy.roth_conversions.safety_limits.min_conversion.base
    )
    if target_attaining_floor > candidate:
        alerts.append(
            f"Increased Roth conversion from {candidate:.2f} to {target_attaining_floor:.2f} to pursue the traditional balance target at age 70."
        )
        candidate = target_attaining_floor
    if target_preserving_cap < candidate:
        alerts.append(
            f"Reduced Roth conversion from {candidate:.2f} to {target_preserving_cap:.2f} to preserve the traditional balance target at age 70."
        )
        candidate = target_preserving_cap

    minimum_floor = _minimum_conversion_floor(scenario, target_at_risk, alerts)
    if minimum_floor > 0:
        candidate = max(candidate, minimum_floor)
        candidate = min(candidate, available)
    return candidate, minimum_floor


def _apply_market_adjustments(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    amount: float,
) -> float:
    config = scenario.strategy.roth_conversions.market_adjustments
    if not config.enabled:
        return amount

    market_return = account_type_return_for_period(config.signal_account_type, period, scenario)
    for band in config.bands:
        lower_ok = band.lower_return is None or market_return >= float(band.lower_return)
        upper_ok = band.upper_return is None or market_return <= float(band.upper_return)
        if lower_ok and upper_ok:
            return amount * float(band.multiplier)

    adjusted = amount
    for rule in config.rules:
        if rule.condition == "market_drawdown" and market_return <= float(rule.threshold):
            adjusted = _apply_adjustment(adjusted, rule.action, float(rule.adjustment_percent))
        if rule.condition == "strong_market" and market_return >= float(rule.threshold):
            adjusted = _apply_adjustment(adjusted, rule.action, float(rule.adjustment_percent))
    return adjusted


def _apply_balance_target_adjustments(
    scenario: RetirementScenario,
    amount: float,
    balances: dict[str, float],
) -> float:
    config = scenario.strategy.roth_conversions.balance_targets
    if not config.enabled:
        return amount

    husband_traditional_balance = sum(
        balances.get(account.name, 0.0)
        for account in _traditional_accounts_for_owner(scenario, AccountOwner.HUSBAND)
    )
    target = float(config.traditional_ira_target_at_70)
    band = target * float(config.acceptable_band_percent)
    if husband_traditional_balance > target + band:
        rule = config.adjustment_logic.if_above_target
        return _apply_adjustment(amount, rule.action, float(rule.adjustment_percent))
    if husband_traditional_balance < max(target - band, 0.0):
        rule = config.adjustment_logic.if_below_target
        return _apply_adjustment(amount, rule.action, float(rule.adjustment_percent))
    return amount


def _apply_adjustment(amount: float, action: str, percent: float) -> float:
    if action == "increase":
        return amount * (1.0 + percent)
    return amount * max(1.0 - percent, 0.0)


def _cap_conversion_by_constraints(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    filing_status: str,
    income: dict[str, float],
    cash_withdrawals: dict[str, float],
    candidate: float,
    minimum_floor: float,
) -> float:
    config = scenario.strategy.roth_conversions
    if _conversion_allowed(scenario, period, filing_status, income, cash_withdrawals, candidate):
        return round(candidate, 2)
    if not config.tax_constraints.allow_partial_bracket_fill:
        return 0.0

    lower = 0.0
    upper = candidate
    for _ in range(24):
        probe = (lower + upper) / 2
        if _conversion_allowed(scenario, period, filing_status, income, cash_withdrawals, probe):
            lower = probe
        else:
            upper = probe
    if lower < minimum_floor and not config.safety_limits.min_conversion.reduce_if_exceeds_bracket:
        return 0.0
    return round(lower, 2)


def _target_preserving_conversion_cap(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    available: float,
) -> float:
    config = scenario.strategy.roth_conversions.balance_targets
    if not config.enabled:
        return available

    years_until_target = max(70 - period.husband_age, 0)
    projected_return = float(scenario.assumptions.investment_return_default)
    required_balance_now = float(config.traditional_ira_target_at_70) / (
        (1.0 + projected_return) ** years_until_target
    )
    return round(max(available - required_balance_now, 0.0), 2)


def _target_attaining_conversion_floor(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    available: float,
) -> float:
    config = scenario.strategy.roth_conversions.balance_targets
    if not config.enabled:
        return 0.0
    if config.target_priority != "higher_than_min_conversion":
        return 0.0
    return min(
        _target_preserving_conversion_cap(scenario, period, available),
        float(scenario.strategy.roth_conversions.safety_limits.max_conversion),
        available,
    )


def _minimum_conversion_floor(
    scenario: RetirementScenario,
    target_at_risk: bool,
    alerts: list[str],
) -> float:
    config = scenario.strategy.roth_conversions
    minimum_config = config.safety_limits.min_conversion
    if not minimum_config.enforce_only_when_target_not_at_risk:
        return float(minimum_config.base)
    if not target_at_risk:
        return float(minimum_config.base)
    if config.balance_targets.allow_below_min_if_needed_to_hit_target:
        alerts.append(
            "Allowed Roth conversion below the configured minimum to preserve the traditional balance target at age 70."
        )
        return 0.0
    return float(minimum_config.base)


def _conversion_allowed(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    filing_status: str,
    income: dict[str, float],
    cash_withdrawals: dict[str, float],
    conversion_amount: float,
) -> bool:
    summary = calculate_tax_summary(
        scenario,
        filing_status,
        income,
        cash_withdrawals,
        extra_ordinary_income=conversion_amount,
        senior_standard_deduction_count=senior_standard_deduction_count(
            filing_status,
            husband_age=period.husband_age,
            wife_age=period.wife_age,
            husband_alive=period.husband_alive,
            wife_alive=period.wife_alive,
        ),
    )
    max_bracket = float(scenario.strategy.roth_conversions.tax_constraints.max_marginal_bracket)
    if (
        _marginal_rate_for_income(scenario, filing_status, summary.federal_taxable_income)
        > max_bracket
    ):
        return False

    irmaa_controls = scenario.strategy.roth_conversions.irmaa_controls
    if not irmaa_controls.enabled or not irmaa_controls.reduce_if_exceeded:
        return True
    if should_override_irmaa_conversion_guardrails(scenario, period):
        return True
    return _irmaa_tier_for_magi(scenario, filing_status, summary.adjusted_gross_income) <= int(
        irmaa_controls.max_tier
    )


def _marginal_rate_for_income(
    scenario: RetirementScenario,
    filing_status: str,
    taxable_income: float,
) -> float:
    if taxable_income <= 0:
        return 0.0
    brackets = (
        scenario.federal_tax.brackets.single
        if filing_status == "single"
        else scenario.federal_tax.brackets.mfj
    )
    for bracket in brackets:
        if bracket.up_to is None or taxable_income <= float(bracket.up_to):
            return float(bracket.rate)
    return float(brackets[-1].rate)


def _irmaa_tier_for_magi(scenario: RetirementScenario, filing_status: str, magi: float) -> int:
    tiers = (
        scenario.medicare.irmaa.single if filing_status == "single" else scenario.medicare.irmaa.mfj
    )
    for index, tier in enumerate(tiers):
        if tier.magi_up_to is None or magi <= float(tier.magi_up_to):
            return index
    return len(tiers) - 1


def _traditional_accounts_for_owner(
    scenario: RetirementScenario,
    owner: AccountOwner,
) -> list[Account]:
    ordered: list[Account] = []
    for account_type in (AccountType.TRADITIONAL_IRA, AccountType.TRADITIONAL_401K):
        ordered.extend(
            account
            for account in scenario.accounts
            if account.owner == owner and account.type == account_type
        )
    return ordered


def _roth_accounts_for_owner(
    scenario: RetirementScenario,
    owner: AccountOwner,
) -> list[Account]:
    ordered: list[Account] = []
    for account_type in (AccountType.ROTH_IRA, AccountType.ROTH_401K):
        ordered.extend(
            account
            for account in scenario.accounts
            if account.owner == owner and account.type == account_type
        )
    return ordered


def _withdraw_from_accounts(
    accounts: list[Account],
    balances: dict[str, float],
    required_amount: float,
) -> dict[str, float]:
    withdrawals: dict[str, float] = {}
    remaining = required_amount
    for account in accounts:
        available = balances.get(account.name, 0.0)
        if available <= 0:
            continue
        amount = min(available, remaining)
        balances[account.name] = round(available - amount, 10)
        withdrawals[account.name] = round(withdrawals.get(account.name, 0.0) + amount, 2)
        remaining = round(remaining - amount, 10)
        if remaining <= 0:
            break
    return withdrawals


def _execute_household_roth_conversion(
    scenario: RetirementScenario,
    balances: dict[str, float],
    required_amount: float,
) -> float:
    remaining = required_amount
    converted_by_owner: dict[AccountOwner, float] = {}
    for owner in (AccountOwner.WIFE, AccountOwner.HUSBAND):
        if remaining <= 0:
            break
        owner_withdrawals = _withdraw_from_accounts(
            _traditional_accounts_for_owner(scenario, owner),
            balances,
            remaining,
        )
        owner_total = round(sum(owner_withdrawals.values()), 2)
        if owner_total <= 0:
            continue
        converted_by_owner[owner] = owner_total
        remaining = round(remaining - owner_total, 10)

    moved_total = round(sum(converted_by_owner.values()), 2)
    if moved_total <= 0:
        return 0.0

    for owner, amount in converted_by_owner.items():
        _deposit_to_roth_accounts(scenario, owner, balances, amount)
    return moved_total


def _deposit_to_roth_accounts(
    scenario: RetirementScenario,
    owner: AccountOwner,
    balances: dict[str, float],
    amount: float,
) -> None:
    roth_accounts = _roth_accounts_for_owner(scenario, owner)
    if not roth_accounts:
        return
    balances[roth_accounts[0].name] += amount


def _merge_amounts(target: dict[str, float], source: dict[str, float]) -> None:
    for key, value in source.items():
        target[key] = round(target.get(key, 0.0) + value, 2)


def _rounded_values(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 2) for key, value in values.items()}


def _dedupe_accounts(accounts: list[Account]) -> list[Account]:
    seen: set[str] = set()
    ordered: list[Account] = []
    for account in accounts:
        if account.name in seen:
            continue
        seen.add(account.name)
        ordered.append(account)
    return ordered

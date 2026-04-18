"""Stage 7 planned withdrawals, conversions, RMDs, and QCD execution."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from retireplan.core.account_flow import annual_return_for_year
from retireplan.core.timeline_builder import TimelinePeriod
from retireplan.scenario import Account, AccountOwner, AccountType, RetirementScenario
from retireplan.tax import TaxSummary, calculate_tax_summary


@dataclass(frozen=True)
class StrategyExecution:
    cash_withdrawals: dict[str, float]
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


def execute_strategy(
    scenario: RetirementScenario,
    period: TimelinePeriod,
    income: dict[str, float],
    filing_status: str,
    balances: dict[str, float],
) -> StrategyExecution:
    alerts: list[str] = []
    cash_withdrawals: dict[str, float] = {}

    rmd_targets = _rmd_targets(scenario, period, balances)
    total_rmd = round(sum(rmd_targets.values()), 2)

    giving_target = _charitable_giving_target(scenario, income, total_rmd)
    qcd_total = _apply_qcd(scenario, period, balances, rmd_targets, giving_target)
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
        filing_status,
        income,
        roth_conversion_total,
        balances,
        cash_withdrawals,
        alerts,
    )

    return StrategyExecution(
        cash_withdrawals=_rounded_values(cash_withdrawals),
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
) -> float:
    qcd = scenario.strategy.charitable_giving.qcd
    if not scenario.strategy.charitable_giving.enabled or not qcd.enabled:
        return 0.0

    qcd_age = ceil(float(qcd.start_age))
    remaining_giving = min(giving_target, float(qcd.annual_limit))
    total_qcd = 0.0
    for owner, age, alive in (
        (AccountOwner.HUSBAND, period.husband_age, period.husband_alive),
        (AccountOwner.WIFE, period.wife_age, period.wife_alive),
    ):
        if not alive or age < qcd_age or remaining_giving <= 0:
            continue
        owner_rmd = rmd_targets.get(owner.value, 0.0)
        if owner_rmd <= 0:
            continue

        owner_qcd = min(owner_rmd, remaining_giving)
        qcd_withdrawals = _withdraw_from_accounts(
            [
                account
                for account in _traditional_accounts_for_owner(scenario, owner)
                if account.type in set(qcd.applies_to)
            ],
            balances,
            owner_qcd,
        )
        owner_qcd_total = round(sum(qcd_withdrawals.values()), 2)
        if owner_qcd_total <= 0:
            continue

        if (
            qcd.tax_treatment.reduces_rmd
            and scenario.strategy.withdrawals.rmd_handling.allow_qcd_to_satisfy_rmd
        ):
            rmd_targets[owner.value] = round(max(owner_rmd - owner_qcd_total, 0.0), 2)
        total_qcd += owner_qcd_total
        remaining_giving = round(max(remaining_giving - owner_qcd_total, 0.0), 2)
    return round(total_qcd, 2)


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

    conversion_withdrawals = _withdraw_from_accounts(
        _traditional_accounts_for_owner(scenario, AccountOwner.HUSBAND),
        balances,
        constrained,
    )
    moved_total = round(sum(conversion_withdrawals.values()), 2)
    if moved_total <= 0:
        return 0.0

    _deposit_to_roth_accounts(scenario, AccountOwner.HUSBAND, balances, moved_total)
    return moved_total


def _fund_conversion_tax_payment(
    scenario: RetirementScenario,
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
            filing_status,
            income,
            cash_withdrawals,
            funding_withdrawals,
            roth_conversion_total,
        )

    return required_tax_payment, used_withdrawals


def _required_conversion_tax_payment(
    scenario: RetirementScenario,
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
            filing_status,
            income,
            projected_withdrawals,
            roth_conversion_total,
        )
    return _estimate_conversion_only_tax(
        scenario,
        filing_status,
        income,
        projected_withdrawals,
        roth_conversion_total,
    )


def _estimate_incremental_conversion_tax(
    scenario: RetirementScenario,
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
    )
    without_conversion = calculate_tax_summary(
        scenario,
        filing_status,
        income,
        withdrawals,
        extra_ordinary_income=0.0,
    )
    return round(max(with_conversion.total_tax - without_conversion.total_tax, 0.0), 2)


def _estimate_conversion_only_tax(
    scenario: RetirementScenario,
    filing_status: str,
    income: dict[str, float],
    withdrawals: dict[str, float],
    roth_conversion_total: float,
) -> float:
    return _estimate_incremental_conversion_tax(
        scenario,
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
    target_at_risk = target_preserving_cap < float(
        scenario.strategy.roth_conversions.safety_limits.min_conversion.base
    )
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

    market_return = annual_return_for_year(scenario.accounts[0], period.year, scenario)
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
    filing_status: str,
    income: dict[str, float],
    cash_withdrawals: dict[str, float],
    candidate: float,
    minimum_floor: float,
) -> float:
    config = scenario.strategy.roth_conversions
    if _conversion_allowed(scenario, filing_status, income, cash_withdrawals, candidate):
        return round(candidate, 2)
    if not config.tax_constraints.allow_partial_bracket_fill:
        return 0.0

    lower = 0.0
    upper = candidate
    for _ in range(24):
        probe = (lower + upper) / 2
        if _conversion_allowed(scenario, filing_status, income, cash_withdrawals, probe):
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

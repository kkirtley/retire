"""Stage 3 federal and generic state income tax calculations."""

from __future__ import annotations

from dataclasses import dataclass

from retireplan.scenario import AccountType, RetirementScenario

_MFJ = "mfj"
_SINGLE = "single"


@dataclass(frozen=True)
class TaxSummary:
    ordinary_income: float
    social_security_benefits: float
    taxable_social_security: float
    adjusted_gross_income: float
    standard_deduction: float
    federal_taxable_income: float
    federal_tax: float
    state_taxable_income: float
    state_tax: float
    total_tax: float

    def ledger_values(self) -> dict[str, float]:
        return {
            "federal": self.federal_tax,
            "state": self.state_tax,
            "total": self.total_tax,
        }


def calculate_tax_summary(
    scenario: RetirementScenario,
    filing_status: str,
    income: dict[str, float],
    withdrawals: dict[str, float],
) -> TaxSummary:
    ordinary_income = round(
        income.get("earned_income_husband", 0.0)
        + income.get("earned_income_wife", 0.0)
        + income.get("pension_income", 0.0)
        + _traditional_withdrawals(scenario, withdrawals),
        2,
    )
    social_security_benefits = round(
        income.get("social_security_husband", 0.0) + income.get("social_security_wife", 0.0),
        2,
    )
    taxable_social_security = round(
        _taxable_social_security(filing_status, ordinary_income, social_security_benefits),
        2,
    )
    adjusted_gross_income = round(ordinary_income + taxable_social_security, 2)
    standard_deduction = round(_standard_deduction(scenario, filing_status), 2)
    federal_taxable_income = round(max(adjusted_gross_income - standard_deduction, 0.0), 2)
    federal_tax = round(_federal_tax(scenario, filing_status, federal_taxable_income), 2)
    state_taxable_income = round(
        _state_taxable_income(
            scenario,
            federal_taxable_income=federal_taxable_income,
        ),
        2,
    )
    state_tax = round(_state_tax(scenario, state_taxable_income), 2)
    total_tax = round(federal_tax + state_tax, 2)

    return TaxSummary(
        ordinary_income=ordinary_income,
        social_security_benefits=social_security_benefits,
        taxable_social_security=taxable_social_security,
        adjusted_gross_income=adjusted_gross_income,
        standard_deduction=standard_deduction,
        federal_taxable_income=federal_taxable_income,
        federal_tax=federal_tax,
        state_taxable_income=state_taxable_income,
        state_tax=state_tax,
        total_tax=total_tax,
    )


def _traditional_withdrawals(
    scenario: RetirementScenario,
    withdrawals: dict[str, float],
) -> float:
    account_types = {account.name: account.type for account in scenario.accounts}
    taxable_types = {AccountType.TRADITIONAL_IRA, AccountType.TRADITIONAL_401K}
    return sum(
        amount
        for account_name, amount in withdrawals.items()
        if account_types.get(account_name) in taxable_types
    )


def _taxable_social_security(
    filing_status: str,
    ordinary_income: float,
    social_security_benefits: float,
) -> float:
    if social_security_benefits <= 0:
        return 0.0

    base_threshold, upper_threshold, tier_cap = _social_security_thresholds(filing_status)
    provisional_income = ordinary_income + 0.5 * social_security_benefits

    if provisional_income <= base_threshold:
        return 0.0
    if provisional_income <= upper_threshold:
        return min(0.5 * (provisional_income - base_threshold), 0.5 * social_security_benefits)

    return min(
        0.85 * social_security_benefits,
        0.85 * (provisional_income - upper_threshold)
        + min(tier_cap, 0.5 * social_security_benefits),
    )


def _social_security_thresholds(filing_status: str) -> tuple[float, float, float]:
    if filing_status == _SINGLE:
        return 25000.0, 34000.0, 4500.0
    return 32000.0, 44000.0, 6000.0


def _standard_deduction(scenario: RetirementScenario, filing_status: str) -> float:
    if filing_status == _SINGLE:
        return float(scenario.federal_tax.standard_deduction.single)
    return float(scenario.federal_tax.standard_deduction.mfj)


def _federal_tax(scenario: RetirementScenario, filing_status: str, taxable_income: float) -> float:
    if taxable_income <= 0:
        return 0.0

    brackets = (
        scenario.federal_tax.brackets.single
        if filing_status == _SINGLE
        else scenario.federal_tax.brackets.mfj
    )

    tax = 0.0
    lower_bound = 0.0
    for bracket in brackets:
        upper_bound = (
            taxable_income if bracket.up_to is None else min(taxable_income, bracket.up_to)
        )
        if upper_bound <= lower_bound:
            continue
        tax += (upper_bound - lower_bound) * float(bracket.rate)
        if bracket.up_to is None or taxable_income <= bracket.up_to:
            break
        lower_bound = float(bracket.up_to)

    return tax


def _state_taxable_income(
    scenario: RetirementScenario,
    federal_taxable_income: float,
) -> float:
    if scenario.state_tax.taxable_income_basis == "federal_taxable_income":
        return federal_taxable_income
    raise ValueError(f"Unsupported state tax basis: {scenario.state_tax.taxable_income_basis}")


def _state_tax(scenario: RetirementScenario, state_taxable_income: float) -> float:
    if scenario.state_tax.model == "none":
        return 0.0
    if scenario.state_tax.model == "effective_rate":
        return state_taxable_income * float(scenario.state_tax.effective_rate or 0.0)
    raise ValueError(f"Unsupported state tax model: {scenario.state_tax.model}")

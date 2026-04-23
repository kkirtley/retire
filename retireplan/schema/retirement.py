from __future__ import annotations

from datetime import date
from enum import Enum
from itertools import pairwise
from math import ceil
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ============================================================
# Enums
# ============================================================


class Currency(str, Enum):
    USD = "USD"


class Cadence(str, Enum):
    ANNUAL = "annual"


class ProrationMethod(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"


class ObjectMergeRule(str, Enum):
    DEEP_MERGE = "deep_merge"


class ListMergeRule(str, Enum):
    REPLACE_UNLESS_KEYED = "replace_unless_keyed"


class FilingStatus(str, Enum):
    MFJ = "mfj"


class StateTaxModel(str, Enum):
    NONE = "none"
    EFFECTIVE_RATE = "effective_rate"


class StateTaxableIncomeBasis(str, Enum):
    FEDERAL_TAXABLE_INCOME = "federal_taxable_income"


class IncomeType(str, Enum):
    W2 = "w2"
    FORM_1099 = "1099"


class AccountType(str, Enum):
    TRADITIONAL_IRA = "traditional_ira"
    TRADITIONAL_401K = "traditional_401k"
    ROTH_IRA = "roth_ira"
    ROTH_401K = "roth_401k"
    HSA = "hsa"
    CASH = "cash"
    RESTRICTED_CASH = "restricted_cash"
    TAXABLE = "taxable"


class AccountOwner(str, Enum):
    HUSBAND = "Husband"
    WIFE = "Wife"
    HOUSEHOLD = "Household"


class ContributionType(str, Enum):
    PERCENT_OF_SALARY = "percent_of_salary"
    FIXED_MONTHLY = "fixed_monthly"
    FIXED_ANNUAL = "fixed_annual"


class SpendingGuardrailTrigger(str, Enum):
    RESOURCE_PRESSURE = "resource_pressure"


class PaymentFrequency(str, Enum):
    MONTHLY = "monthly"


class MortgagePayoffMethod(str, Enum):
    COMPUTE_EXTRA_PRINCIPAL = "compute_extra_principal"


class ConversionTaxTreatment(str, Enum):
    ANNUAL_CASH_OUTFLOW_SAME_YEAR = "annual_cash_outflow_same_year"


class ConversionStrategy(str, Enum):
    ADAPTIVE_LADDER = "adaptive_ladder"


class HistoricalDataset(str, Enum):
    DAMODARAN_US_ANNUAL_1970_2025 = "damodaran_us_annual_1970_2025"


class HistoricalWeightingMethod(str, Enum):
    EQUAL = "equal"
    MODERN_HEAVIER = "modern_heavier"


class MarketCondition(str, Enum):
    MARKET_DRAWDOWN = "market_drawdown"
    STRONG_MARKET = "strong_market"


class AdjustmentAction(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"


class TargetPriority(str, Enum):
    HIGHER_THAN_MIN_CONVERSION = "higher_than_min_conversion"


class MinConversionType(str, Enum):
    FLOOR_WITH_TAX_GUARD = "floor_with_tax_guard"


class ConversionTaxPaymentTiming(str, Enum):
    SAME_YEAR = "same_year"


class EstimatedTaxMethod(str, Enum):
    INCREMENTAL = "incremental"


class LifeChangingEvent(str, Enum):
    WORK_STOPPAGE = "work_stoppage"
    WORK_REDUCTION = "work_reduction"
    CONVERSION_ONLY = "conversion_only"


class ConversionTaxSource(str, Enum):
    TAXABLE_BRIDGE_ACCOUNT = "taxable_bridge_account"
    HOUSEHOLD_OPERATING_CASH = "household_operating_cash"
    TAXABLE = "taxable"
    TRADITIONAL_DISTRIBUTION = "traditional_distribution"
    CASH = "cash"


class GivingPolicyType(str, Enum):
    GREATER_OF = "greater_of"


class GivingCompareTo(str, Enum):
    RMD = "rmd"


class GivingIncomeDefinition(str, Enum):
    RECURRING_SOURCES_ONLY = "recurring_sources_only"


class IRAInsufficientAction(str, Enum):
    SKIP_EXCESS_GIVING = "skip_excess_giving"


class WithdrawalOrderType(str, Enum):
    HOUSEHOLD_OPERATING_CASH = "household_operating_cash"
    TAXABLE_BRIDGE_ACCOUNT = "taxable_bridge_account"
    TRADITIONAL_IRA = "traditional_ira"
    TRADITIONAL_401K = "traditional_401k"
    ROTH_IRA = "roth_ira"
    ROTH_401K = "roth_401k"


# ============================================================
# Base
# ============================================================


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


RESTRICTED_RETIREMENT_CASHFLOW_POLICY = "never_use_for_retirement_model_cashflows"
BRIDGE_ACCOUNT_NAME = "Taxable Bridge Account"
HOUSEHOLD_OPERATING_CASH_ACCOUNT_NAME = "Household Operating Cash"


# ============================================================
# Common helpers
# ============================================================


class ReturnScheduleEntry(StrictBaseModel):
    start_date: date
    annual_rate: float = Field(ge=0.0, le=1.0)
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ReturnScheduleEntry":
        if self.end_date is not None and self.end_date <= self.start_date:
            raise ValueError("return schedule end_date must be after start_date")
        return self


class MergeRules(StrictBaseModel):
    object_merge: ObjectMergeRule
    list_merge: ListMergeRule


class ValidationConfig(StrictBaseModel):
    strict: bool
    override_merge_rules: MergeRules


# ============================================================
# Metadata / Simulation / Assumptions
# ============================================================


class Metadata(StrictBaseModel):
    scenario_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    created: date
    currency: Currency
    cadence: Cadence


class EndCondition(StrictBaseModel):
    wife_age: int = Field(ge=80)


class ProrationConfig(StrictBaseModel):
    enabled: bool
    method: ProrationMethod


class Simulation(StrictBaseModel):
    start_date: date
    retirement_date: date
    end_condition: EndCondition
    proration: ProrationConfig

    @model_validator(mode="after")
    def validate_dates(self) -> "Simulation":
        if self.start_date >= self.retirement_date:
            raise ValueError(
                "simulation.start_date must be earlier than simulation.retirement_date"
            )
        return self


class Assumptions(StrictBaseModel):
    inflation_rate: float = Field(ge=0.0, le=1.0)
    investment_return_default: float = Field(ge=0.0, le=1.0)
    success_age: int = Field(ge=90)
    ss_cola: float = Field(ge=0.0, le=1.0)
    va_cola: float = Field(ge=0.0, le=1.0)
    rmd_start_age: int
    rmd_uniform_lifetime_table: Dict[int, float]

    @field_validator("rmd_start_age")
    @classmethod
    def validate_rmd_start_age(cls, value: int) -> int:
        if value not in {73, 75}:
            raise ValueError("rmd_start_age must be 73 or 75")
        return value

    @field_validator("rmd_uniform_lifetime_table")
    @classmethod
    def validate_rmd_uniform_lifetime_table(cls, table: Dict[int, float]) -> Dict[int, float]:
        if not table:
            raise ValueError("rmd_uniform_lifetime_table must not be empty")

        previous_age = -1
        previous_factor: float | None = None
        for age in sorted(table):
            factor = table[age]
            if age < 0:
                raise ValueError("rmd_uniform_lifetime_table ages must be non-negative")
            if factor <= 0:
                raise ValueError("rmd_uniform_lifetime_table factors must be positive")
            if age <= previous_age:
                raise ValueError("rmd_uniform_lifetime_table ages must be strictly increasing")
            if previous_factor is not None and factor >= previous_factor:
                raise ValueError(
                    "rmd_uniform_lifetime_table factors must decrease as ages increase"
                )
            previous_age = age
            previous_factor = factor
        return table

    @model_validator(mode="after")
    def validate_rmd_config(self) -> "Assumptions":
        if self.rmd_start_age not in self.rmd_uniform_lifetime_table:
            raise ValueError("rmd_uniform_lifetime_table must include the configured rmd_start_age")
        return self


# ============================================================
# Historical market analysis
# ============================================================


class HistoricalWeighting(StrictBaseModel):
    method: HistoricalWeightingMethod = HistoricalWeightingMethod.EQUAL
    modern_start_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    modern_weight_multiplier: float = Field(default=1.0, ge=1.0)

    @model_validator(mode="after")
    def validate_modern_bias(self) -> "HistoricalWeighting":
        if (
            self.method == HistoricalWeightingMethod.MODERN_HEAVIER
            and self.modern_start_year is None
        ):
            raise ValueError(
                "historical_analysis.weighting.modern_start_year is required for modern_heavier weighting"
            )
        return self


class AssetAllocation(StrictBaseModel):
    stocks: float = Field(ge=0.0, le=1.0)
    bonds: float = Field(ge=0.0, le=1.0)
    cash: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "AssetAllocation":
        total = self.stocks + self.bonds + self.cash
        if abs(total - 1.0) > 1e-6:
            raise ValueError("asset allocation weights must sum to 1.0")
        return self


class GlidePathBand(StrictBaseModel):
    start_age: int = Field(ge=0)
    end_age: int = Field(ge=0)
    allocation: AssetAllocation

    @model_validator(mode="after")
    def validate_age_range(self) -> "GlidePathBand":
        if self.end_age < self.start_age:
            raise ValueError("glide path band end_age must be on or after start_age")
        return self


class AccountTypeHistoricalPolicy(StrictBaseModel):
    glide_path: List[GlidePathBand]

    @model_validator(mode="after")
    def validate_glide_path(self) -> "AccountTypeHistoricalPolicy":
        sorted_bands = sorted(self.glide_path, key=lambda band: band.start_age)
        for previous, current in pairwise(sorted_bands):
            if previous.end_age >= current.start_age:
                raise ValueError("historical glide path bands may not overlap")
        return self


class MarketAdjustmentBand(StrictBaseModel):
    lower_return: Optional[float] = None
    upper_return: Optional[float] = None
    multiplier: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "MarketAdjustmentBand":
        if self.lower_return is None and self.upper_return is None:
            raise ValueError("market adjustment band must define lower_return or upper_return")
        if (
            self.lower_return is not None
            and self.upper_return is not None
            and self.lower_return > self.upper_return
        ):
            raise ValueError("market adjustment band lower_return must be <= upper_return")
        return self


class HistoricalAnalysis(StrictBaseModel):
    enabled: bool = False
    dataset: HistoricalDataset = HistoricalDataset.DAMODARAN_US_ANNUAL_1970_2025
    selected_start_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    success_rate_target: float = Field(default=0.90, ge=0.0, le=1.0)
    use_historical_inflation_for_expenses: bool = True
    use_historical_inflation_for_income_cola: bool = True
    weighting: HistoricalWeighting = Field(default_factory=HistoricalWeighting)
    account_type_return_policies: Dict[AccountType, AccountTypeHistoricalPolicy] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_selected_start_year(self) -> "HistoricalAnalysis":
        if not self.enabled and self.selected_start_year is not None:
            raise ValueError(
                "historical_analysis.selected_start_year must be null when historical_analysis.enabled is false"
            )
        return self


# ============================================================
# Household
# ============================================================


class ModeledDeath(StrictBaseModel):
    enabled: bool
    death_year: Optional[int] = None

    @model_validator(mode="after")
    def validate_consistency(self) -> "ModeledDeath":
        if not self.enabled and self.death_year is not None:
            raise ValueError("death_year must be null when modeled_death.enabled is false")
        return self


class Person(StrictBaseModel):
    label: str
    birth_month: int = Field(ge=1, le=12)
    birth_year: int = Field(ge=1900, le=2100)
    current_age: int = Field(ge=0)
    retirement_age: int = Field(ge=0)
    modeled_death: ModeledDeath


class ExpenseStepdownAfterHusbandDeath(StrictBaseModel):
    enabled: bool
    surviving_expense_ratio: float = Field(ge=0.0, le=1.0)


class Household(StrictBaseModel):
    filing_status_initial: FilingStatus
    state_of_residence: str = Field(min_length=1)
    husband: Person
    wife: Person
    expense_stepdown_after_husband_death: ExpenseStepdownAfterHusbandDeath


# ============================================================
# Income
# ============================================================


class EarnedIncomePerson(StrictBaseModel):
    enabled: bool
    income_type: IncomeType
    taxable: bool
    annual_gross_salary_start: float = Field(ge=0.0)
    annual_raise_rate: float = Field(ge=0.0, le=1.0)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "EarnedIncomePerson":
        if self.end_date < self.start_date:
            raise ValueError("earned income end_date must be on or after start_date")
        return self


class EarnedIncome(StrictBaseModel):
    husband: EarnedIncomePerson
    wife: EarnedIncomePerson


class VADisability(StrictBaseModel):
    owner: AccountOwner
    amount_monthly: float = Field(ge=0.0)
    taxable: bool
    cola_rate: float = Field(ge=0.0, le=1.0)
    start_date: date
    end_at_death: bool

    @model_validator(mode="after")
    def validate_owner_and_taxability(self) -> "VADisability":
        if self.owner != AccountOwner.HUSBAND:
            raise ValueError("va_disability.owner must be Husband")
        if self.taxable:
            raise ValueError("va_disability.taxable must be false")
        return self


class ConditionalStart(StrictBaseModel):
    husband_death_after: date


class VASurvivorBenefit(StrictBaseModel):
    owner: AccountOwner
    enabled: bool
    conditional_start: ConditionalStart
    amount_monthly: float = Field(ge=0.0)
    taxable: bool
    cola_rate: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_owner_and_taxability(self) -> "VASurvivorBenefit":
        if self.owner != AccountOwner.WIFE:
            raise ValueError("va_survivor_benefit.owner must be Wife")
        if self.taxable:
            raise ValueError("va_survivor_benefit.taxable must be false")
        return self


class SocialSecurityPerson(StrictBaseModel):
    claim_age: float = Field(ge=62)
    amount_monthly_at_claim: float = Field(ge=0.0)
    cola_rate: float = Field(ge=0.0, le=1.0)


class SocialSecuritySurvivorRule(StrictBaseModel):
    enabled: bool
    step_up_to_higher_benefit: bool


class SocialSecurity(StrictBaseModel):
    husband: SocialSecurityPerson
    wife: SocialSecurityPerson
    survivor_rule: SocialSecuritySurvivorRule


class PensionIncomeItem(StrictBaseModel):
    enabled: bool
    owner: AccountOwner
    amount_monthly: float = Field(ge=0.0)
    taxable: bool
    cola_rate: float = Field(ge=0.0, le=1.0)
    start_date: date

    @model_validator(mode="after")
    def validate_owner(self) -> "PensionIncomeItem":
        if self.owner != AccountOwner.WIFE:
            raise ValueError("wife_imrf.owner must be Wife")
        return self


class PensionIncome(StrictBaseModel):
    wife_imrf: PensionIncomeItem


class IncomeConfig(StrictBaseModel):
    earned_income: EarnedIncome
    va_disability: VADisability
    va_survivor_benefit: VASurvivorBenefit
    social_security: SocialSecurity
    pension_income: PensionIncome


# ============================================================
# Accounts
# ============================================================


class PurposeTransition(StrictBaseModel):
    transition_age_husband: int = Field(ge=0)
    new_purpose: str = Field(min_length=1)


class Account(StrictBaseModel):
    name: str = Field(min_length=1)
    type: AccountType
    owner: AccountOwner
    starting_balance: float = Field(ge=0.0)
    return_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    return_schedule: Optional[List[ReturnScheduleEntry]] = None
    withdrawals_enabled: Optional[bool] = None
    contributions_enabled: Optional[bool] = None
    purpose: Optional[str] = None
    purpose_transition: Optional[PurposeTransition] = None
    target_balance_at_age_65: Optional[float] = Field(default=None, ge=0.0)
    target_balance_is_advisory: Optional[bool] = None
    restriction: Optional[str] = None

    @model_validator(mode="after")
    def validate_return_configuration(self) -> "Account":
        if self.return_rate is None and not self.return_schedule:
            raise ValueError(f"account '{self.name}' must define return_rate or return_schedule")
        if (
            self.restriction is not None
            and self.restriction != RESTRICTED_RETIREMENT_CASHFLOW_POLICY
        ):
            raise ValueError(
                f"account '{self.name}' uses an unsupported restriction; "
                f"expected {RESTRICTED_RETIREMENT_CASHFLOW_POLICY}"
            )
        if self.return_schedule:
            sorted_entries = sorted(self.return_schedule, key=lambda x: x.start_date)
            for prev, curr in pairwise(sorted_entries):
                if prev.end_date is None:
                    raise ValueError(
                        f"account '{self.name}' has an open-ended return_schedule entry before a later entry"
                    )
                if prev.end_date >= curr.start_date:
                    raise ValueError(
                        f"account '{self.name}' return_schedule periods may not overlap"
                    )
        if self.name == "Car Fund":
            if self.type != AccountType.RESTRICTED_CASH:
                raise ValueError("Car Fund must use account type 'restricted_cash'")
            if self.withdrawals_enabled is not False:
                raise ValueError("Car Fund withdrawals_enabled must be false")
        return self


# ============================================================
# Contributions
# ============================================================


class SurplusAllocation(StrictBaseModel):
    enabled: bool = True
    destination_account: Optional[str] = None
    start_age_husband: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_destination_account(self) -> "SurplusAllocation":
        if self.enabled and not self.destination_account:
            raise ValueError(
                "contributions.surplus_allocation.destination_account is required when surplus allocation is enabled"
            )
        return self


class ContributionSchedule(StrictBaseModel):
    name: str = Field(min_length=1)
    enabled: bool
    owner: AccountOwner
    destination_account: str
    type: ContributionType
    percent: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    amount_monthly: Optional[float] = Field(default=None, ge=0.0)
    amount_annual: Optional[float] = Field(default=None, ge=0.0)
    start_date: date
    end_date: date
    purpose: Optional[str] = None

    @model_validator(mode="after")
    def validate_driver_fields(self) -> "ContributionSchedule":
        if self.end_date < self.start_date:
            raise ValueError(f"contribution '{self.name}' end_date must be on or after start_date")

        driver_count = sum(
            value is not None for value in (self.percent, self.amount_monthly, self.amount_annual)
        )
        if driver_count != 1:
            raise ValueError(
                f"contribution '{self.name}' must define exactly one of percent, amount_monthly, amount_annual"
            )

        if self.type == ContributionType.PERCENT_OF_SALARY and self.percent is None:
            raise ValueError(f"contribution '{self.name}' type percent_of_salary requires percent")
        if self.type == ContributionType.FIXED_MONTHLY and self.amount_monthly is None:
            raise ValueError(
                f"contribution '{self.name}' type fixed_monthly requires amount_monthly"
            )
        if self.type == ContributionType.FIXED_ANNUAL and self.amount_annual is None:
            raise ValueError(f"contribution '{self.name}' type fixed_annual requires amount_annual")
        return self


class ContributionsConfig(StrictBaseModel):
    enabled: bool
    surplus_allocation: SurplusAllocation
    schedules: List[ContributionSchedule]


# ============================================================
# Expenses / Guardrails
# ============================================================


class ExpenseAdjustment(StrictBaseModel):
    start_year: int = Field(ge=0)
    end_year: int = Field(ge=0)
    amount_annual: float = Field(ge=0.0)
    inflation_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_year_range(self) -> "ExpenseAdjustment":
        if self.end_year < self.start_year:
            raise ValueError("expense adjustment end_year must be on or after start_year")
        return self


class InflatingAnnualExpense(StrictBaseModel):
    amount_annual: float = Field(ge=0.0)
    inflation_rate: float = Field(ge=0.0, le=1.0)
    adjustments: List[ExpenseAdjustment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_adjustments(self) -> "InflatingAnnualExpense":
        sorted_adjustments = sorted(self.adjustments, key=lambda adjustment: adjustment.start_year)
        for previous, current in pairwise(sorted_adjustments):
            if previous.end_year >= current.start_year:
                raise ValueError("expense adjustments may not overlap")
        return self


class DatedInflatingAnnualExpense(StrictBaseModel):
    amount_annual: float = Field(ge=0.0)
    start_date: date
    inflation_rate: float = Field(ge=0.0, le=1.0)


class HousingExpenses(StrictBaseModel):
    property_tax: DatedInflatingAnnualExpense
    homeowners_insurance: DatedInflatingAnnualExpense


class ExpensesConfig(StrictBaseModel):
    base_living: InflatingAnnualExpense
    travel: InflatingAnnualExpense
    housing: HousingExpenses


class GuardrailTrigger(StrictBaseModel):
    type: SpendingGuardrailTrigger


class SpendingGuardrails(StrictBaseModel):
    enabled: bool
    base_spending_annual: float = Field(ge=0.0)
    floor_spending_annual: float = Field(ge=0.0)
    trigger: GuardrailTrigger

    @model_validator(mode="after")
    def validate_floor(self) -> "SpendingGuardrails":
        if self.floor_spending_annual > self.base_spending_annual:
            raise ValueError("floor_spending_annual cannot exceed base_spending_annual")
        return self


# ============================================================
# Mortgage
# ============================================================


class PayoffByAge(StrictBaseModel):
    enabled: bool
    target_age: int | None = Field(default=None, ge=0)
    target_date: date | None = None
    method: MortgagePayoffMethod


class MortgageConfig(StrictBaseModel):
    enabled: bool
    starting_balance: float = Field(ge=0.0)
    interest_rate: float = Field(ge=0.0, le=1.0)
    remaining_term_years: int = Field(ge=0)
    scheduled_payment_monthly: float | None = Field(default=None, ge=0.0)
    payment_frequency: PaymentFrequency
    payoff_by_age: PayoffByAge

    @model_validator(mode="after")
    def validate_enabled_fields(self) -> "MortgageConfig":
        if self.enabled:
            if self.starting_balance <= 0:
                raise ValueError("mortgage.starting_balance must be > 0 when mortgage is enabled")
            if self.interest_rate <= 0:
                raise ValueError("mortgage.interest_rate must be > 0 when mortgage is enabled")
            if self.remaining_term_years <= 0:
                raise ValueError(
                    "mortgage.remaining_term_years must be > 0 when mortgage is enabled"
                )
            if self.scheduled_payment_monthly is not None and self.scheduled_payment_monthly <= 0:
                raise ValueError("mortgage.scheduled_payment_monthly must be > 0 when provided")
        return self


# ============================================================
# Taxes / Federal / Medicare
# Shared defaults for these schema blocks are intentionally pinned in
# defaults/policy_defaults.yaml to current-year published policy values.
# Scenario inputs stay value-driven rather than year-driven, so tests must lock
# the concrete default numbers to avoid silent year drift.
# ============================================================


class ConversionTaxPaymentConfig(StrictBaseModel):
    treatment: ConversionTaxTreatment


class TaxesConfig(StrictBaseModel):
    conversion_tax_payment: ConversionTaxPaymentConfig


class StandardDeduction(StrictBaseModel):
    mfj: float = Field(ge=0.0)
    single: float = Field(ge=0.0)
    additional_age65_mfj_per_person: float = Field(ge=0.0)
    additional_age65_single: float = Field(ge=0.0)


class TaxBracket(StrictBaseModel):
    rate: float = Field(ge=0.0, le=1.0)
    up_to: Optional[float] = Field(default=None, ge=0.0)


class FederalBrackets(StrictBaseModel):
    mfj: List[TaxBracket]
    single: List[TaxBracket]

    @field_validator("mfj", "single")
    @classmethod
    def validate_brackets_sorted(cls, brackets: List[TaxBracket]) -> List[TaxBracket]:
        previous = -1.0
        for i, bracket in enumerate(brackets):
            if bracket.up_to is None:
                if i != len(brackets) - 1:
                    raise ValueError("only the last tax bracket may have up_to=null")
                break
            if bracket.up_to <= previous:
                raise ValueError("tax brackets must be sorted in ascending order by up_to")
            previous = bracket.up_to
        return brackets


class FederalTaxConfig(StrictBaseModel):
    standard_deduction: StandardDeduction
    brackets: FederalBrackets


class StateTaxConfig(StrictBaseModel):
    model: StateTaxModel
    taxable_income_basis: StateTaxableIncomeBasis = StateTaxableIncomeBasis.FEDERAL_TAXABLE_INCOME
    effective_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_model_config(self) -> "StateTaxConfig":
        if self.model == StateTaxModel.EFFECTIVE_RATE and self.effective_rate is None:
            raise ValueError(
                "state_tax.effective_rate is required when state_tax.model is effective_rate"
            )
        if self.model == StateTaxModel.NONE and self.effective_rate not in {None, 0.0}:
            raise ValueError(
                "state_tax.effective_rate must be omitted or zero when state_tax.model is none"
            )
        return self


class PremiumConfig(StrictBaseModel):
    base_premium_monthly: float = Field(ge=0.0)


class IRMAATier(StrictBaseModel):
    magi_up_to: Optional[float] = Field(default=None, ge=0.0)
    part_b_add: float = Field(ge=0.0)
    part_d_add: float = Field(ge=0.0)


class IRMAAReconsiderationConfig(StrictBaseModel):
    enabled: bool
    event: LifeChangingEvent
    use_current_year_magi: bool
    apply_after_retirement: bool
    override_conversion_guardrails: bool


class IRMAAConfig(StrictBaseModel):
    lookback_years: int
    mfj: List[IRMAATier]
    single: List[IRMAATier]
    reconsideration: IRMAAReconsiderationConfig

    @field_validator("lookback_years")
    @classmethod
    def validate_lookback(cls, value: int) -> int:
        if value != 2:
            raise ValueError("irmaa.lookback_years must be 2")
        return value

    @field_validator("mfj", "single")
    @classmethod
    def validate_sorted_tiers(cls, tiers: List[IRMAATier]) -> List[IRMAATier]:
        previous = -1.0
        for i, tier in enumerate(tiers):
            if tier.magi_up_to is None:
                if i != len(tiers) - 1:
                    raise ValueError("only the last IRMAA tier may have magi_up_to=null")
                break
            if tier.magi_up_to <= previous:
                raise ValueError("IRMAA tiers must be sorted in ascending order by magi_up_to")
            previous = tier.magi_up_to
        return tiers


class MedicareConfig(StrictBaseModel):
    start_age: int = Field(ge=0)
    part_b: PremiumConfig
    part_d: PremiumConfig
    irmaa: IRMAAConfig


# ============================================================
# Strategy
# ============================================================


class BasePolicy(StrictBaseModel):
    active_ages: List[int]
    base_conversion_amounts: Dict[int, float]

    @model_validator(mode="after")
    def validate_amounts_match_ages(self) -> "BasePolicy":
        missing = set(self.active_ages) - set(self.base_conversion_amounts.keys())
        if missing:
            raise ValueError(f"base_conversion_amounts missing entries for ages: {sorted(missing)}")
        return self


class TaxConstraints(StrictBaseModel):
    max_marginal_bracket: float = Field(ge=0.0, le=1.0)
    allow_partial_bracket_fill: bool


class IRMAAControls(StrictBaseModel):
    enabled: bool
    max_tier: int = Field(ge=0)
    reduce_if_exceeded: bool


class MarketAdjustmentRule(StrictBaseModel):
    condition: MarketCondition
    threshold: float
    action: AdjustmentAction
    adjustment_percent: float = Field(ge=0.0, le=1.0)


class MarketAdjustments(StrictBaseModel):
    enabled: bool
    signal_account_type: AccountType = AccountType.TRADITIONAL_IRA
    rules: List[MarketAdjustmentRule] = Field(default_factory=list)
    bands: List[MarketAdjustmentBand] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_adjustment_config(self) -> "MarketAdjustments":
        if self.enabled and not self.rules and not self.bands:
            raise ValueError("market_adjustments requires rules or bands when enabled")

        sorted_bands = sorted(
            self.bands,
            key=lambda band: float("-inf") if band.lower_return is None else band.lower_return,
        )
        previous_upper: Optional[float] = None
        for band in sorted_bands:
            lower = band.lower_return
            upper = band.upper_return
            if previous_upper is not None and lower is not None and lower < previous_upper:
                raise ValueError("market adjustment bands may not overlap")
            if upper is not None:
                previous_upper = upper
        return self


class BalanceAdjustmentRule(StrictBaseModel):
    action: AdjustmentAction
    adjustment_percent: float = Field(ge=0.0, le=1.0)


class BalanceAdjustmentLogic(StrictBaseModel):
    if_above_target: BalanceAdjustmentRule
    if_below_target: BalanceAdjustmentRule


class BalanceTargets(StrictBaseModel):
    enabled: bool
    traditional_ira_target_at_70: float = Field(ge=0.0)
    acceptable_band_percent: float = Field(ge=0.0, le=1.0)
    target_priority: TargetPriority
    allow_below_min_if_needed_to_hit_target: bool
    adjustment_logic: BalanceAdjustmentLogic


class SocialSecurityInteraction(StrictBaseModel):
    reduce_after_husband_claim: bool
    reduction_percent: float = Field(ge=0.0, le=1.0)


class MinConversionConfig(StrictBaseModel):
    type: MinConversionType
    base: float = Field(ge=0.0)
    reduce_if_exceeds_bracket: bool
    enforce_only_when_target_not_at_risk: bool


class SafetyLimits(StrictBaseModel):
    max_conversion: float = Field(ge=0.0)
    min_conversion: MinConversionConfig

    @model_validator(mode="after")
    def validate_range(self) -> "SafetyLimits":
        if self.max_conversion < self.min_conversion.base:
            raise ValueError("max_conversion must be >= min_conversion.base")
        return self


class ConversionTaxPaymentStrategy(StrictBaseModel):
    enabled: bool
    payment_timing: ConversionTaxPaymentTiming
    estimated_tax_method: EstimatedTaxMethod
    source_order: List[ConversionTaxSource]
    source_account_name: str
    allow_roth_for_conversion_taxes: bool
    gross_up_conversion_if_needed: bool
    track_conversion_tax_separately: bool
    allow_bridge_for_living_expenses: bool
    prioritize_tax_use_first: bool
    use_bridge_for_living_only_if_absolutely_necessary: bool


class RothConversions(StrictBaseModel):
    enabled: bool
    strategy: ConversionStrategy
    base_policy: BasePolicy
    tax_constraints: TaxConstraints
    irmaa_controls: IRMAAControls
    market_adjustments: MarketAdjustments
    balance_targets: BalanceTargets
    social_security_interaction: SocialSecurityInteraction
    safety_limits: SafetyLimits
    tax_payment: ConversionTaxPaymentStrategy

    @model_validator(mode="after")
    def validate_target_override_logic(self) -> "RothConversions":
        if (
            self.balance_targets.allow_below_min_if_needed_to_hit_target
            and not self.balance_targets.enabled
        ):
            raise ValueError(
                "allow_below_min_if_needed_to_hit_target requires balance_targets.enabled=true"
            )
        return self


class GivingPolicy(StrictBaseModel):
    type: GivingPolicyType
    percent_of_income: float = Field(ge=0.0, le=1.0)
    compare_to: GivingCompareTo
    income_definition: GivingIncomeDefinition
    recurring_sources: List[str]


class QCDTaxTreatment(StrictBaseModel):
    reduces_rmd: bool
    excluded_from_taxable_income: bool


class QCDDepletionMethod(str, Enum):
    LEVEL_ANNUAL_QCD = "level_annual_qcd"


class QCDDepletionTarget(StrictBaseModel):
    enabled: bool = False
    owners: List[AccountOwner] = Field(
        default_factory=lambda: [AccountOwner.HUSBAND, AccountOwner.WIFE]
    )
    target_age: int = Field(default=90, ge=71)
    target_balance: float = Field(default=0.0, ge=0.0)
    method: QCDDepletionMethod = QCDDepletionMethod.LEVEL_ANNUAL_QCD

    @model_validator(mode="after")
    def validate_owners(self) -> "QCDDepletionTarget":
        if self.enabled and not self.owners:
            raise ValueError("QCD depletion target requires at least one owner")
        return self


class QCDConfig(StrictBaseModel):
    enabled: bool
    start_age: float = Field(ge=70.5)
    annual_limit: float = Field(ge=0.0)
    allow_above_rmd: bool = False
    applies_to: List[AccountType]
    tax_treatment: QCDTaxTreatment
    depletion_target: QCDDepletionTarget = Field(default_factory=QCDDepletionTarget)

    @model_validator(mode="after")
    def validate_depletion_rules(self) -> "QCDConfig":
        if self.depletion_target.enabled and not self.allow_above_rmd:
            raise ValueError("QCD depletion target requires allow_above_rmd=true")
        if self.depletion_target.enabled and self.depletion_target.target_age < ceil(
            self.start_age
        ):
            raise ValueError("QCD depletion target age must be at or after the QCD start age")
        return self


class GivingCoordinationRules(StrictBaseModel):
    apply_qcd_before_rmd_taxation: bool
    if_ira_insufficient_for_giving: IRAInsufficientAction
    prohibit_other_accounts_for_giving: bool


class CharitableGiving(StrictBaseModel):
    enabled: bool
    policy: GivingPolicy
    qcd: QCDConfig
    coordination_rules: GivingCoordinationRules


class WithdrawalRestrictions(StrictBaseModel):
    never_use_accounts: List[str]


class BridgeUsagePreAge70(StrictBaseModel):
    primary_use: str
    secondary_use: str


class BridgeUsagePostAge70(StrictBaseModel):
    use_as: str


class BridgeUsage(StrictBaseModel):
    pre_age_70: BridgeUsagePreAge70
    post_age_70: BridgeUsagePostAge70


class RMDHandling(StrictBaseModel):
    enforce: bool
    allow_qcd_to_satisfy_rmd: bool
    withdraw_remaining_rmd_if_needed: bool


class Withdrawals(StrictBaseModel):
    order: List[WithdrawalOrderType]
    restrictions: WithdrawalRestrictions
    bridge_usage: BridgeUsage
    rmd_handling: RMDHandling


class AnalyticsSubsection(StrictBaseModel):
    enabled: bool = False
    track: List[str] = Field(default_factory=list)


class Analytics(StrictBaseModel):
    required_outputs: List[str] = Field(
        default_factory=lambda: [
            "yearly_ledger",
            "account_balances_by_year",
            "taxes_by_year",
            "conversion_totals_by_year",
            "rmd_qcd_giving_by_year",
            "failure_year",
            "net_worth",
            "total_taxes",
            "total_conversions",
            "ira_balance_at_70",
        ]
    )
    conversion_efficiency: AnalyticsSubsection = Field(default_factory=AnalyticsSubsection)
    rmd_projection: AnalyticsSubsection = Field(default_factory=AnalyticsSubsection)
    charitable_tracking: AnalyticsSubsection = Field(default_factory=AnalyticsSubsection)


class AccountRollovers(StrictBaseModel):
    enabled: bool = False
    roll_traditional_401k_to_ira: bool = True
    roll_roth_401k_to_ira: bool = True


class StrategyConfig(StrictBaseModel):
    roth_conversions: RothConversions
    charitable_giving: CharitableGiving
    withdrawals: Withdrawals
    analytics: Analytics = Field(default_factory=Analytics)
    account_rollovers: AccountRollovers = Field(default_factory=AccountRollovers)


# ============================================================
# Root
# ============================================================


class RetirementScenario(StrictBaseModel):
    metadata: Metadata
    simulation: Simulation
    assumptions: Assumptions
    validation: ValidationConfig
    household: Household
    income: IncomeConfig
    accounts: List[Account]
    contributions: ContributionsConfig
    expenses: ExpensesConfig
    spending_guardrails: SpendingGuardrails
    mortgage: MortgageConfig
    taxes: TaxesConfig
    federal_tax: FederalTaxConfig
    state_tax: StateTaxConfig
    medicare: MedicareConfig
    strategy: StrategyConfig
    historical_analysis: HistoricalAnalysis = Field(default_factory=HistoricalAnalysis)
    overrides: Dict[str, Any]

    def _account_by_name(self, account_name: str) -> Optional[Account]:
        return next((account for account in self.accounts if account.name == account_name), None)

    def _restricted_account_names(self) -> set[str]:
        return {
            account.name
            for account in self.accounts
            if account.restriction == RESTRICTED_RETIREMENT_CASHFLOW_POLICY
        }

    def _bridge_account_required(self) -> bool:
        if self.contributions.surplus_allocation.destination_account == BRIDGE_ACCOUNT_NAME:
            return True
        if any(
            schedule.destination_account == BRIDGE_ACCOUNT_NAME
            for schedule in self.contributions.schedules
        ):
            return True
        if WithdrawalOrderType.TAXABLE_BRIDGE_ACCOUNT in self.strategy.withdrawals.order:
            return True
        if (
            ConversionTaxSource.TAXABLE_BRIDGE_ACCOUNT
            in self.strategy.roth_conversions.tax_payment.source_order
        ):
            return True
        return False

    def _validate_destination_account(self, account_name: str, context: str) -> None:
        destination_account = self._account_by_name(account_name)
        if destination_account is None:
            raise ValueError(f"{context} must refer to an existing account")
        if destination_account.contributions_enabled is False:
            raise ValueError(f"{context} must refer to an account that accepts contributions")

    def _validate_account_references(self, account_names: set[str]) -> None:
        if self._bridge_account_required() and BRIDGE_ACCOUNT_NAME not in account_names:
            raise ValueError(
                f"{BRIDGE_ACCOUNT_NAME} must exist when bridge-account strategy paths are configured"
            )

        surplus_allocation = self.contributions.surplus_allocation
        if surplus_allocation.enabled and surplus_allocation.destination_account is not None:
            self._validate_destination_account(
                surplus_allocation.destination_account,
                "contributions.surplus_allocation.destination_account",
            )

        for schedule in self.contributions.schedules:
            self._validate_destination_account(
                schedule.destination_account,
                f"contribution '{schedule.name}' destination_account",
            )

        source_account_name = self.strategy.roth_conversions.tax_payment.source_account_name
        if source_account_name not in account_names:
            raise ValueError(
                "strategy.roth_conversions.tax_payment.source_account_name must refer to an existing account"
            )

        if (
            ConversionTaxSource.HOUSEHOLD_OPERATING_CASH
            in self.strategy.roth_conversions.tax_payment.source_order
            and HOUSEHOLD_OPERATING_CASH_ACCOUNT_NAME not in account_names
        ):
            raise ValueError(
                "Household Operating Cash must exist when household_operating_cash is in tax source order"
            )

        for restricted_name in self.strategy.withdrawals.restrictions.never_use_accounts:
            if restricted_name not in account_names:
                raise ValueError(
                    f"never_use_account '{restricted_name}' must refer to an existing account"
                )

    def _validate_employment_dates(self) -> None:
        for person_name, earned in (
            ("husband", self.income.earned_income.husband),
            ("wife", self.income.earned_income.wife),
        ):
            if earned.end_date >= self.simulation.retirement_date:
                raise ValueError(
                    f"income.earned_income.{person_name}.end_date must be before simulation.retirement_date"
                )

        for schedule in self.contributions.schedules:
            if (
                schedule.type == ContributionType.PERCENT_OF_SALARY
                and schedule.end_date >= self.simulation.retirement_date
            ):
                raise ValueError(
                    f"employment-related contribution '{schedule.name}' must end before simulation.retirement_date"
                )

    def _validate_withdrawal_strategy(self, account_names: set[str]) -> None:
        restricted_account_names = self._restricted_account_names()
        configured_never_use_accounts = set(
            self.strategy.withdrawals.restrictions.never_use_accounts
        )

        missing_restricted_accounts = restricted_account_names - configured_never_use_accounts
        if missing_restricted_accounts:
            missing_names = ", ".join(sorted(missing_restricted_accounts))
            raise ValueError(
                "restricted accounts must appear in strategy.withdrawals.restrictions.never_use_accounts: "
                f"{missing_names}"
            )

        non_restricted_never_use_accounts = configured_never_use_accounts - restricted_account_names
        if non_restricted_never_use_accounts:
            unexpected_names = ", ".join(sorted(non_restricted_never_use_accounts))
            raise ValueError(
                "never_use_accounts may only contain accounts marked with restriction "
                f"{RESTRICTED_RETIREMENT_CASHFLOW_POLICY}: {unexpected_names}"
            )

        surplus_destination = self.contributions.surplus_allocation.destination_account
        if surplus_destination in restricted_account_names:
            raise ValueError(
                "restricted accounts cannot be used as surplus allocation destinations"
            )

        source_account_name = self.strategy.roth_conversions.tax_payment.source_account_name
        if source_account_name in restricted_account_names:
            raise ValueError("restricted accounts cannot be used as conversion tax payment sources")

        if (
            ConversionTaxSource.TAXABLE_BRIDGE_ACCOUNT
            in self.strategy.roth_conversions.tax_payment.source_order
            and BRIDGE_ACCOUNT_NAME not in account_names
        ):
            raise ValueError(
                f"{BRIDGE_ACCOUNT_NAME} must exist when taxable_bridge_account is in tax source order"
            )

        if (
            WithdrawalOrderType.TAXABLE_BRIDGE_ACCOUNT in self.strategy.withdrawals.order
            and BRIDGE_ACCOUNT_NAME not in account_names
        ):
            raise ValueError(
                f"{BRIDGE_ACCOUNT_NAME} must exist when taxable_bridge_account is in withdrawal order"
            )

    def _validate_charitable_giving(self, account_names: set[str]) -> None:
        del account_names
        if self.strategy.charitable_giving.qcd.enabled:
            qcd_types = set(self.strategy.charitable_giving.qcd.applies_to)
            applicable_accounts = [
                account
                for account in self.accounts
                if account.type in qcd_types
                and account.owner in {AccountOwner.HUSBAND, AccountOwner.WIFE}
                and account.withdrawals_enabled is not False
                and account.restriction != RESTRICTED_RETIREMENT_CASHFLOW_POLICY
            ]
            if not applicable_accounts:
                raise ValueError("QCD is enabled but no applicable account type exists in accounts")

            if self.strategy.charitable_giving.qcd.depletion_target.enabled:
                for owner in self.strategy.charitable_giving.qcd.depletion_target.owners:
                    owner_has_applicable_account = any(
                        account.owner == owner for account in applicable_accounts
                    )
                    if not owner_has_applicable_account:
                        owner_label = owner.value if isinstance(owner, AccountOwner) else str(owner)
                        raise ValueError(
                            f"QCD depletion target owner {owner_label} requires an applicable IRA account"
                        )

        if self.strategy.charitable_giving.coordination_rules.prohibit_other_accounts_for_giving:
            if (
                self.strategy.charitable_giving.coordination_rules.if_ira_insufficient_for_giving
                != IRAInsufficientAction.SKIP_EXCESS_GIVING
            ):
                raise ValueError(
                    "when prohibit_other_accounts_for_giving is true, if_ira_insufficient_for_giving must be skip_excess_giving"
                )

    def _validate_account_rollovers(self) -> None:
        rollovers = self.strategy.account_rollovers
        if not rollovers.enabled:
            return

        for owner in (AccountOwner.HUSBAND, AccountOwner.WIFE):
            owner_accounts = [account for account in self.accounts if account.owner == owner]
            if (
                rollovers.roll_traditional_401k_to_ira
                and any(account.type == AccountType.TRADITIONAL_401K for account in owner_accounts)
                and not any(
                    account.type == AccountType.TRADITIONAL_IRA for account in owner_accounts
                )
            ):
                raise ValueError(
                    f"strategy.account_rollovers requires a traditional_ira target for {owner.value}"
                )
            if (
                rollovers.roll_roth_401k_to_ira
                and any(account.type == AccountType.ROTH_401K for account in owner_accounts)
                and not any(account.type == AccountType.ROTH_IRA for account in owner_accounts)
            ):
                raise ValueError(
                    f"strategy.account_rollovers requires a roth_ira target for {owner.value}"
                )

    def _validate_historical_analysis(self) -> None:
        if not self.historical_analysis.enabled:
            return

        configured_types = set(self.historical_analysis.account_type_return_policies)
        missing_types = {
            account.type for account in self.accounts if account.type not in configured_types
        }
        if missing_types:
            missing_names = ", ".join(sorted(account_type.value for account_type in missing_types))
            raise ValueError(
                "historical_analysis.account_type_return_policies is missing account types: "
                f"{missing_names}"
            )

    @model_validator(mode="after")
    def validate_cross_references(self) -> "RetirementScenario":
        account_names = {account.name for account in self.accounts}
        if len(account_names) != len(self.accounts):
            raise ValueError("account names must be unique")

        self._validate_account_references(account_names)
        self._validate_employment_dates()
        self._validate_withdrawal_strategy(account_names)
        self._validate_charitable_giving(account_names)
        self._validate_account_rollovers()
        self._validate_historical_analysis()

        return self


RetirementScenario.model_rebuild(_types_namespace=globals())

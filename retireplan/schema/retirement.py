from __future__ import annotations

from datetime import date
from enum import Enum
from itertools import pairwise
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

    @model_validator(mode="after")
    def validate_ages(self) -> "Person":
        if self.retirement_age < self.current_age:
            raise ValueError("retirement_age must be >= current_age")
        return self


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
    destination_account: str


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


class InflatingAnnualExpense(StrictBaseModel):
    amount_annual: float = Field(ge=0.0)
    inflation_rate: float = Field(ge=0.0, le=1.0)


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
    target_age: int = Field(ge=0)
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
# ============================================================


class ConversionTaxPaymentConfig(StrictBaseModel):
    treatment: ConversionTaxTreatment


class TaxesConfig(StrictBaseModel):
    conversion_tax_payment: ConversionTaxPaymentConfig


class StandardDeduction(StrictBaseModel):
    mfj: float = Field(ge=0.0)
    single: float = Field(ge=0.0)


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
    rules: List[MarketAdjustmentRule]


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


class QCDConfig(StrictBaseModel):
    enabled: bool
    start_age: float = Field(ge=70.5)
    annual_limit: float = Field(ge=0.0)
    applies_to: List[AccountType]
    tax_treatment: QCDTaxTreatment


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
    enabled: bool
    track: List[str]


class Analytics(StrictBaseModel):
    required_outputs: List[str]
    conversion_efficiency: AnalyticsSubsection
    rmd_projection: AnalyticsSubsection
    charitable_tracking: AnalyticsSubsection


class AccountRollovers(StrictBaseModel):
    enabled: bool = False
    roll_traditional_401k_to_ira: bool = True
    roll_roth_401k_to_ira: bool = True


class StrategyConfig(StrictBaseModel):
    roth_conversions: RothConversions
    charitable_giving: CharitableGiving
    withdrawals: Withdrawals
    analytics: Analytics
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
    overrides: Dict[str, Any]

    def _validate_account_references(self, account_names: set[str]) -> None:
        if self.contributions.surplus_allocation.destination_account not in account_names:
            raise ValueError(
                "contributions.surplus_allocation.destination_account must refer to an existing account"
            )

        for schedule in self.contributions.schedules:
            if schedule.destination_account not in account_names:
                raise ValueError(
                    f"contribution '{schedule.name}' destination_account must refer to an existing account"
                )

        source_account_name = self.strategy.roth_conversions.tax_payment.source_account_name
        if source_account_name not in account_names:
            raise ValueError(
                "strategy.roth_conversions.tax_payment.source_account_name must refer to an existing account"
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
        if "Car Fund" not in self.strategy.withdrawals.restrictions.never_use_accounts:
            raise ValueError(
                "Car Fund must appear in strategy.withdrawals.restrictions.never_use_accounts"
            )

        if (
            ConversionTaxSource.TAXABLE_BRIDGE_ACCOUNT
            in self.strategy.roth_conversions.tax_payment.source_order
            and "Taxable Bridge Account" not in account_names
        ):
            raise ValueError(
                "Taxable Bridge Account must exist when taxable_bridge_account is in tax source order"
            )

    def _validate_charitable_giving(self, account_names: set[str]) -> None:
        del account_names
        if self.strategy.charitable_giving.qcd.enabled:
            qcd_types = set(self.strategy.charitable_giving.qcd.applies_to)
            existing_types = {account.type for account in self.accounts}
            if not (qcd_types & existing_types):
                raise ValueError("QCD is enabled but no applicable account type exists in accounts")

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

        return self


RetirementScenario.model_rebuild(_types_namespace=globals())

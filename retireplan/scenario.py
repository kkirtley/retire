"""Backward-compatible accessors for the packaged scenario schema."""

from __future__ import annotations

from retireplan.schema import retirement as _schema
from retireplan.schema.retirement import (
    Account,
    AccountType,
    ContributionType,
    EarnedIncomePerson,
    RetirementScenario,
    WithdrawalOrderType,
)

__all__: list[str] = [
    "Account",
    "AccountType",
    "ContributionType",
    "EarnedIncomePerson",
    "RetirementScenario",
    "WithdrawalOrderType",
]
for _name, _value in vars(_schema).items():
    if _name.startswith("_"):
        continue
    if getattr(_value, "__module__", None) != _schema.__name__:
        continue
    globals()[_name] = _value
    if _name not in __all__:
        __all__.append(_name)

from pathlib import Path

import pytest
import yaml

from retireplan.io import load_scenario, load_scenario_text


def test_load_baseline_scenario_and_collect_warnings(golden_loaded):
    loaded = golden_loaded

    assert loaded.scenario.metadata.version == "1.0.1"
    assert loaded.scenario.household.husband.label == "Husband"
    assert loaded.warnings == []
    assert loaded.scenario.assumptions.rmd_uniform_lifetime_table[75] == 24.6
    assert loaded.scenario.strategy.account_rollovers.enabled is True
    assert loaded.scenario.contributions.surplus_allocation.enabled is True
    assert (
        loaded.scenario.contributions.surplus_allocation.destination_account
        == "Taxable Bridge Account"
    )
    assert loaded.scenario.contributions.surplus_allocation.start_age_husband == 70
    assert loaded.scenario.strategy.charitable_giving.qcd.allow_above_rmd is True
    assert loaded.scenario.strategy.charitable_giving.qcd.depletion_target.enabled is True
    assert loaded.scenario.strategy.charitable_giving.qcd.depletion_target.owners == ["Husband"]
    assert loaded.scenario.strategy.charitable_giving.qcd.depletion_target.target_age == 90
    assert loaded.scenario.historical_analysis.enabled is False
    assert loaded.scenario.historical_analysis.dataset == "damodaran_us_annual_1970_2025"
    assert "traditional_ira" in loaded.scenario.historical_analysis.account_type_return_policies
    assert loaded.scenario.strategy.analytics.required_outputs == [
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
    assert loaded.scenario.strategy.analytics.conversion_efficiency.enabled is False
    assert loaded.scenario.strategy.analytics.rmd_projection.enabled is False
    assert loaded.scenario.strategy.analytics.charitable_tracking.enabled is False


def test_loader_applies_shared_defaults_when_scenario_omits_policy_table(tmp_path, golden_payload):
    payload = golden_payload
    payload["assumptions"].pop("rmd_uniform_lifetime_table", None)
    payload.pop("federal_tax", None)
    payload.pop("medicare", None)
    payload.pop("taxes", None)

    temp_path = tmp_path / "shared-defaults.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    loaded = load_scenario(temp_path)

    assert loaded.scenario.assumptions.rmd_uniform_lifetime_table[75] == 24.6
    assert loaded.scenario.federal_tax.standard_deduction.mfj == 30000.0
    assert loaded.scenario.federal_tax.standard_deduction.additional_age65_mfj_per_person == 1600.0
    assert loaded.scenario.federal_tax.standard_deduction.additional_age65_single == 2000.0
    assert loaded.scenario.medicare.part_b.base_premium_monthly == 174.7
    assert loaded.scenario.taxes.conversion_tax_payment.treatment == "annual_cash_outflow_same_year"


def test_loader_defaults_analytics_when_scenario_omits_block(golden_payload):
    payload = golden_payload
    payload["strategy"].pop("analytics", None)

    loaded = load_scenario_text(yaml.safe_dump(payload, sort_keys=False))

    assert loaded.scenario.strategy.analytics.required_outputs == [
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
    assert loaded.scenario.strategy.analytics.conversion_efficiency.track == []
    assert loaded.scenario.strategy.analytics.rmd_projection.track == []
    assert loaded.scenario.strategy.analytics.charitable_tracking.track == []


def test_repo_experimental_analytics_scenario_overrides_canonical_baseline(golden_scenario_path):
    scenario_path = golden_scenario_path.parent / "scenario_experimental_analytics.yaml"

    loaded = load_scenario(scenario_path)

    assert loaded.scenario.strategy.analytics.required_outputs == [
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
    assert loaded.scenario.strategy.analytics.conversion_efficiency.enabled is True
    assert loaded.scenario.strategy.analytics.rmd_projection.enabled is True
    assert loaded.scenario.strategy.analytics.charitable_tracking.enabled is True
    assert loaded.scenario.strategy.analytics.conversion_efficiency.track == [
        "taxes_paid_on_conversions",
        "estimated_future_tax_saved",
        "effective_conversion_rate",
    ]


def test_scenarios_root_contains_only_active_files(golden_scenario_path):
    scenarios_dir = golden_scenario_path.parent
    root_entries = {path.name for path in scenarios_dir.iterdir()}

    assert "baseline_canonical.yaml" in root_entries
    assert "test_baseline_minimal.yaml" in root_entries
    assert "README.md" in root_entries
    assert "archive" in root_entries
    assert not any(name.startswith("baseline_v") for name in root_entries)


def test_scenario_archive_contains_legacy_baselines(golden_scenario_path):
    archive_dir = golden_scenario_path.parent / "archive"
    archived_entries = {path.name for path in archive_dir.iterdir()}

    assert any(
        name.startswith("baseline_v") and name.endswith(".yaml") for name in archived_entries
    )


def test_loader_rejects_scenario_delta_with_unsupported_extends_field(
    tmp_path, golden_scenario_path
):
    baseline_path = tmp_path / "baseline_canonical.yaml"
    baseline_path.write_text(
        golden_scenario_path.parent.joinpath("baseline_canonical.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    scenario_path = tmp_path / "scenario_invalid_extends.yaml"
    scenario_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "scenario_name": "Invalid Extends",
                    "version": "1.0.0",
                    "description": "Unsupported extends field",
                    "created": "2026-04-21",
                    "currency": "USD",
                    "cadence": "annual",
                },
                "extends": "baseline_canonical.yaml",
                "overrides": {"assumptions": {"inflation_rate": 0.04}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="may only define metadata and overrides"):
        load_scenario(scenario_path)


def test_loader_rejects_unknown_root_field(tmp_path, golden_payload):
    payload = golden_payload
    payload["unexpected_field"] = True

    scenario_path = tmp_path / "unknown-field.yaml"
    scenario_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected_field"):
        load_scenario(scenario_path)


def test_loader_rejects_percent_of_salary_contribution_after_retirement_date(
    tmp_path, golden_payload
):
    payload = golden_payload
    payload["contributions"]["schedules"][0]["end_date"] = "2033-01-01"

    scenario_path = tmp_path / "late-employment-contribution.yaml"
    scenario_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="employment-related contribution 'Husband Traditional 401k employee' must end before simulation.retirement_date",
    ):
        load_scenario(scenario_path)


def test_loader_rejects_rollover_without_matching_ira_target(tmp_path, golden_payload):
    payload = golden_payload
    payload["strategy"]["account_rollovers"] = {
        "enabled": True,
        "roll_traditional_401k_to_ira": True,
        "roll_roth_401k_to_ira": True,
    }
    payload["accounts"] = [
        account
        for account in payload["accounts"]
        if not (account["owner"] == "Wife" and account["type"] == "traditional_ira")
    ]

    temp_path = tmp_path / "missing-rollover-target.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="traditional_ira target for Wife"):
        load_scenario(temp_path)


def test_loader_rejects_qcd_depletion_target_without_above_rmd(tmp_path, golden_payload):
    payload = golden_payload
    payload["strategy"]["charitable_giving"]["qcd"]["allow_above_rmd"] = False

    temp_path = tmp_path / "invalid-qcd-depletion.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="allow_above_rmd=true"):
        load_scenario(temp_path)


def test_loader_rejects_missing_bridge_account_when_bridge_paths_are_configured(
    tmp_path, golden_payload
):
    payload = golden_payload
    payload["accounts"] = [
        account for account in payload["accounts"] if account["name"] != "Taxable Bridge Account"
    ]

    temp_path = tmp_path / "missing-bridge-account.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Taxable Bridge Account must exist"):
        load_scenario(temp_path)


def test_loader_rejects_household_operating_cash_source_order_without_account(
    tmp_path, golden_payload
):
    payload = golden_payload
    payload["strategy"]["roth_conversions"]["tax_payment"]["source_order"] = [
        "household_operating_cash"
    ]

    temp_path = tmp_path / "missing-household-operating-cash.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Household Operating Cash must exist"):
        load_scenario(temp_path)


def test_loader_rejects_restricted_account_missing_from_never_use_accounts(
    tmp_path, golden_payload
):
    payload = golden_payload
    payload["strategy"]["withdrawals"]["restrictions"]["never_use_accounts"] = []

    temp_path = tmp_path / "restricted-account-not-never-use.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="restricted accounts must appear"):
        load_scenario(temp_path)


def test_loader_rejects_never_use_account_without_restriction_flag(tmp_path, golden_payload):
    payload = golden_payload
    payload["strategy"]["withdrawals"]["restrictions"]["never_use_accounts"] = [
        "Car Fund",
        "Taxable Bridge Account",
    ]

    temp_path = tmp_path / "never-use-without-restriction.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="never_use_accounts may only contain accounts marked"):
        load_scenario(temp_path)


def test_loader_rejects_qcd_depletion_owner_without_applicable_ira_account(
    tmp_path, golden_payload
):
    payload = golden_payload
    payload["strategy"]["charitable_giving"]["qcd"]["depletion_target"]["owners"] = ["Wife"]
    payload["accounts"] = [
        account
        for account in payload["accounts"]
        if not (account["owner"] == "Wife" and account["type"] == "traditional_ira")
    ]

    temp_path = tmp_path / "qcd-owner-missing-ira.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ValueError, match="QCD depletion target owner Wife requires an applicable IRA account"
    ):
        load_scenario(temp_path)


def test_loader_rejects_restricted_surplus_destination(tmp_path, golden_payload):
    payload = golden_payload
    payload["contributions"]["surplus_allocation"]["destination_account"] = "Car Fund"

    temp_path = tmp_path / "restricted-surplus-destination.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ValueError, match="restricted accounts cannot be used as surplus allocation destinations"
    ):
        load_scenario(temp_path)


def test_loader_rejects_missing_contribution_destination_account(tmp_path, golden_payload):
    payload = golden_payload
    payload["contributions"]["schedules"][0]["destination_account"] = "Missing Account"

    temp_path = tmp_path / "missing-contribution-destination.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="contribution 'Husband Traditional 401k employee' destination_account must refer to an existing account",
    ):
        load_scenario(temp_path)


def test_loader_rejects_missing_conversion_tax_source_account(tmp_path, golden_payload):
    payload = golden_payload
    payload["strategy"]["roth_conversions"]["tax_payment"][
        "source_account_name"
    ] = "Missing Account"

    temp_path = tmp_path / "missing-conversion-tax-source.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="source_account_name must refer to an existing account"):
        load_scenario(temp_path)


def test_loader_rejects_restricted_conversion_tax_source(tmp_path, golden_payload):
    payload = golden_payload
    payload["strategy"]["roth_conversions"]["tax_payment"]["source_account_name"] = "Car Fund"

    temp_path = tmp_path / "restricted-conversion-tax-source.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ValueError, match="restricted accounts cannot be used as conversion tax payment sources"
    ):
        load_scenario(temp_path)


def test_loader_merges_scenario_delta_with_canonical_baseline(tmp_path):
    baseline_path = tmp_path / "baseline_canonical.yaml"
    baseline_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "scenario_name": "Canonical Baseline",
                    "version": "1.0.0",
                    "description": "Base scenario",
                    "created": "2026-04-20",
                    "currency": "USD",
                    "cadence": "annual",
                },
                "simulation": {
                    "start_date": "2026-07-01",
                    "retirement_date": "2033-01-01",
                    "end_condition": {"wife_age": 90},
                    "proration": {"enabled": True, "method": "daily"},
                },
                "assumptions": {
                    "inflation_rate": 0.025,
                    "investment_return_default": 0.05,
                    "success_age": 90,
                    "ss_cola": 0.022,
                    "va_cola": 0.025,
                    "rmd_start_age": 75,
                },
                "validation": {
                    "strict": False,
                    "override_merge_rules": {
                        "object_merge": "deep_merge",
                        "list_merge": "replace_unless_keyed",
                    },
                },
                "household": {
                    "filing_status_initial": "mfj",
                    "state_of_residence": "Missouri",
                    "husband": {
                        "label": "Husband",
                        "birth_month": 7,
                        "birth_year": 1967,
                        "current_age": 58,
                        "retirement_age": 65,
                        "modeled_death": {"enabled": False, "death_year": None},
                    },
                    "wife": {
                        "label": "Wife",
                        "birth_month": 2,
                        "birth_year": 1967,
                        "current_age": 59,
                        "retirement_age": 65,
                        "modeled_death": {"enabled": False, "death_year": None},
                    },
                    "expense_stepdown_after_husband_death": {
                        "enabled": True,
                        "surviving_expense_ratio": 0.7,
                    },
                },
                "income": {
                    "earned_income": {
                        "husband": {
                            "enabled": True,
                            "income_type": "w2",
                            "taxable": True,
                            "annual_gross_salary_start": 195000.0,
                            "annual_raise_rate": 0.02,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        },
                        "wife": {
                            "enabled": True,
                            "income_type": "1099",
                            "taxable": True,
                            "annual_gross_salary_start": 60000.0,
                            "annual_raise_rate": 0.02,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        },
                    },
                    "va_disability": {
                        "owner": "Husband",
                        "amount_monthly": 4158.0,
                        "taxable": False,
                        "cola_rate": 0.025,
                        "start_date": "2026-07-01",
                        "end_at_death": True,
                    },
                    "va_survivor_benefit": {
                        "owner": "Wife",
                        "enabled": False,
                        "conditional_start": {"husband_death_after": "2035-02-01"},
                        "amount_monthly": 0.0,
                        "taxable": False,
                        "cola_rate": 0.025,
                    },
                    "social_security": {
                        "husband": {
                            "claim_age": 70,
                            "amount_monthly_at_claim": 5002.0,
                            "cola_rate": 0.025,
                        },
                        "wife": {
                            "claim_age": 65,
                            "amount_monthly_at_claim": 1500.0,
                            "cola_rate": 0.025,
                        },
                        "survivor_rule": {
                            "enabled": True,
                            "step_up_to_higher_benefit": True,
                        },
                    },
                    "pension_income": {
                        "wife_imrf": {
                            "enabled": True,
                            "owner": "Wife",
                            "amount_monthly": 302.9,
                            "taxable": True,
                            "cola_rate": 0.025,
                            "start_date": "2026-07-01",
                        }
                    },
                },
                "accounts": [
                    {
                        "name": "Husband Traditional IRA",
                        "type": "traditional_ira",
                        "owner": "Husband",
                        "starting_balance": 376000.0,
                        "return_rate": 0.05,
                    },
                    {
                        "name": "Car Fund",
                        "type": "restricted_cash",
                        "owner": "Household",
                        "starting_balance": 22000.0,
                        "return_rate": 0.033,
                        "withdrawals_enabled": False,
                        "contributions_enabled": True,
                        "restriction": "never_use_for_retirement_model_cashflows",
                    },
                    {
                        "name": "Taxable Bridge Account",
                        "type": "taxable",
                        "owner": "Household",
                        "starting_balance": 0.0,
                        "return_rate": 0.03,
                        "withdrawals_enabled": True,
                        "contributions_enabled": True,
                    },
                ],
                "contributions": {
                    "enabled": True,
                    "surplus_allocation": {
                        "enabled": True,
                        "destination_account": "Taxable Bridge Account",
                        "start_age_husband": 70,
                    },
                    "schedules": [
                        {
                            "name": "Bridge funding",
                            "enabled": True,
                            "owner": "Household",
                            "destination_account": "Taxable Bridge Account",
                            "type": "fixed_monthly",
                            "amount_monthly": 1000.0,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        }
                    ],
                },
                "expenses": {
                    "base_living": {
                        "amount_annual": 70000.0,
                        "inflation_rate": 0.025,
                        "adjustments": [],
                    },
                    "travel": {"amount_annual": 0.0, "inflation_rate": 0.025},
                    "housing": {
                        "property_tax": {
                            "amount_annual": 7000.0,
                            "start_date": "2026-07-01",
                            "inflation_rate": 0.02,
                        },
                        "homeowners_insurance": {
                            "amount_annual": 2500.0,
                            "start_date": "2026-07-01",
                            "inflation_rate": 0.02,
                        },
                    },
                },
                "spending_guardrails": {
                    "enabled": True,
                    "base_spending_annual": 70000.0,
                    "floor_spending_annual": 60000.0,
                    "trigger": {"type": "resource_pressure"},
                },
                "mortgage": {
                    "enabled": False,
                    "starting_balance": 0.0,
                    "interest_rate": 0.06,
                    "remaining_term_years": 15,
                    "scheduled_payment_monthly": None,
                    "payment_frequency": "monthly",
                    "payoff_by_age": {
                        "enabled": False,
                        "target_age": 65,
                        "target_date": "2032-12-31",
                        "method": "compute_extra_principal",
                    },
                },
                "taxes": {"conversion_tax_payment": {"treatment": "annual_cash_outflow_same_year"}},
                "state_tax": {
                    "model": "effective_rate",
                    "taxable_income_basis": "federal_taxable_income",
                    "effective_rate": 0.04,
                },
                "medicare": {
                    "irmaa": {
                        "reconsideration": {
                            "enabled": True,
                            "event": "work_stoppage",
                            "use_current_year_magi": True,
                            "apply_after_retirement": True,
                            "override_conversion_guardrails": False,
                        }
                    }
                },
                "strategy": {
                    "roth_conversions": {
                        "enabled": False,
                        "strategy": "adaptive_ladder",
                        "base_policy": {
                            "active_ages": [65],
                            "base_conversion_amounts": {65: 0.0},
                        },
                        "tax_constraints": {
                            "max_marginal_bracket": 0.22,
                            "allow_partial_bracket_fill": True,
                        },
                        "irmaa_controls": {
                            "enabled": False,
                            "max_tier": 2,
                            "reduce_if_exceeded": True,
                        },
                        "market_adjustments": {
                            "enabled": False,
                            "signal_account_type": "traditional_ira",
                            "rules": [],
                            "bands": [],
                        },
                        "balance_targets": {
                            "enabled": False,
                            "traditional_ira_target_at_70": 0.0,
                            "acceptable_band_percent": 0.33,
                            "target_priority": "higher_than_min_conversion",
                            "allow_below_min_if_needed_to_hit_target": False,
                            "adjustment_logic": {
                                "if_above_target": {
                                    "action": "increase",
                                    "adjustment_percent": 0.25,
                                },
                                "if_below_target": {
                                    "action": "decrease",
                                    "adjustment_percent": 0.2,
                                },
                            },
                        },
                        "social_security_interaction": {
                            "reduce_after_husband_claim": False,
                            "reduction_percent": 0.0,
                        },
                        "safety_limits": {
                            "max_conversion": 0.0,
                            "min_conversion": {
                                "type": "floor_with_tax_guard",
                                "base": 0.0,
                                "reduce_if_exceeds_bracket": True,
                                "enforce_only_when_target_not_at_risk": True,
                            },
                        },
                        "tax_payment": {
                            "enabled": False,
                            "payment_timing": "same_year",
                            "estimated_tax_method": "incremental",
                            "source_order": ["taxable_bridge_account"],
                            "source_account_name": "Taxable Bridge Account",
                            "allow_roth_for_conversion_taxes": False,
                            "gross_up_conversion_if_needed": False,
                            "track_conversion_tax_separately": True,
                            "allow_bridge_for_living_expenses": True,
                            "prioritize_tax_use_first": True,
                            "use_bridge_for_living_only_if_absolutely_necessary": True,
                        },
                    },
                    "charitable_giving": {
                        "enabled": False,
                        "policy": {
                            "type": "greater_of",
                            "percent_of_income": 0.0,
                            "compare_to": "rmd",
                            "income_definition": "recurring_sources_only",
                            "recurring_sources": ["va_disability"],
                        },
                        "qcd": {
                            "enabled": False,
                            "start_age": 70.5,
                            "annual_limit": 100000.0,
                            "allow_above_rmd": False,
                            "applies_to": ["traditional_ira"],
                            "tax_treatment": {
                                "reduces_rmd": True,
                                "excluded_from_taxable_income": True,
                            },
                            "depletion_target": {
                                "enabled": False,
                                "owners": ["Husband"],
                                "target_age": 90,
                                "target_balance": 0.0,
                                "method": "level_annual_qcd",
                            },
                        },
                        "coordination_rules": {
                            "apply_qcd_before_rmd_taxation": True,
                            "if_ira_insufficient_for_giving": "skip_excess_giving",
                            "prohibit_other_accounts_for_giving": True,
                        },
                    },
                    "withdrawals": {
                        "order": ["taxable_bridge_account", "traditional_ira"],
                        "restrictions": {"never_use_accounts": ["Car Fund"]},
                        "bridge_usage": {
                            "pre_age_70": {
                                "primary_use": "conversion_taxes",
                                "secondary_use": "living_expenses_if_necessary",
                            },
                            "post_age_70": {"use_as": "growth_and_liquidity"},
                        },
                        "rmd_handling": {
                            "enforce": True,
                            "allow_qcd_to_satisfy_rmd": True,
                            "withdraw_remaining_rmd_if_needed": True,
                        },
                    },
                    "analytics": {
                        "required_outputs": ["yearly_ledger"],
                        "conversion_efficiency": {"enabled": False, "track": []},
                        "rmd_projection": {"enabled": False, "track": []},
                        "charitable_tracking": {"enabled": False, "track": []},
                    },
                    "account_rollovers": {
                        "enabled": False,
                        "roll_traditional_401k_to_ira": True,
                        "roll_roth_401k_to_ira": True,
                    },
                },
                "historical_analysis": {
                    "enabled": False,
                    "dataset": "damodaran_us_annual_1970_2025",
                    "selected_start_year": None,
                    "success_rate_target": 0.9,
                    "use_historical_inflation_for_expenses": True,
                    "use_historical_inflation_for_income_cola": True,
                    "weighting": {
                        "method": "equal",
                        "modern_start_year": None,
                        "modern_weight_multiplier": 1.0,
                    },
                    "account_type_return_policies": {},
                },
                "overrides": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    scenario_path = tmp_path / "scenario_high_inflation.yaml"
    scenario_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "scenario_name": "High Inflation",
                    "version": "1.0.0",
                    "description": "Inflation stress scenario",
                },
                "overrides": {
                    "assumptions": {"inflation_rate": 0.04},
                    "expenses": {
                        "base_living": {"inflation_rate": 0.04},
                        "travel": {"inflation_rate": 0.04},
                    },
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    loaded = load_scenario(scenario_path)

    assert loaded.scenario.metadata.scenario_name == "High Inflation"
    assert loaded.scenario.assumptions.inflation_rate == 0.04
    assert loaded.scenario.expenses.base_living.inflation_rate == 0.04
    assert loaded.scenario.income.va_disability.amount_monthly == 4158.0
    assert loaded.scenario.overrides == {
        "assumptions": {"inflation_rate": 0.04},
        "expenses": {
            "base_living": {"inflation_rate": 0.04},
            "travel": {"inflation_rate": 0.04},
        },
    }


def test_loader_replaces_lists_when_merging_scenario_delta(tmp_path):
    baseline_path = tmp_path / "baseline_canonical.yaml"
    baseline_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "scenario_name": "Canonical Baseline",
                    "version": "1.0.0",
                    "description": "Base scenario",
                    "created": "2026-04-20",
                    "currency": "USD",
                    "cadence": "annual",
                },
                "simulation": {
                    "start_date": "2026-07-01",
                    "retirement_date": "2033-01-01",
                    "end_condition": {"wife_age": 90},
                    "proration": {"enabled": True, "method": "daily"},
                },
                "assumptions": {
                    "inflation_rate": 0.025,
                    "investment_return_default": 0.05,
                    "success_age": 90,
                    "ss_cola": 0.022,
                    "va_cola": 0.025,
                    "rmd_start_age": 75,
                },
                "validation": {
                    "strict": False,
                    "override_merge_rules": {
                        "object_merge": "deep_merge",
                        "list_merge": "replace_unless_keyed",
                    },
                },
                "household": {
                    "filing_status_initial": "mfj",
                    "state_of_residence": "Missouri",
                    "husband": {
                        "label": "Husband",
                        "birth_month": 7,
                        "birth_year": 1967,
                        "current_age": 58,
                        "retirement_age": 65,
                        "modeled_death": {"enabled": False, "death_year": None},
                    },
                    "wife": {
                        "label": "Wife",
                        "birth_month": 2,
                        "birth_year": 1967,
                        "current_age": 59,
                        "retirement_age": 65,
                        "modeled_death": {"enabled": False, "death_year": None},
                    },
                    "expense_stepdown_after_husband_death": {
                        "enabled": True,
                        "surviving_expense_ratio": 0.7,
                    },
                },
                "income": {
                    "earned_income": {
                        "husband": {
                            "enabled": True,
                            "income_type": "w2",
                            "taxable": True,
                            "annual_gross_salary_start": 195000.0,
                            "annual_raise_rate": 0.02,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        },
                        "wife": {
                            "enabled": True,
                            "income_type": "1099",
                            "taxable": True,
                            "annual_gross_salary_start": 60000.0,
                            "annual_raise_rate": 0.02,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        },
                    },
                    "va_disability": {
                        "owner": "Husband",
                        "amount_monthly": 4158.0,
                        "taxable": False,
                        "cola_rate": 0.025,
                        "start_date": "2026-07-01",
                        "end_at_death": True,
                    },
                    "va_survivor_benefit": {
                        "owner": "Wife",
                        "enabled": False,
                        "conditional_start": {"husband_death_after": "2035-02-01"},
                        "amount_monthly": 0.0,
                        "taxable": False,
                        "cola_rate": 0.025,
                    },
                    "social_security": {
                        "husband": {
                            "claim_age": 70,
                            "amount_monthly_at_claim": 5002.0,
                            "cola_rate": 0.025,
                        },
                        "wife": {
                            "claim_age": 65,
                            "amount_monthly_at_claim": 1500.0,
                            "cola_rate": 0.025,
                        },
                        "survivor_rule": {
                            "enabled": True,
                            "step_up_to_higher_benefit": True,
                        },
                    },
                    "pension_income": {
                        "wife_imrf": {
                            "enabled": True,
                            "owner": "Wife",
                            "amount_monthly": 302.9,
                            "taxable": True,
                            "cola_rate": 0.025,
                            "start_date": "2026-07-01",
                        }
                    },
                },
                "accounts": [
                    {
                        "name": "Husband Traditional IRA",
                        "type": "traditional_ira",
                        "owner": "Husband",
                        "starting_balance": 376000.0,
                        "return_rate": 0.05,
                    },
                    {
                        "name": "Car Fund",
                        "type": "restricted_cash",
                        "owner": "Household",
                        "starting_balance": 22000.0,
                        "return_rate": 0.033,
                        "withdrawals_enabled": False,
                        "contributions_enabled": True,
                        "restriction": "never_use_for_retirement_model_cashflows",
                    },
                    {
                        "name": "Taxable Bridge Account",
                        "type": "taxable",
                        "owner": "Household",
                        "starting_balance": 0.0,
                        "return_rate": 0.03,
                        "withdrawals_enabled": True,
                        "contributions_enabled": True,
                    },
                ],
                "contributions": {
                    "enabled": True,
                    "surplus_allocation": {
                        "enabled": True,
                        "destination_account": "Taxable Bridge Account",
                        "start_age_husband": 70,
                    },
                    "schedules": [
                        {
                            "name": "Bridge funding",
                            "enabled": True,
                            "owner": "Household",
                            "destination_account": "Taxable Bridge Account",
                            "type": "fixed_monthly",
                            "amount_monthly": 1000.0,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        },
                        {
                            "name": "Second funding line",
                            "enabled": True,
                            "owner": "Household",
                            "destination_account": "Taxable Bridge Account",
                            "type": "fixed_annual",
                            "amount_annual": 1200.0,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        },
                    ],
                },
                "expenses": {
                    "base_living": {
                        "amount_annual": 70000.0,
                        "inflation_rate": 0.025,
                        "adjustments": [],
                    },
                    "travel": {"amount_annual": 0.0, "inflation_rate": 0.025},
                    "housing": {
                        "property_tax": {
                            "amount_annual": 7000.0,
                            "start_date": "2026-07-01",
                            "inflation_rate": 0.02,
                        },
                        "homeowners_insurance": {
                            "amount_annual": 2500.0,
                            "start_date": "2026-07-01",
                            "inflation_rate": 0.02,
                        },
                    },
                },
                "spending_guardrails": {
                    "enabled": True,
                    "base_spending_annual": 70000.0,
                    "floor_spending_annual": 60000.0,
                    "trigger": {"type": "resource_pressure"},
                },
                "mortgage": {
                    "enabled": False,
                    "starting_balance": 0.0,
                    "interest_rate": 0.06,
                    "remaining_term_years": 15,
                    "scheduled_payment_monthly": None,
                    "payment_frequency": "monthly",
                    "payoff_by_age": {
                        "enabled": False,
                        "target_age": 65,
                        "target_date": "2032-12-31",
                        "method": "compute_extra_principal",
                    },
                },
                "taxes": {"conversion_tax_payment": {"treatment": "annual_cash_outflow_same_year"}},
                "state_tax": {
                    "model": "effective_rate",
                    "taxable_income_basis": "federal_taxable_income",
                    "effective_rate": 0.04,
                },
                "medicare": {
                    "irmaa": {
                        "reconsideration": {
                            "enabled": True,
                            "event": "work_stoppage",
                            "use_current_year_magi": True,
                            "apply_after_retirement": True,
                            "override_conversion_guardrails": False,
                        }
                    }
                },
                "strategy": {
                    "roth_conversions": {
                        "enabled": False,
                        "strategy": "adaptive_ladder",
                        "base_policy": {
                            "active_ages": [65],
                            "base_conversion_amounts": {65: 0.0},
                        },
                        "tax_constraints": {
                            "max_marginal_bracket": 0.22,
                            "allow_partial_bracket_fill": True,
                        },
                        "irmaa_controls": {
                            "enabled": False,
                            "max_tier": 2,
                            "reduce_if_exceeded": True,
                        },
                        "market_adjustments": {
                            "enabled": False,
                            "signal_account_type": "traditional_ira",
                            "rules": [],
                            "bands": [],
                        },
                        "balance_targets": {
                            "enabled": False,
                            "traditional_ira_target_at_70": 0.0,
                            "acceptable_band_percent": 0.33,
                            "target_priority": "higher_than_min_conversion",
                            "allow_below_min_if_needed_to_hit_target": False,
                            "adjustment_logic": {
                                "if_above_target": {
                                    "action": "increase",
                                    "adjustment_percent": 0.25,
                                },
                                "if_below_target": {
                                    "action": "decrease",
                                    "adjustment_percent": 0.2,
                                },
                            },
                        },
                        "social_security_interaction": {
                            "reduce_after_husband_claim": False,
                            "reduction_percent": 0.0,
                        },
                        "safety_limits": {
                            "max_conversion": 0.0,
                            "min_conversion": {
                                "type": "floor_with_tax_guard",
                                "base": 0.0,
                                "reduce_if_exceeds_bracket": True,
                                "enforce_only_when_target_not_at_risk": True,
                            },
                        },
                        "tax_payment": {
                            "enabled": False,
                            "payment_timing": "same_year",
                            "estimated_tax_method": "incremental",
                            "source_order": ["taxable_bridge_account"],
                            "source_account_name": "Taxable Bridge Account",
                            "allow_roth_for_conversion_taxes": False,
                            "gross_up_conversion_if_needed": False,
                            "track_conversion_tax_separately": True,
                            "allow_bridge_for_living_expenses": True,
                            "prioritize_tax_use_first": True,
                            "use_bridge_for_living_only_if_absolutely_necessary": True,
                        },
                    },
                    "charitable_giving": {
                        "enabled": False,
                        "policy": {
                            "type": "greater_of",
                            "percent_of_income": 0.0,
                            "compare_to": "rmd",
                            "income_definition": "recurring_sources_only",
                            "recurring_sources": ["va_disability"],
                        },
                        "qcd": {
                            "enabled": False,
                            "start_age": 70.5,
                            "annual_limit": 100000.0,
                            "allow_above_rmd": False,
                            "applies_to": ["traditional_ira"],
                            "tax_treatment": {
                                "reduces_rmd": True,
                                "excluded_from_taxable_income": True,
                            },
                            "depletion_target": {
                                "enabled": False,
                                "owners": ["Husband"],
                                "target_age": 90,
                                "target_balance": 0.0,
                                "method": "level_annual_qcd",
                            },
                        },
                        "coordination_rules": {
                            "apply_qcd_before_rmd_taxation": True,
                            "if_ira_insufficient_for_giving": "skip_excess_giving",
                            "prohibit_other_accounts_for_giving": True,
                        },
                    },
                    "withdrawals": {
                        "order": ["taxable_bridge_account", "traditional_ira"],
                        "restrictions": {"never_use_accounts": ["Car Fund"]},
                        "bridge_usage": {
                            "pre_age_70": {
                                "primary_use": "conversion_taxes",
                                "secondary_use": "living_expenses_if_necessary",
                            },
                            "post_age_70": {"use_as": "growth_and_liquidity"},
                        },
                        "rmd_handling": {
                            "enforce": True,
                            "allow_qcd_to_satisfy_rmd": True,
                            "withdraw_remaining_rmd_if_needed": True,
                        },
                    },
                    "analytics": {
                        "required_outputs": ["yearly_ledger"],
                        "conversion_efficiency": {"enabled": False, "track": []},
                        "rmd_projection": {"enabled": False, "track": []},
                        "charitable_tracking": {"enabled": False, "track": []},
                    },
                    "account_rollovers": {
                        "enabled": False,
                        "roll_traditional_401k_to_ira": True,
                        "roll_roth_401k_to_ira": True,
                    },
                },
                "historical_analysis": {
                    "enabled": False,
                    "dataset": "damodaran_us_annual_1970_2025",
                    "selected_start_year": None,
                    "success_rate_target": 0.9,
                    "use_historical_inflation_for_expenses": True,
                    "use_historical_inflation_for_income_cola": True,
                    "weighting": {
                        "method": "equal",
                        "modern_start_year": None,
                        "modern_weight_multiplier": 1.0,
                    },
                    "account_type_return_policies": {},
                },
                "overrides": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    scenario_path = tmp_path / "scenario_replace_contributions.yaml"
    scenario_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "scenario_name": "Contribution Replacement",
                    "version": "1.0.0",
                    "description": "Replace contribution schedules",
                },
                "overrides": {
                    "contributions": {
                        "schedules": [
                            {
                                "name": "Replacement schedule",
                                "enabled": True,
                                "owner": "Household",
                                "destination_account": "Taxable Bridge Account",
                                "type": "fixed_annual",
                                "amount_annual": 5000.0,
                                "start_date": "2026-07-01",
                                "end_date": "2032-12-31",
                            }
                        ]
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    loaded = load_scenario(scenario_path)

    assert len(loaded.scenario.contributions.schedules) == 1
    assert loaded.scenario.contributions.schedules[0].name == "Replacement schedule"


def test_loader_rejects_non_override_fields_in_scenario_delta(tmp_path):
    baseline_path = tmp_path / "baseline_canonical.yaml"
    baseline_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "scenario_name": "Canonical Baseline",
                    "version": "1.0.0",
                    "description": "Base scenario",
                    "created": "2026-04-20",
                    "currency": "USD",
                    "cadence": "annual",
                },
                "simulation": {
                    "start_date": "2026-07-01",
                    "retirement_date": "2033-01-01",
                    "end_condition": {"wife_age": 90},
                    "proration": {"enabled": True, "method": "daily"},
                },
                "assumptions": {
                    "inflation_rate": 0.025,
                    "investment_return_default": 0.05,
                    "success_age": 90,
                    "ss_cola": 0.022,
                    "va_cola": 0.025,
                    "rmd_start_age": 75,
                },
                "validation": {
                    "strict": False,
                    "override_merge_rules": {
                        "object_merge": "deep_merge",
                        "list_merge": "replace_unless_keyed",
                    },
                },
                "household": {
                    "filing_status_initial": "mfj",
                    "state_of_residence": "Missouri",
                    "husband": {
                        "label": "Husband",
                        "birth_month": 7,
                        "birth_year": 1967,
                        "current_age": 58,
                        "retirement_age": 65,
                        "modeled_death": {"enabled": False, "death_year": None},
                    },
                    "wife": {
                        "label": "Wife",
                        "birth_month": 2,
                        "birth_year": 1967,
                        "current_age": 59,
                        "retirement_age": 65,
                        "modeled_death": {"enabled": False, "death_year": None},
                    },
                    "expense_stepdown_after_husband_death": {
                        "enabled": True,
                        "surviving_expense_ratio": 0.7,
                    },
                },
                "income": {
                    "earned_income": {
                        "husband": {
                            "enabled": True,
                            "income_type": "w2",
                            "taxable": True,
                            "annual_gross_salary_start": 195000.0,
                            "annual_raise_rate": 0.02,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        },
                        "wife": {
                            "enabled": True,
                            "income_type": "1099",
                            "taxable": True,
                            "annual_gross_salary_start": 60000.0,
                            "annual_raise_rate": 0.02,
                            "start_date": "2026-07-01",
                            "end_date": "2032-12-31",
                        },
                    },
                    "va_disability": {
                        "owner": "Husband",
                        "amount_monthly": 4158.0,
                        "taxable": False,
                        "cola_rate": 0.025,
                        "start_date": "2026-07-01",
                        "end_at_death": True,
                    },
                    "va_survivor_benefit": {
                        "owner": "Wife",
                        "enabled": False,
                        "conditional_start": {"husband_death_after": "2035-02-01"},
                        "amount_monthly": 0.0,
                        "taxable": False,
                        "cola_rate": 0.025,
                    },
                    "social_security": {
                        "husband": {
                            "claim_age": 70,
                            "amount_monthly_at_claim": 5002.0,
                            "cola_rate": 0.025,
                        },
                        "wife": {
                            "claim_age": 65,
                            "amount_monthly_at_claim": 1500.0,
                            "cola_rate": 0.025,
                        },
                        "survivor_rule": {
                            "enabled": True,
                            "step_up_to_higher_benefit": True,
                        },
                    },
                    "pension_income": {
                        "wife_imrf": {
                            "enabled": True,
                            "owner": "Wife",
                            "amount_monthly": 302.9,
                            "taxable": True,
                            "cola_rate": 0.025,
                            "start_date": "2026-07-01",
                        }
                    },
                },
                "accounts": [
                    {
                        "name": "Husband Traditional IRA",
                        "type": "traditional_ira",
                        "owner": "Husband",
                        "starting_balance": 376000.0,
                        "return_rate": 0.05,
                    },
                    {
                        "name": "Car Fund",
                        "type": "restricted_cash",
                        "owner": "Household",
                        "starting_balance": 22000.0,
                        "return_rate": 0.033,
                        "withdrawals_enabled": False,
                        "contributions_enabled": True,
                        "restriction": "never_use_for_retirement_model_cashflows",
                    },
                    {
                        "name": "Taxable Bridge Account",
                        "type": "taxable",
                        "owner": "Household",
                        "starting_balance": 0.0,
                        "return_rate": 0.03,
                        "withdrawals_enabled": True,
                        "contributions_enabled": True,
                    },
                ],
                "contributions": {
                    "enabled": True,
                    "surplus_allocation": {
                        "enabled": True,
                        "destination_account": "Taxable Bridge Account",
                        "start_age_husband": 70,
                    },
                    "schedules": [],
                },
                "expenses": {
                    "base_living": {
                        "amount_annual": 70000.0,
                        "inflation_rate": 0.025,
                        "adjustments": [],
                    },
                    "travel": {"amount_annual": 0.0, "inflation_rate": 0.025},
                    "housing": {
                        "property_tax": {
                            "amount_annual": 7000.0,
                            "start_date": "2026-07-01",
                            "inflation_rate": 0.02,
                        },
                        "homeowners_insurance": {
                            "amount_annual": 2500.0,
                            "start_date": "2026-07-01",
                            "inflation_rate": 0.02,
                        },
                    },
                },
                "spending_guardrails": {
                    "enabled": True,
                    "base_spending_annual": 70000.0,
                    "floor_spending_annual": 60000.0,
                    "trigger": {"type": "resource_pressure"},
                },
                "mortgage": {
                    "enabled": False,
                    "starting_balance": 0.0,
                    "interest_rate": 0.06,
                    "remaining_term_years": 15,
                    "scheduled_payment_monthly": None,
                    "payment_frequency": "monthly",
                    "payoff_by_age": {
                        "enabled": False,
                        "target_age": 65,
                        "target_date": "2032-12-31",
                        "method": "compute_extra_principal",
                    },
                },
                "taxes": {"conversion_tax_payment": {"treatment": "annual_cash_outflow_same_year"}},
                "state_tax": {
                    "model": "effective_rate",
                    "taxable_income_basis": "federal_taxable_income",
                    "effective_rate": 0.04,
                },
                "medicare": {
                    "irmaa": {
                        "reconsideration": {
                            "enabled": True,
                            "event": "work_stoppage",
                            "use_current_year_magi": True,
                            "apply_after_retirement": True,
                            "override_conversion_guardrails": False,
                        }
                    }
                },
                "strategy": {
                    "roth_conversions": {
                        "enabled": False,
                        "strategy": "adaptive_ladder",
                        "base_policy": {
                            "active_ages": [65],
                            "base_conversion_amounts": {65: 0.0},
                        },
                        "tax_constraints": {
                            "max_marginal_bracket": 0.22,
                            "allow_partial_bracket_fill": True,
                        },
                        "irmaa_controls": {
                            "enabled": False,
                            "max_tier": 2,
                            "reduce_if_exceeded": True,
                        },
                        "market_adjustments": {
                            "enabled": False,
                            "signal_account_type": "traditional_ira",
                            "rules": [],
                            "bands": [],
                        },
                        "balance_targets": {
                            "enabled": False,
                            "traditional_ira_target_at_70": 0.0,
                            "acceptable_band_percent": 0.33,
                            "target_priority": "higher_than_min_conversion",
                            "allow_below_min_if_needed_to_hit_target": False,
                            "adjustment_logic": {
                                "if_above_target": {
                                    "action": "increase",
                                    "adjustment_percent": 0.25,
                                },
                                "if_below_target": {
                                    "action": "decrease",
                                    "adjustment_percent": 0.2,
                                },
                            },
                        },
                        "social_security_interaction": {
                            "reduce_after_husband_claim": False,
                            "reduction_percent": 0.0,
                        },
                        "safety_limits": {
                            "max_conversion": 0.0,
                            "min_conversion": {
                                "type": "floor_with_tax_guard",
                                "base": 0.0,
                                "reduce_if_exceeds_bracket": True,
                                "enforce_only_when_target_not_at_risk": True,
                            },
                        },
                        "tax_payment": {
                            "enabled": False,
                            "payment_timing": "same_year",
                            "estimated_tax_method": "incremental",
                            "source_order": ["taxable_bridge_account"],
                            "source_account_name": "Taxable Bridge Account",
                            "allow_roth_for_conversion_taxes": False,
                            "gross_up_conversion_if_needed": False,
                            "track_conversion_tax_separately": True,
                            "allow_bridge_for_living_expenses": True,
                            "prioritize_tax_use_first": True,
                            "use_bridge_for_living_only_if_absolutely_necessary": True,
                        },
                    },
                    "charitable_giving": {
                        "enabled": False,
                        "policy": {
                            "type": "greater_of",
                            "percent_of_income": 0.0,
                            "compare_to": "rmd",
                            "income_definition": "recurring_sources_only",
                            "recurring_sources": ["va_disability"],
                        },
                        "qcd": {
                            "enabled": False,
                            "start_age": 70.5,
                            "annual_limit": 100000.0,
                            "allow_above_rmd": False,
                            "applies_to": ["traditional_ira"],
                            "tax_treatment": {
                                "reduces_rmd": True,
                                "excluded_from_taxable_income": True,
                            },
                            "depletion_target": {
                                "enabled": False,
                                "owners": ["Husband"],
                                "target_age": 90,
                                "target_balance": 0.0,
                                "method": "level_annual_qcd",
                            },
                        },
                        "coordination_rules": {
                            "apply_qcd_before_rmd_taxation": True,
                            "if_ira_insufficient_for_giving": "skip_excess_giving",
                            "prohibit_other_accounts_for_giving": True,
                        },
                    },
                    "withdrawals": {
                        "order": ["taxable_bridge_account", "traditional_ira"],
                        "restrictions": {"never_use_accounts": ["Car Fund"]},
                        "bridge_usage": {
                            "pre_age_70": {
                                "primary_use": "conversion_taxes",
                                "secondary_use": "living_expenses_if_necessary",
                            },
                            "post_age_70": {"use_as": "growth_and_liquidity"},
                        },
                        "rmd_handling": {
                            "enforce": True,
                            "allow_qcd_to_satisfy_rmd": True,
                            "withdraw_remaining_rmd_if_needed": True,
                        },
                    },
                    "analytics": {
                        "required_outputs": ["yearly_ledger"],
                        "conversion_efficiency": {"enabled": False, "track": []},
                        "rmd_projection": {"enabled": False, "track": []},
                        "charitable_tracking": {"enabled": False, "track": []},
                    },
                    "account_rollovers": {
                        "enabled": False,
                        "roll_traditional_401k_to_ira": True,
                        "roll_roth_401k_to_ira": True,
                    },
                },
                "historical_analysis": {
                    "enabled": False,
                    "dataset": "damodaran_us_annual_1970_2025",
                    "selected_start_year": None,
                    "success_rate_target": 0.9,
                    "use_historical_inflation_for_expenses": True,
                    "use_historical_inflation_for_income_cola": True,
                    "weighting": {
                        "method": "equal",
                        "modern_start_year": None,
                        "modern_weight_multiplier": 1.0,
                    },
                    "account_type_return_policies": {},
                },
                "overrides": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    scenario_path = tmp_path / "scenario_invalid_root.yaml"
    scenario_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "scenario_name": "Invalid Delta",
                    "version": "1.0.0",
                    "description": "Invalid scenario delta",
                },
                "simulation": {"start_date": "2026-08-01"},
                "overrides": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="may only define metadata and overrides"):
        load_scenario(scenario_path)


def test_repo_high_inflation_scenario_inherits_canonical_baseline():
    loaded = load_scenario(Path("scenarios/scenario_high_inflation.yaml"))

    assert loaded.scenario.metadata.scenario_name == "High Inflation Stress"
    assert loaded.scenario.assumptions.inflation_rate == 0.04
    assert loaded.scenario.expenses.base_living.inflation_rate == 0.04
    assert loaded.scenario.expenses.housing.property_tax.inflation_rate == 0.03
    assert loaded.scenario.strategy.withdrawals.order == [
        "taxable_bridge_account",
        "traditional_ira",
        "traditional_401k",
        "roth_ira",
        "roth_401k",
    ]
    assert loaded.scenario.overrides["assumptions"]["inflation_rate"] == 0.04


def test_repo_historical_analysis_scenario_replaces_policy_map_from_canonical_baseline():
    loaded = load_scenario(Path("scenarios/scenario_historical_analysis.yaml"))

    assert loaded.scenario.metadata.scenario_name == "Historical Analysis Comparison"
    assert loaded.scenario.historical_analysis.enabled is True
    assert loaded.scenario.historical_analysis.weighting.method == "modern_heavier"
    assert set(loaded.scenario.historical_analysis.account_type_return_policies) == {
        "cash",
        "traditional_ira",
        "traditional_401k",
        "roth_ira",
        "roth_401k",
        "hsa",
        "taxable",
        "restricted_cash",
    }


def test_loader_rejects_scenario_delta_without_canonical_baseline(tmp_path):
    scenario_path = tmp_path / "scenario_orphan.yaml"
    scenario_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "scenario_name": "Orphan Delta",
                    "version": "1.0.0",
                    "description": "Delta without baseline",
                },
                "overrides": {"assumptions": {"inflation_rate": 0.04}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires sibling baseline_canonical.yaml"):
        load_scenario(scenario_path)


def test_loader_allows_soft_diagnostics_when_validation_is_not_strict(tmp_path, golden_payload):
    payload = golden_payload
    payload["validation"]["strict"] = False
    payload["household"]["husband"]["current_age"] = 99

    temp_path = tmp_path / "baseline_v9.9.9.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    loaded = load_scenario(temp_path)

    assert len(loaded.warnings) == 2
    assert any("filename version does not match" in warning.lower() for warning in loaded.warnings)
    assert any("household.husband.current_age=99" in warning for warning in loaded.warnings)


def test_loader_fails_soft_diagnostics_when_validation_is_strict(tmp_path, golden_payload):
    payload = golden_payload
    payload["validation"]["strict"] = True
    payload["household"]["husband"]["current_age"] = 99

    temp_path = tmp_path / "baseline_v9.9.9.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Strict validation failed") as exc_info:
        load_scenario(temp_path)

    message = str(exc_info.value)
    assert "filename version does not match" in message.lower()
    assert "household.husband.current_age=99" in message


def test_loader_strict_override_forces_failure_even_when_scenario_is_non_strict(
    tmp_path, golden_payload
):
    payload = golden_payload
    payload["validation"]["strict"] = False
    payload["household"]["husband"]["current_age"] = 99

    temp_path = tmp_path / "baseline_v9.9.9.yaml"
    temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Strict validation failed"):
        load_scenario(temp_path, strict_validation=True)

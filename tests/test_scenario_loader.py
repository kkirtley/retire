import pytest
import yaml

from retireplan.io import load_scenario


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

"""Stage 8 reporting tables and chart-series exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from retireplan.core import ProjectionResult
from retireplan.core.historical_analysis import HistoricalAnalysisResult
from retireplan.core.strategy import project_qcd_depletion_progress
from retireplan.core.timeline_builder import milestone_date_for_age
from retireplan.output_formatting import round_output_value
from retireplan.scenario import RetirementScenario


def build_reporting_bundle(
    result: ProjectionResult,
    scenario: RetirementScenario | None = None,
    historical_analysis: HistoricalAnalysisResult | None = None,
) -> dict[str, Any]:
    tables = {
        "yearly_overview": _yearly_overview_table(result),
        "cashflow": _cashflow_table(result),
        "tax_detail": _tax_detail_table(result),
        "account_balances": _account_balances_table(result),
    }
    if scenario is not None:
        tables["qcd_depletion"] = _qcd_depletion_table(result, scenario)
    if historical_analysis is not None:
        tables["historical_cohorts"] = _historical_cohorts_table(historical_analysis)
    charts = {
        "total_liquid_net_worth": _liquid_net_worth_chart(result),
        "income_vs_expenses": _income_vs_expenses_chart(result),
        "taxes_over_time": _taxes_chart(result),
        "account_balances_stacked": _account_balances_chart(result),
    }
    if historical_analysis is not None:
        charts["historical_terminal_net_worth"] = _historical_terminal_net_worth_chart(
            historical_analysis
        )
    bundle = {
        "summary": {
            "scenario_name": result.scenario_name,
            "version": result.version,
            "success": result.success,
            "failure_year": result.failure_year,
            "rows": len(result.ledger),
            "historical_analysis_included": historical_analysis is not None,
        },
        "output_contract": result.output_contract,
        "tables": tables,
        "charts": charts,
    }
    return round_output_value(bundle)


def write_reporting_bundle(bundle: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    reporting_path = output_dir / "reporting.json"
    chart_series_path = output_dir / "chart_series.json"

    reporting_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    chart_series_path.write_text(json.dumps(bundle["charts"], indent=2), encoding="utf-8")

    table_paths: dict[str, str] = {}
    for name, table in bundle["tables"].items():
        path = output_dir / f"{name}.csv"
        _write_csv_table(path, table["columns"], table["rows"])
        table_paths[name] = str(path)

    return {
        "reporting_json": str(reporting_path),
        "chart_series_json": str(chart_series_path),
        "tables": table_paths,
    }


def _yearly_overview_table(result: ProjectionResult) -> dict[str, Any]:
    columns = [
        "year",
        "husband/wife ages",
        "husband_age",
        "wife_age",
        "filing_status",
        "income_total",
        "expenses_total",
        "taxes_total",
        "rollover_total",
        "roth_conversion_total",
        "qcd_distribution_total",
        "net_cash_flow",
        "liquid_resources_end",
        "success",
    ]
    rows = []
    for row in result.ledger:
        rows.append(
            {
                "year": row.year,
                "husband/wife ages": f"{row.husband_age} / {row.wife_age}",
                "husband_age": row.husband_age,
                "wife_age": row.wife_age,
                "filing_status": row.filing_status,
                "income_total": round(sum(row.income.values()), 2),
                "expenses_total": round(sum(row.expenses.values()), 2),
                "taxes_total": row.taxes.get("total", 0.0),
                "rollover_total": round(sum(row.rollovers.values()), 2),
                "roth_conversion_total": row.strategy.get("roth_conversion_total", 0.0),
                "qcd_distribution_total": round(sum(row.qcd_distributions.values()), 2),
                "net_cash_flow": row.net_cash_flow,
                "liquid_resources_end": row.liquid_resources_end,
                "success": row.success,
            }
        )
    return {"columns": columns, "rows": rows}


def _cashflow_table(result: ProjectionResult) -> dict[str, Any]:
    columns = [
        "year",
        "husband/wife ages",
        "total_income",
        "base_living",
        "travel",
        "housing_total",
        "medicare_total",
        "total_expenses",
        "non_conversion_tax_total",
        "operating_gap_before_withdrawals",
        "bridge_withdrawal_for_conversion_taxes",
        "bridge_withdrawal_for_operations",
        "total_bridge_withdrawal",
        "other_withdrawals",
        "surplus_to_bridge",
        "total_taxes",
        "total_contributions",
        "total_withdrawals",
        "total_qcd_distributions",
        "conversion_tax_payment",
        "net_cash_flow",
    ]
    rows = []
    for row in result.ledger:
        base_living = row.expenses.get("base_living", 0.0)
        travel = row.expenses.get("travel", 0.0)
        housing_total = round(
            row.expenses.get("property_tax", 0.0)
            + row.expenses.get("homeowners_insurance", 0.0)
            + row.expenses.get("mortgage_payment", 0.0),
            2,
        )
        medicare_total = row.medicare.get("total", 0.0)
        total_income = round(sum(row.income.values()), 2)
        total_expenses = round(sum(row.expenses.values()), 2)
        total_taxes = row.taxes.get("total", 0.0)
        conversion_tax_payment = row.strategy.get("conversion_tax_payment", 0.0)
        non_conversion_tax_total = round(max(total_taxes - conversion_tax_payment, 0.0), 2)
        operating_gap_before_withdrawals = round(
            max(total_expenses + non_conversion_tax_total - total_income, 0.0),
            2,
        )
        total_bridge_withdrawal = row.withdrawals.get("Taxable Bridge Account", 0.0)
        bridge_withdrawal_for_conversion_taxes = round(
            min(total_bridge_withdrawal, conversion_tax_payment),
            2,
        )
        bridge_withdrawal_for_operations = round(
            max(total_bridge_withdrawal - bridge_withdrawal_for_conversion_taxes, 0.0),
            2,
        )
        other_withdrawals = round(
            max(sum(row.withdrawals.values()) - total_bridge_withdrawal, 0.0),
            2,
        )
        rows.append(
            {
                "year": row.year,
                "husband/wife ages": f"{row.husband_age} / {row.wife_age}",
                "total_income": total_income,
                "base_living": base_living,
                "travel": travel,
                "housing_total": housing_total,
                "medicare_total": medicare_total,
                "total_expenses": total_expenses,
                "non_conversion_tax_total": non_conversion_tax_total,
                "operating_gap_before_withdrawals": operating_gap_before_withdrawals,
                "bridge_withdrawal_for_conversion_taxes": bridge_withdrawal_for_conversion_taxes,
                "bridge_withdrawal_for_operations": bridge_withdrawal_for_operations,
                "total_bridge_withdrawal": total_bridge_withdrawal,
                "other_withdrawals": other_withdrawals,
                "surplus_to_bridge": row.surplus_allocations.get("Taxable Bridge Account", 0.0),
                "total_taxes": total_taxes,
                "total_contributions": round(sum(row.contributions.values()), 2),
                "total_withdrawals": round(sum(row.withdrawals.values()), 2),
                "total_qcd_distributions": round(sum(row.qcd_distributions.values()), 2),
                "conversion_tax_payment": conversion_tax_payment,
                "net_cash_flow": row.net_cash_flow,
            }
        )
    return {"columns": columns, "rows": rows}


def _qcd_depletion_table(
    result: ProjectionResult,
    scenario: RetirementScenario,
) -> dict[str, Any]:
    columns = [
        "year",
        "husband/wife ages",
        "husband_balance",
        "husband_target_age",
        "husband_required_qcd",
        "husband_actual_qcd",
        "husband_projected_balance_at_target_age",
        "wife_balance",
        "wife_target_age",
        "wife_required_qcd",
        "wife_actual_qcd",
        "wife_projected_balance_at_target_age",
        "on_pace",
        "constrained",
    ]
    rows = []
    for row in result.ledger:
        owner_progress = {
            progress.owner: progress
            for progress in project_qcd_depletion_progress(
                scenario,
                year=row.year,
                husband_age=row.husband_age,
                wife_age=row.wife_age,
                husband_alive=row.husband_alive,
                wife_alive=row.wife_alive,
                account_balances_end=row.account_balances_end,
                qcd_distributions=row.qcd_distributions,
                alerts=row.alerts,
            )
        }
        if not owner_progress:
            continue
        if all(
            (
                row.year
                < milestone_date_for_age(
                    scenario.household.husband.birth_year,
                    scenario.household.husband.birth_month,
                    float(scenario.strategy.charitable_giving.qcd.start_age),
                ).year
                if owner == "Husband"
                else row.year
                < milestone_date_for_age(
                    scenario.household.wife.birth_year,
                    scenario.household.wife.birth_month,
                    float(scenario.strategy.charitable_giving.qcd.start_age),
                ).year
            )
            for owner in owner_progress
        ):
            continue
        husband = owner_progress.get("Husband")
        wife = owner_progress.get("Wife")
        rows.append(
            {
                "year": row.year,
                "husband/wife ages": f"{row.husband_age} / {row.wife_age}",
                "husband_balance": 0.0 if husband is None else husband.current_balance,
                "husband_target_age": None if husband is None else husband.target_age,
                "husband_required_qcd": 0.0 if husband is None else husband.annual_qcd_required,
                "husband_actual_qcd": 0.0 if husband is None else husband.actual_qcd,
                "husband_projected_balance_at_target_age": (
                    0.0 if husband is None else husband.projected_balance_at_target_age
                ),
                "wife_balance": 0.0 if wife is None else wife.current_balance,
                "wife_target_age": None if wife is None else wife.target_age,
                "wife_required_qcd": 0.0 if wife is None else wife.annual_qcd_required,
                "wife_actual_qcd": 0.0 if wife is None else wife.actual_qcd,
                "wife_projected_balance_at_target_age": (
                    0.0 if wife is None else wife.projected_balance_at_target_age
                ),
                "on_pace": all(progress.on_pace for progress in owner_progress.values()),
                "constrained": any(progress.constrained for progress in owner_progress.values()),
            }
        )
    return {"columns": columns, "rows": rows}


def _chart_axis_step(values: list[float]) -> float:
    if not values:
        return 50_000.0
    minimum = min(0.0, min(values))
    maximum = max(values)
    span = max(maximum - minimum, 50_000.0)
    rough_step = span / 8
    step_units = max(1, int((rough_step + 49_999.9999) // 50_000.0))
    return float(step_units * 50_000)


def _chart_age(row) -> int:
    return row.wife_age


def _tax_detail_table(result: ProjectionResult) -> dict[str, Any]:
    columns = ["year", "federal_tax", "state_tax", "total_tax", "medicare_total"]
    rows = []
    for row in result.ledger:
        rows.append(
            {
                "year": row.year,
                "federal_tax": row.taxes.get("federal", 0.0),
                "state_tax": row.taxes.get("state", 0.0),
                "total_tax": row.taxes.get("total", 0.0),
                "medicare_total": row.medicare.get("total", 0.0),
            }
        )
    return {"columns": columns, "rows": rows}


def _account_balances_table(result: ProjectionResult) -> dict[str, Any]:
    columns = ["year", "account", "balance_end"]
    rows = []
    for row in result.ledger:
        for account_name, balance in row.account_balances_end.items():
            rows.append(
                {
                    "year": row.year,
                    "account": account_name,
                    "balance_end": balance,
                }
            )
    return {"columns": columns, "rows": rows}


def _historical_cohorts_table(historical_analysis: HistoricalAnalysisResult) -> dict[str, Any]:
    columns = [
        "start_year",
        "end_year",
        "weight",
        "success",
        "failure_year",
        "terminal_net_worth",
        "total_taxes_paid",
        "total_roth_converted",
    ]
    rows = [cohort.__dict__ for cohort in historical_analysis.cohorts]
    return {"columns": columns, "rows": rows}


def _historical_terminal_net_worth_chart(
    historical_analysis: HistoricalAnalysisResult,
) -> dict[str, Any]:
    values = [cohort.terminal_net_worth for cohort in historical_analysis.cohorts]
    return {
        "title": "Historical Cohort Terminal Net Worth",
        "kind": "bar",
        "x_axis": "historical_start_year",
        "y_axis_step": _chart_axis_step(values),
        "series": [
            {
                "name": "terminal_net_worth",
                "points": [
                    {"historical_start_year": cohort.start_year, "value": cohort.terminal_net_worth}
                    for cohort in historical_analysis.cohorts
                ],
            }
        ],
    }


def _liquid_net_worth_chart(result: ProjectionResult) -> dict[str, Any]:
    values = [row.liquid_resources_end for row in result.ledger]
    return {
        "title": "Total Liquid Net Worth",
        "kind": "line",
        "x_axis": "age",
        "y_axis_step": _chart_axis_step(values),
        "series": [
            {
                "name": "liquid_resources_end",
                "points": [
                    {"age": _chart_age(row), "value": row.liquid_resources_end}
                    for row in result.ledger
                ],
            }
        ],
    }


def _income_vs_expenses_chart(result: ProjectionResult) -> dict[str, Any]:
    values = [round(sum(row.income.values()), 2) for row in result.ledger] + [
        round(sum(row.expenses.values()), 2) for row in result.ledger
    ]
    return {
        "title": "Income vs Expenses",
        "kind": "line",
        "x_axis": "age",
        "y_axis_step": _chart_axis_step(values),
        "series": [
            {
                "name": "income_total",
                "points": [
                    {"age": _chart_age(row), "value": round(sum(row.income.values()), 2)}
                    for row in result.ledger
                ],
            },
            {
                "name": "expenses_total",
                "points": [
                    {"age": _chart_age(row), "value": round(sum(row.expenses.values()), 2)}
                    for row in result.ledger
                ],
            },
        ],
    }


def _taxes_chart(result: ProjectionResult) -> dict[str, Any]:
    values = [
        value
        for row in result.ledger
        for value in (
            row.taxes.get("federal", 0.0),
            row.taxes.get("state", 0.0),
            row.taxes.get("total", 0.0),
        )
    ]
    return {
        "title": "Taxes Over Time",
        "kind": "line",
        "x_axis": "age",
        "y_axis_step": _chart_axis_step(values),
        "series": [
            {
                "name": "federal_tax",
                "points": [
                    {"age": _chart_age(row), "value": row.taxes.get("federal", 0.0)}
                    for row in result.ledger
                ],
            },
            {
                "name": "state_tax",
                "points": [
                    {"age": _chart_age(row), "value": row.taxes.get("state", 0.0)}
                    for row in result.ledger
                ],
            },
            {
                "name": "total_tax",
                "points": [
                    {"age": _chart_age(row), "value": row.taxes.get("total", 0.0)}
                    for row in result.ledger
                ],
            },
        ],
    }


def _account_balances_chart(result: ProjectionResult) -> dict[str, Any]:
    if not result.ledger:
        return {
            "title": "Account Balances",
            "kind": "stacked_area",
            "x_axis": "age",
            "y_axis_step": 50_000.0,
            "series": [],
        }

    grouped_series = {
        "Husband Traditional": lambda balances: sum(
            value
            for name, value in balances.items()
            if name.startswith("Husband ") and "Traditional" in name
        ),
        "Husband Roth": lambda balances: sum(
            value
            for name, value in balances.items()
            if name.startswith("Husband ") and "Roth" in name
        ),
        "Wife Traditional": lambda balances: sum(
            value
            for name, value in balances.items()
            if name.startswith("Wife ") and "Traditional" in name
        ),
        "Wife Roth": lambda balances: sum(
            value for name, value in balances.items() if name.startswith("Wife ") and "Roth" in name
        ),
        "Taxable": lambda balances: sum(
            value for name, value in balances.items() if "Taxable" in name
        ),
    }
    values = [
        round(series_builder(row.account_balances_end), 2)
        for series_builder in grouped_series.values()
        for row in result.ledger
    ]
    return {
        "title": "Account Balances",
        "kind": "stacked_area",
        "x_axis": "age",
        "y_axis_step": _chart_axis_step(values),
        "series": [
            {
                "name": series_name,
                "points": [
                    {
                        "age": _chart_age(row),
                        "value": round(series_builder(row.account_balances_end), 2),
                    }
                    for row in result.ledger
                ],
            }
            for series_name, series_builder in grouped_series.items()
        ],
    }


def _write_csv_table(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

"""Stage 8 reporting tables and chart-series exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from retireplan.core import ProjectionResult


def build_reporting_bundle(result: ProjectionResult) -> dict[str, Any]:
    tables = {
        "yearly_overview": _yearly_overview_table(result),
        "cashflow": _cashflow_table(result),
        "tax_detail": _tax_detail_table(result),
        "account_balances": _account_balances_table(result),
    }
    charts = {
        "total_liquid_net_worth": _liquid_net_worth_chart(result),
        "income_vs_expenses": _income_vs_expenses_chart(result),
        "taxes_over_time": _taxes_chart(result),
        "account_balances_stacked": _account_balances_chart(result),
    }
    return {
        "summary": {
            "scenario_name": result.scenario_name,
            "version": result.version,
            "success": result.success,
            "failure_year": result.failure_year,
            "rows": len(result.ledger),
        },
        "tables": tables,
        "charts": charts,
    }


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
                "net_cash_flow": row.net_cash_flow,
                "liquid_resources_end": row.liquid_resources_end,
                "success": row.success,
            }
        )
    return {"columns": columns, "rows": rows}


def _cashflow_table(result: ProjectionResult) -> dict[str, Any]:
    columns = [
        "year",
        "total_income",
        "total_expenses",
        "total_taxes",
        "total_contributions",
        "total_withdrawals",
        "net_cash_flow",
    ]
    rows = []
    for row in result.ledger:
        rows.append(
            {
                "year": row.year,
                "total_income": round(sum(row.income.values()), 2),
                "total_expenses": round(sum(row.expenses.values()), 2),
                "total_taxes": row.taxes.get("total", 0.0),
                "total_contributions": round(sum(row.contributions.values()), 2),
                "total_withdrawals": round(sum(row.withdrawals.values()), 2),
                "net_cash_flow": row.net_cash_flow,
            }
        )
    return {"columns": columns, "rows": rows}


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


def _liquid_net_worth_chart(result: ProjectionResult) -> dict[str, Any]:
    return {
        "title": "Total Liquid Net Worth",
        "kind": "line",
        "x_axis": "year",
        "series": [
            {
                "name": "liquid_resources_end",
                "points": [
                    {"year": row.year, "value": row.liquid_resources_end} for row in result.ledger
                ],
            }
        ],
    }


def _income_vs_expenses_chart(result: ProjectionResult) -> dict[str, Any]:
    return {
        "title": "Income vs Expenses",
        "kind": "line",
        "x_axis": "year",
        "series": [
            {
                "name": "income_total",
                "points": [
                    {"year": row.year, "value": round(sum(row.income.values()), 2)}
                    for row in result.ledger
                ],
            },
            {
                "name": "expenses_total",
                "points": [
                    {"year": row.year, "value": round(sum(row.expenses.values()), 2)}
                    for row in result.ledger
                ],
            },
        ],
    }


def _taxes_chart(result: ProjectionResult) -> dict[str, Any]:
    return {
        "title": "Taxes Over Time",
        "kind": "line",
        "x_axis": "year",
        "series": [
            {
                "name": "federal_tax",
                "points": [
                    {"year": row.year, "value": row.taxes.get("federal", 0.0)}
                    for row in result.ledger
                ],
            },
            {
                "name": "state_tax",
                "points": [
                    {"year": row.year, "value": row.taxes.get("state", 0.0)}
                    for row in result.ledger
                ],
            },
            {
                "name": "total_tax",
                "points": [
                    {"year": row.year, "value": row.taxes.get("total", 0.0)}
                    for row in result.ledger
                ],
            },
        ],
    }


def _account_balances_chart(result: ProjectionResult) -> dict[str, Any]:
    account_names = sorted(result.ledger[0].account_balances_end) if result.ledger else []
    return {
        "title": "Account Balances",
        "kind": "stacked_area",
        "x_axis": "year",
        "series": [
            {
                "name": account_name,
                "points": [
                    {
                        "year": row.year,
                        "value": row.account_balances_end.get(account_name, 0.0),
                    }
                    for row in result.ledger
                ],
            }
            for account_name in account_names
        ],
    }


def _write_csv_table(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

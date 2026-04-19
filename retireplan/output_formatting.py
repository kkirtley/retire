"""Helpers for rounding outward-facing output values without changing engine math."""

from __future__ import annotations

from typing import Any


def round_output_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, dict):
        return {key: round_output_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [round_output_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(round_output_value(item) for item in value)
    return value

"""Smoke tests to verify basic package structure."""

import retireplan


def test_package_imports():
    """Test that the package imports successfully."""
    assert retireplan.__version__ == "0.1.0"


def test_cli_imports():
    """Test that CLI module imports successfully."""
    from retireplan.cli import main

    assert main.app is not None

"""Smoke tests for package entry points."""

import retireplan


def test_package_imports():
    assert retireplan.__version__ == "0.1.0"
    assert retireplan.RetirementScenario is not None


def test_cli_imports():
    from retireplan.cli import main

    assert main.app is not None

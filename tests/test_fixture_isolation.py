import re
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent


def test_test_suite_does_not_reference_live_scenarios_directory():
    offenders: list[str] = []
    pattern = re.compile(r'joinpath\(\s*["\']scenarios["\']|/\s*["\']scenarios["\']')

    for path in TESTS_DIR.glob("test_*.py"):
        if path.name == Path(__file__).name:
            continue
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            offenders.append(path.name)

    assert offenders == []


def test_test_suite_does_not_reference_archived_baselines():
    offenders: list[str] = []
    pattern = re.compile(r"baseline_v1\.0\.1|baseline_v1\.0\.2")

    for path in TESTS_DIR.glob("test_*.py"):
        if path.name == Path(__file__).name:
            continue
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            offenders.append(path.name)

    assert offenders == []

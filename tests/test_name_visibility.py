"""Enforces the internal-name-visibility rule's decidable half: no module
under src/snakestream may import an underscore-prefixed name from another
module in the package. See design decision 3 of
name-by-visibility-not-underscore for why this is a test rather than a lint
rule for now."""

from __future__ import annotations

import ast
import glob

import pytest

_SRC_ROOT = "src/snakestream"


def _cross_module_private_imports(paths: list[str]) -> list[tuple[str, str, str]]:
    """Every (importing module, defining module, name) triple where one of the
    given files imports an underscore-prefixed name from a module whose path
    starts with "snakestream". Walks the whole AST, not just module-level
    statements, so a function-local import is covered too."""
    findings = []
    for path in paths:
        with open(path) as f:
            tree = ast.parse(f.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("snakestream"):
                findings.extend((path, node.module, alias.name) for alias in node.names if alias.name.startswith("_"))
    return findings


def _format_findings(findings: list[tuple[str, str, str]]) -> str:
    lines = [f"{importer} imports {name!r} from {definer!r}" for importer, definer, name in findings]
    return "Cross-module private imports:\n" + "\n".join(lines)


def test_no_module_imports_a_private_name_from_another_module() -> None:
    findings = _cross_module_private_imports(sorted(glob.glob(f"{_SRC_ROOT}/*.py")))
    if findings:
        pytest.fail(_format_findings(findings))


def test_the_check_reports_importer_definer_and_name_on_a_violation(tmp_path) -> None:
    violating = tmp_path / "violating_module.py"
    violating.write_text("from snakestream.sink import _UNSET\n")

    findings = _cross_module_private_imports([str(violating)])
    message = _format_findings(findings)

    assert str(violating) in message
    assert "snakestream.sink" in message
    assert "_UNSET" in message


def test_a_tests_module_reaching_into_a_private_name_is_not_inspected() -> None:
    # test_racing_encounter_order.py and test_comparator_segments.py both do
    # legitimate white-box testing, importing underscore-prefixed names
    # straight from their modules under test (snakestream.fork_join's
    # _pull_round, snakestream.comparator's _is_comparator_arity). The check
    # itself can detect that shape when pointed at it - this isn't vacuous -
    # but the production check below only ever globs src/snakestream/*.py, so
    # these two files are never in its scope and neither import is ever
    # reported.
    findings = _cross_module_private_imports(["tests/test_racing_encounter_order.py", "tests/test_comparator_segments.py"])
    assert ("tests/test_racing_encounter_order.py", "snakestream.fork_join", "_pull_round") in findings
    assert ("tests/test_comparator_segments.py", "snakestream.comparator", "_is_comparator_arity") in findings

    scanned = sorted(glob.glob(f"{_SRC_ROOT}/*.py"))
    assert "tests/test_racing_encounter_order.py" not in scanned
    assert "tests/test_comparator_segments.py" not in scanned

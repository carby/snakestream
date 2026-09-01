import shutil
import subprocess
from pathlib import Path

TYPING_DIR = Path(__file__).parent / "typing"
TY = shutil.which("ty")


def _check(filename: str) -> subprocess.CompletedProcess[str]:
    assert TY is not None, "ty must be on PATH (dev dependency, see pyproject.toml)"
    return subprocess.run(
        [TY, "check", str(TYPING_DIR / filename)],
        capture_output=True,
        text=True,
        check=False,  # callers assert on returncode; a non-zero exit is the expected result
    )


def test_element_type_mismatch_after_map_is_caught() -> None:
    result = _check("bad_stream_map.py")
    assert result.returncode != 0
    assert "unresolved-attribute" in result.stdout


def test_generic_stream_usage_type_checks_cleanly() -> None:
    result = _check("good_stream_types.py")
    assert result.returncode == 0, result.stdout


def test_to_map_with_a_container_and_no_merge_function_is_rejected() -> None:
    """The only thing enforcing "no to_map(k, v, map_supplier) form".

    Java has no such overload, and the exclusion is deliberately left to the
    declared surface rather than a runtime raise: telling a merge function from
    a mapping type would mean inspecting a callable, and both are callables of
    the right shape.
    """
    result = _check("bad_to_map_container_without_merge.py")
    assert result.returncode != 0
    assert "no-matching-overload" in result.stdout

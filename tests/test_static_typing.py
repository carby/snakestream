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
    )


def test_element_type_mismatch_after_map_is_caught() -> None:
    result = _check("bad_stream_map.py")
    assert result.returncode != 0
    assert "unresolved-attribute" in result.stdout


def test_generic_stream_usage_type_checks_cleanly() -> None:
    result = _check("good_stream_types.py")
    assert result.returncode == 0, result.stdout

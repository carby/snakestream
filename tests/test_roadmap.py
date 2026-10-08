"""Runs `tools/roadmap.py check` so the roadmap fails the build rather than rotting.

The rules themselves - frontmatter schema, bucket criteria, generated indexes,
and every `refs` entry resolving against openspec/ and the tree - live in the
vendored script and are tested where it comes from; see roadmap/README.md."""

from __future__ import annotations

import subprocess
import sys


def test_the_roadmap_passes_its_own_check() -> None:
    result = subprocess.run(
        [sys.executable, "tools/roadmap.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

"""Runs `roadmap check` so the roadmap fails the build rather than rotting.

The rules themselves - frontmatter schema, bucket criteria, generated indexes,
and every `refs` entry resolving against openspec/ and the tree - live in the
roadmap CLI (the simple-agentic-roadmap-skill npm package) and are tested
where it comes from; see roadmap/README.md. This runs the release
roadmap/roadmap.toml pins, through npx, so it needs Node 22 or later. Without
npx the test is skipped locally and fails in CI."""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROADMAP_TOML = Path(__file__).resolve().parent.parent / "roadmap" / "roadmap.toml"


def test_the_roadmap_passes_its_own_check() -> None:
    npx = shutil.which("npx")
    if npx is None:
        if os.environ.get("CI"):
            pytest.fail("npx not found: the roadmap check needs Node 22 or later")
        pytest.skip("npx not found: the roadmap check needs Node 22 or later")

    pin = tomllib.loads(ROADMAP_TOML.read_text(encoding="utf-8"))["version"]
    result = subprocess.run(
        [npx, "--yes", f"--package=simple-agentic-roadmap-skill@{pin}", "--", "roadmap", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

"""Enforces roadmap/'s schema so the queue fails the build rather than rotting.

The half worth having is the ref check: an item naming an openspec change, a
spec or a source file is resolved against the tree, so a rename breaks CI
instead of leaving a pointer that reads fine and is wrong. See
tools/roadmap_index.py for the schema itself and roadmap/README.md for the
entry criteria the bucket rules encode."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "tools")

import roadmap_index


@pytest.fixture(scope="module")
def items() -> list[roadmap_index.Item]:
    return roadmap_index.load()


def test_every_item_satisfies_the_schema_and_its_bucket_criterion(items) -> None:
    if problems := roadmap_index.validate(items):
        pytest.fail("Roadmap problems:\n" + "\n".join(problems))


def test_the_index_matches_the_items_it_summarises(items) -> None:
    committed = roadmap_index.README.read_text()
    assert committed == roadmap_index.readme_with_index(items), (
        "roadmap/README.md's index is stale; run `python tools/roadmap_index.py`"
    )


def test_there_is_at_least_one_item_so_the_checks_are_not_vacuous(items) -> None:
    assert items
    assert all(item.body.strip() for item in items), "an item with no prose is a title, not an item"


def test_a_missing_frontmatter_fence_is_reported_with_the_path(tmp_path) -> None:
    orphan = tmp_path / "no-fence.md"
    orphan.write_text("Just prose, no metadata.\n")

    with pytest.raises(ValueError, match=r"no-fence\.md: no \+\+\+-fenced TOML frontmatter"):
        roadmap_index.parse(orphan)


def test_malformed_toml_is_reported_with_the_path(tmp_path) -> None:
    broken = tmp_path / "broken.md"
    broken.write_text('+++\nid = "broken\n+++\nBody.\n')

    with pytest.raises(ValueError, match=r"broken\.md: malformed TOML frontmatter"):
        roadmap_index.parse(broken)


@pytest.mark.parametrize(
    ("frontmatter", "expected"),
    [
        ('bucket = "someday"', "is not one of now, next, later"),
        ('bucket = "later"', "must name what it is blocked_on"),
        ('bucket = "next"', "must carry the date it was claimed"),
        ('bucket = "now"\nclaimed = 2026-09-06', "belongs in 'next', not 'now'"),
        ('bucket = "now"\nblocked_on = "a call"', "blocked_on belongs to a 'later' item"),
        ('bucket = "now"\nfiled = "2026-09-06"', "must be a bare TOML date"),
        ('bucket = "now"\nurgency = "high"', "unknown field(s) urgency"),
        ('bucket = "now"\n[refs]\nspecs = ["no-such-spec"]', "is not a spec in openspec/specs"),
        ('bucket = "now"\n[refs]\nchanges = ["no-such-change"]', "neither an active nor an archived change"),
        ('bucket = "now"\n[refs]\nfiles = ["src/snakestream/gone.py"]', "does not exist"),
        ('bucket = "now"\n[refs]\nowner = ["someone"]', "unknown ref kind(s) owner"),
    ],
)
def test_each_rule_rejects_the_item_that_breaks_it(tmp_path, frontmatter, expected) -> None:
    item = tmp_path / "sample.md"
    defaults = 'id = "sample"\ntitle = "Sample"\nrank = 1\nfiled = 2026-09-06\n'
    keep = "\n".join(line for line in defaults.splitlines() if line.split(" =")[0] not in frontmatter)
    item.write_text(f"+++\n{keep}\n{frontmatter}\n+++\nBody.\n")

    problems = roadmap_index.validate([roadmap_index.parse(item)], root=Path())

    assert any(expected in problem for problem in problems), f"expected {expected!r} in {problems}"


def test_an_id_that_disagrees_with_its_filename_is_a_problem(tmp_path) -> None:
    item = tmp_path / "on-disk.md"
    item.write_text('+++\nid = "in-frontmatter"\ntitle = "T"\nbucket = "now"\nrank = 1\nfiled = 2026-09-06\n+++\nBody.\n')

    problems = roadmap_index.validate([roadmap_index.parse(item)])

    assert any("does not match its filename" in problem for problem in problems)


def test_two_items_sharing_a_rank_in_one_bucket_is_a_problem(tmp_path) -> None:
    parsed = []
    for name in ("first", "second"):
        item = tmp_path / f"{name}.md"
        item.write_text(f'+++\nid = "{name}"\ntitle = "T"\nbucket = "now"\nrank = 1\nfiled = 2026-09-06\n+++\nBody.\n')
        parsed.append(roadmap_index.parse(item))

    problems = roadmap_index.validate(parsed)

    assert any("rank 1 is already taken" in problem for problem in problems)


def test_a_readme_without_the_markers_is_refused(tmp_path, items) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Roadmap\n\nNo markers here.\n")

    with pytest.raises(ValueError, match="index markers not found"):
        roadmap_index.readme_with_index(items, readme=readme)

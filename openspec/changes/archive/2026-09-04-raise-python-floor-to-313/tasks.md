## 1. Move the floor

- [x] 1.1 In `pyproject.toml`, set `requires-python = ">=3.13"`; verify `uv sync` resolves and `uv run python -c "import snakestream"` succeeds.
- [x] 1.2 In `pyproject.toml`, set `[tool.ruff] target-version = "py313"`; verify `uv run ruff check .` reports exactly 14 `UP043` findings and nothing else.
- [x] 1.3 In `.github/workflows/check.yml`, drop `"3.12"` from both matrices, leaving 3.13–3.14; verify by grep that no `3.12` remains and the `if: matrix.python-version == '3.14'` conditionals are untouched.

## 2. Take the UP043 fixes

- [x] 2.1 Run `uv run ruff check --select=UP043 --fix .` — scoped to the one rule, not a bare `--fix` (design: Risks). Verify the diff is exactly 14 single-line edits across `stream.py` (5), `collector.py` (5), `execution.py` (2) and `tests/test_find_first.py` (2), and that each removes only a trailing `, None`.
- [x] 2.2 Verify no annotation lost meaning: `uv run ty check src` passes and `uv run pytest tests/test_static_typing.py` still shows all four fixtures behaving as declared — including the two negative ones (`bad_stream_map.py`, `bad_to_map_container_without_merge.py`) continuing to **fail** `ty`. A wrong assumption about typeshed's defaults surfaces here (design decision 1).
- [x] 2.3 Verify `uv run ruff check .` is clean — zero findings, not merely no `UP043`.

## 3. Record the declines

- [x] 3.1 Confirm no code change is made for PEP 696 defaults on `Collector` or any other generic in the package (design decision 2). Verify `Collector[T, A, R]`'s parameter list is byte-identical to before this change; the decline is the deliverable.
- [x] 3.2 Confirm no code change is made for `TypeIs` and that `is_async_callable()`'s signature is untouched (design decision 3). Verify the `cast()` count in `src/` is unchanged before and after — this change neither adds nor removes one.

## 4. Update the specs

- [x] 4.1 Verify the `stream-iterator` delta carries all three scenarios of its requirement verbatim and changes only the written type plus the added explanatory sentence; confirm with `openspec validate raise-python-floor-to-313`. (Archive applies it to the main spec — do not hand-edit `openspec/specs/`.)
- [x] 4.2 Grep `openspec/specs/` for any other written `AsyncGenerator[..., None]` and verify `stream-iterator` was the only one; if another appears, add a delta for it rather than leaving the drift.

## 5. Correct the prose

- [x] 5.1 In `CLAUDE.md`, change "across Python 3.12–3.14" to "across Python 3.13–3.14"; verify no `3.12` remains in the file.
- [x] 5.2 Add a README Migration entry for the dropped interpreter. State plainly that this step has **no** silent break — unlike the 3.12 entry's alias-introspection change — so a reader upgrading across several versions can tell the two apart. Cite `openspec/changes/raise-python-floor-to-313`.
- [x] 5.3 Grep the repo for remaining `3.12` claims outside `openspec/changes/archive/`; verify every surviving hit is historical narrative or deliberately out of scope, and record which. The archived 3.12 change legitimately says 3.12 throughout and is not rewritten.
- [x] 5.4 Note in the change record that `.readthedocs.yml`'s `python: "3.13"` pin now sits exactly at the floor rather than above it, and is deliberately left for the 3.14 step (design: Non-Goals). No edit now.

## 6. Validate as CI does

- [x] 6.1 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src` and `uv run pytest --cov-fail-under=98`; verify all pass. Record the coverage figure before and after — it should be unchanged, since no branch is added or removed.
- [x] 6.2 Run `openspec validate raise-python-floor-to-313`; verify it reports valid.

## 1. Implementation

- [x] 1.1 Add `joining(delimiter: str = "", prefix: str = "", suffix: str = "")` to `collector.py`, returning an `async def` collector that concatenates pulled `str` elements with the delimiter and wraps the result in `prefix`/`suffix`.
- [x] 1.2 Verify a non-`str` element raises `TypeError` (no explicit `isinstance` check needed if the join logic naturally raises — confirm this holds, add an explicit check only if it doesn't).

## 2. Tests

- [x] 2.1 Add `tests/test_joining.py` covering: no-arg join, delimiter-only, delimiter+prefix+suffix, single-element (no delimiter applied), empty stream (with and without prefix/suffix), and `TypeError` on a non-`str` element.
- [x] 2.2 Run `uv run pytest tests/test_joining.py` and the full suite (`uv run pytest`) to confirm no regressions and coverage stays at/above the gate.

## 3. Docs

- [x] 3.1 Add a `Collectors` table section to `README.md` (new section, following the existing `Stream` table's format) with a row for `joining(delimiter, prefix, suffix)`.
- [x] 3.2 Move roadmap.md **Now** item #1 (`joining()`) to **Done**, following the existing Done-entry format (what/why/tests/link to this change).

## 4. Validation

- [x] 4.1 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 4.2 `uv run ty check src`

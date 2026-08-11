## 1. Implementation

- [x] 1.1 Simplify `Stream.of()` in `src/snakestream/stream.py` to `def of(*args: Any) -> Stream` with single-arg pass-through / multi-arg list-wrap, removing the dict/list `isinstance` branches and `**kwargs` handling.
- [x] 1.2 Special-case `str`/`bytes` as scalar in `_normalize()` in `src/snakestream/base_stream.py`, alongside the existing `dict` check.

## 2. Tests

- [x] 2.1 Remove the four kwargs-only tests from `tests/test_of.py` (`test_single_kw_arg`, `test_kw_and_regular_arg`, `test_multiple_kw`, `test_multiple_kw_mixed`).
- [x] 2.2 Add tests asserting `Stream.of("abc")` yields `["abc"]` and `Stream.of(b"ab")` yields `[b"ab"]`.
- [x] 2.3 Add a test asserting `Stream.of(a=1)` raises `TypeError`.
- [x] 2.4 Run `uv run pytest` and confirm all remaining/updated `test_of.py` cases pass, plus the full suite (checking nothing else relied on kwargs or char-spreading str/bytes).

## 3. Docs

- [x] 3.1 Update the `of()` row in README.md's API table (currently `of(*args, *kwargs)`) to reflect the new signature.
- [x] 3.2 Add two **BREAKING** entries to README.md's migration log per `CLAUDE.md`: kwargs removal, and str/bytes scalar normalization.
- [x] 3.3 Move the "Simplify `Stream.of()`" item from roadmap.md's **Now** table to **Done**, summarizing what shipped.

## 4. Verification

- [x] 4.1 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 4.2 `uv run ty check src`
- [x] 4.3 `uv run pytest --cov-fail-under=98`

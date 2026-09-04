## 1. Move the floor

- [x] 1.1 In `pyproject.toml`, set `requires-python = ">=3.12"`; verify `uv sync` resolves and `uv run python -c "import snakestream"` succeeds.
- [x] 1.2 In `pyproject.toml`, set `[tool.ruff] target-version = "py312"`; verify `uv run ruff check .` reports exactly the four `UP046` findings (`collector.py:77`, `sink.py:49`, `stream.py:103`, `stream_builder.py:9`) and nothing else.
- [x] 1.3 In `.github/workflows/check.yml`, drop `"3.11"` from both matrices, leaving 3.12–3.14; verify by grep that no `3.11` remains and the `if: matrix.python-version == '3.14'` conditionals are untouched.
  - Also dropped `3.11` from `.github/workflows/deliver.yml`'s matrix (same gap as the prior floor raise: unmentioned in this proposal's Impact, but left alone it would run `uv sync`/`pytest` on 3.11 and fail once `requires-python` is `>=3.12`). Consistent with the fix applied to that file in `openspec/changes/archive/2026-09-04-raise-python-floor-to-311`.

## 2. Convert type.py's aliases

- [x] 2.1 Convert each parameterized alias in `src/snakestream/type.py` to a PEP 695 `type` statement, declaring on each the exact parameters it uses (`type Predicate[T]`, `type Mapper[T, R]`, `type Accumulator[T, R]`, `type Finisher[A, R]`, …). Verify every alias's parameter list matches how call sites subscript it — they are used subscripted throughout, so an arity mistake surfaces as a `ty` error rather than silently.
  - Verified subscript arity/order at every call site via grep (`collector.py`, `collectors.py`, `comparator.py`, `stream.py`) before writing the aliases: `BiConsumer[R, T]` (not `[T, R]`) matches both its own `Callable[[R, T], ...]` body and every call site (`BiConsumer[A, T]`, `BiConsumer[R, T]`, `BiConsumer[R, R]`). `AsyncComparator`, `KeyExtractorComparator`, and `CloseHandler` are used bare everywhere (never subscripted) even though `AsyncComparator`'s body references `T` — kept `type AsyncComparator[T]` regardless, since the task asks for the parameters the *definition* uses, and bare usage of a generic alias remains valid.
- [x] 2.2 Unquote `FlatMapper`'s `"Stream[R]"` (design context 2: the `type` RHS is lazy, so the `TYPE_CHECKING`-only import of `Stream` is fine unquoted). Verify with `uv run python -c "import snakestream.type"` and `uv run ty check src`.
- [x] 2.3 Leave `StateMap` as a plain assignment or convert it, whichever reads better — it takes no parameters, so `type StateMap = dict[Any, Any]` is optional. Record the choice and the reason.
  - Kept as a plain assignment. It takes no parameters and a `type` statement adds nothing readability-wise for a non-generic alias; a comment now says so at the definition.
- [x] 2.4 Keep `T`, `R`, `A`, `Aiter`, `C` and `M` as `TypeVar` declarations, and keep the `TypeVar` import. Add a comment at that block stating why they are not scoped parameters (design decision 2: shared across modules, `C`/`M` carry bounds used at 3 and 5 sites, PEP 695 has no shared-typevar syntax). Verify the comment names the constraint rather than restating the code.
- [x] 2.5 Verify no alias lost its meaning: `uv run ty check src` passes, and `uv run python -c "from snakestream.type import Mapper; print(Mapper[int, str])"` still prints a subscripted alias.
  - `ty check src`: all checks passed. `Mapper[int, str]` prints `Mapper[int, str]`.

## 3. Convert the four generic classes

- [x] 3.1 `src/snakestream/stream.py`: `class Stream(Generic[T])` → `class Stream[T]`; drop `Generic` from the `typing` import if now unused. Verify `uv run ruff check .` no longer reports `UP046` for this file.
  - `Generic` dropped from the `typing` import; module-level `T` import from `type.py` also dropped — grep confirmed every bare `T` in the file lives inside the `Stream` class body (only `_normalize`/`_accept`/`_concat` sit outside it, and none use `T`), so the class's own scoped parameter is the only `T` needed.
- [x] 3.2 `src/snakestream/stream_builder.py`: same for `StreamBuilder`; note it imports `T` from `type.py` solely for this, so check whether that import is now unused and remove it if so.
  - `T` import removed; it had no other use in the file.
- [x] 3.3 `src/snakestream/sink.py`: `class Sink(ABC, Generic[T])` → `class Sink[T](ABC)`; verify the ABC base still comes through by running `uv run pytest tests/test_sink.py`.
  - `Generic` dropped from the `typing` import, but the `T` import from `type.py` was **kept**: `IntermediateSink`, `StatefulSink`, `TerminalSink`, `UnseededSink` and `GeneratorBridgeSink` all subscript `Sink[T]`/`TerminalSink[T]` using the module-level `T` and are not part of this conversion (they're not `UP046` findings — they subscript, they don't use `Generic` directly). `tests/test_sink.py`: 27 passed.
- [x] 3.4 `src/snakestream/collector.py`: `class Collector(Generic[T, A, R])` → `class Collector[T, A, R]`; verify parameter order is preserved, since `Collector[T, Any, R]` is written at many call sites and a reorder would type-check wrongly rather than fail loudly.
  - Order preserved (`[T, A, R]`, matching every `Collector[T, Any, R]`/`Collector[Any, C, C]`-shaped call site). `Generic` dropped from `typing`; `A`/`R` dropped from the `type.py` import (used only inside `Collector.__init__`), `T` kept (used by `CollectorSink(AsyncDispatch, TerminalSink[T])`, module-level).
- [x] 3.5 Verify `uv run ruff check .` is clean — zero findings, not merely no `UP046`.
  - `uv run ruff check .`: All checks passed. Also ran the full suite early as a sanity check: `uv run pytest` — 1000 passed.

## 4. Prove the conversion is faithful

- [x] 4.1 Run `uv run pytest tests/test_static_typing.py` and verify all four fixtures behave as declared — crucially that the two negative ones (`bad_stream_map.py`, `bad_to_map_container_without_merge.py`) still **fail** `ty` with their expected diagnostics. A silent widening to `Any` shows up here as a test that stopped failing (design: Risks).
  - 4 passed, including `test_element_type_mismatch_after_map_is_caught` and `test_to_map_with_a_container_and_no_merge_function_is_rejected` — the tests asserting the negative fixtures still produce their expected `ty` diagnostics. No widening.
- [x] 4.2 Run `uv run pytest tests/test_name_visibility.py` and verify the naming build-check still passes with the converted aliases.
  - 3 passed.
- [x] 4.3 Confirm `openspec/specs/generic-stream-typing/spec.md` needs no edit: re-read its requirements against the converted code and verify each is still literally true. Record the check; do not edit the spec (design decision 3).
  - Re-read all 8 requirements: every one is phrased as observable typing behavior (element-type inference, alias return-type contracts, `StreamBuilder[T].build()` → `Stream[T]`) with no mention of `Generic`/`TypeVar`/PEP 695. All still literally true post-conversion; not edited.

## 5. Correct the prose

- [x] 5.1 In `CLAUDE.md`, change "across Python 3.11–3.14" to "across Python 3.12–3.14"; verify no `3.11` remains in the file.
- [x] 5.2 Add a README Migration entry covering both breaks: the dropped interpreter (loud, at `pip` resolution) and the alias introspection change (silent — `get_origin`/`get_args` on a subscripted alias, with the measured before/after from `design.md` context 3, and the note that static typing is unaffected). Match the density of surrounding entries and cite `openspec/changes/raise-python-floor-to-312`.
  - Re-measured rather than trusted design.md's figures: `get_origin(Mapper[int, str])` → `Mapper` (was `collections.abc.Callable`), `get_args(...)` → `(int, str)` (was `([int], str | Awaitable[str])`), `type(Mapper)` → `typing.TypeAliasType`, RHS reachable via `.__value__`. Matches design context 3 exactly.
- [x] 5.3 Grep the repo for remaining `3.11` claims outside `openspec/changes/archive/`; verify every surviving hit is historical narrative or deliberately out of scope, and record which. Note that the archived 3.11 change legitimately says 3.11 throughout and is not rewritten.
  - `openspec/specs/install-smoke-test/spec.md`: still says 3.11–3.14 — expected, handled by archive's sync per the MODIFIED delta, not hand-edited during apply (same pattern as the prior floor raise).
  - `README.md:172` (behavior table) and the two Migration-log entries (line-shifted, now below the new one): historical/descriptive, correctly left as-is — the table row's "on Python 3.11+" remains literally true (every supported interpreter is now 3.12+, a subset of 3.11+), and Migration entries document past floors, not the current one.
  - `roadmap.md`'s `3.11x`/`3.21x` hits are benchmark multipliers, not Python versions — false positives from the grep, correctly ignored.
  - **Gap found and fixed (out of the proposal's stated Impact, surfaced and confirmed with the user):** `openspec/specs/stream-close-handling/spec.md:49` said "the supported floor is 3.11", which becomes a false claim once this change lands. Reworded to state the invariant (floor has been at or above 3.11 since it was raised there) instead of naming a specific current floor, so it won't go stale at the next raise either.
  - This change's own artifacts (`proposal.md`, `design.md`, `tasks.md`) and the archived 3.11 change legitimately say 3.11 throughout; not rewritten.

## 6. Validate as CI does

- [x] 6.1 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src` and `uv run pytest --cov-fail-under=98`; verify all pass. Record the coverage figure before and after.
  - All five pass: ruff check clean, ruff format clean (604 files), pytest 1000 passed, ty check src clean, cov-fail-under=98 gate passes.
  - Coverage before (stashed, pre-change): 98.66%. Coverage after: 98.66%. Unchanged, as expected — this change is a syntax conversion, no branches added or removed.
- [x] 6.2 Run `openspec validate raise-python-floor-to-312`; verify it reports valid.
  - `openspec validate raise-python-floor-to-312` reports: Change 'raise-python-floor-to-312' is valid

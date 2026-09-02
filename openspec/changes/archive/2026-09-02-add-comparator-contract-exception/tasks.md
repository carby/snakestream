## 1. The exception type

- [x] 1.1 Add `ComparatorContractException(StreamBuildException, TypeError)` to `src/snakestream/exception.py`, with a docstring stating why it mixes in `TypeError` (design.md Decision 3) and why its base is `StreamBuildException` rather than `StreamException` (Decision 2). Verify `uv run python -c "from snakestream.exception import ComparatorContractException as E; print([c.__name__ for c in E.__mro__])"` prints the linearization in design.md Decision 3.
- [x] 1.2 Retire the public `COMPARATOR_RESULT_TYPE_MESSAGE` the preceding commit added: the exception takes the offending value and renders the wording itself, so the constant becomes a module-private `_RESULT_TYPE_MESSAGE` (design.md Decision 5). This also disposes of its comment, which claimed seven check sites (six — it counted the deleted `check_comparator_result_type` definition) and opened "the one TypeError this library raises rather than defining". Verify `grep -rn "COMPARATOR_RESULT_TYPE_MESSAGE" src/ tests/` returns nothing.
- [x] 1.3 Keep the offending value in `args` and render in `__str__` rather than formatting in `__init__`, so the exception survives a pickle round trip (design.md Decision 5). Verify the round-trip and message tests in `tests/test_exception_hierarchy.py` pass.

## 2. The raise sites

- [x] 2.1 Replace `raise TypeError(...)` with `raise ComparatorContractException(...)` at the three sites in `src/snakestream/sort.py` (`_checked`, `_checked_segment_comparator`, `_merge`), leaving the guard, the message and the position untouched. Verify `grep -n "raise TypeError" src/snakestream/sort.py` returns nothing.
- [x] 2.2 Replace the same at the three sites in `src/snakestream/comparator.py` (`is_new_extremum`, `_comparator_segment_sign_sync`, `_comparator_segment_sign_async`). Verify `grep -n "raise TypeError" src/snakestream/comparator.py` returns nothing.
- [x] 2.3 Run `uv run pytest` and verify all 989 existing tests pass unchanged — in particular the eight `pytest.raises(TypeError)` assertions in `test_sorted.py`, `test_comparator_segments.py`, `test_nulls_ordering.py`, `test_min.py`, `test_max_by.py` and `test_min_by.py`, which are the compatibility evidence that the change is purely widening.
- [x] 2.4 Run `uv run ty check src` and verify it reports no new diagnostics; if narrowing changed around any raise site (design.md Risks), resolve it there rather than by re-introducing a cast.

## 3. Tests for the new behavior

- [x] 3.1 Add tests covering the `exception-hierarchy` delta's new scenarios: a bool comparator caught by `except StreamBuildException`, by `except StreamException`, propagating uncaught past `except ValueError`, and `issubclass` reporting `ComparatorContractException` under `StreamException`, `StreamBuildException` and `TypeError`. Verify they pass.
- [x] 3.2 Add the `comparator-contract` delta's two new scenarios: the rejection caught as a library exception while still satisfying `except TypeError`, and a comparator returning `str` rejected the same way with the returned type named in the message. Verify they pass.
- [x] 3.3 Add a test asserting the async-comparator segment rejection still raises `StreamBuildException` and is **not** a `ComparatorContractException`, so the two adjacent raises in `_checked_segment_comparator` stay distinguishable. Verify it passes.
- [x] 3.4 Run `uv run pytest --cov-fail-under=98` and verify the gate holds, with `exception.py`, `sort.py` and `comparator.py` at the coverage they had before this change.

## 4. Documentation

- [x] 4.1 Add a README Migration entry marked `(not breaking)`, following README.md:295's `StreamException` precedent: state that the comparator rejection is now `ComparatorContractException`, that `except TypeError` is unaffected, that `except StreamBuildException` and `except StreamException` now catch it, and that a caller matching on exact type (`type(e) is TypeError`) is the one shape that changes. Verify the entry names this change directory.
- [x] 4.2 Check whether `CLAUDE.md`'s architecture notes or README's collector/comparator tables mention the bare `TypeError` and update them if so. Verify with `grep -n "TypeError" README.md CLAUDE.md`.

## 5. Gates

- [x] 5.1 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`, `uv run pytest` and `uv run pytest --cov-fail-under=98`; verify all pass, matching what CI runs on the 3.14 leg.
- [x] 5.2 Run `openspec validate add-comparator-contract-exception --strict` and verify the change is still valid after any spec edits made during implementation.

+++
id = "min-by-max-by-reducing"
title = "Added `min_by()`, `max_by()` and `reducing()`"
filed = 2026-08-17
closed = 2026-08-17
outcome = "shipped"
+++

Added `min_by(comparator)`, `max_by(comparator)`, and `reducing(...)`
(`collector.py`) — collector wrappers around `Stream.min`/`max`/`reduce`'s
already-implemented logic, exposed as `collect()`-compatible collectors
rather than terminal-op methods, matching Java's `Collectors.minBy`/
`maxBy`/`reducing` (adapted to this project's existing snake_case naming
convention, e.g. `for_each`/`to_array`/`summing_int`, not literal Java
camelCase). `min_by`/`max_by` reuse `check_comparator_result_type`
(`sort.py`) and mirror `Stream._min_max`'s tie-break (first of equal
elements wins) and `None`-on-empty-stream behavior exactly. `reducing`
implements all three Java overload shapes — `reducing(binary_operator)`
(no identity, mirrors `Stream.reduce(accumulator)`),
`reducing(identity, binary_operator)` (mirrors
`Stream.reduce(identity, accumulator)`), and
`reducing(identity, mapper, binary_operator)` (maps each element before
folding, argument order matching Java's
`reducing(U identity, Function<T,U> mapper, BinaryOperator<U> op)`
exactly) — dispatched via `@overload` + a runtime `_UNSET` sentinel, the
same pattern `Stream.reduce` already uses. The loop bodies are
intentionally duplicated from `Stream._min_max`/`reduce` rather than
retrofitting those methods to accept an arbitrary `AsyncGenerator`, since
a collector's contract has no `Stream` instance in scope and the loops are
short and stable; `check_comparator_result_type` stays imported from
`sort.py` as the single source of truth for the one piece of real shared
logic. Discovered during implementation: the three `reducing` `@overload`
stub bodies pushed combined branch coverage below the repo's 98% gate
(each unreachable `def ...: ...` stub counts as a never-taken branch);
fixed with `# pragma: no cover` on each stub line, an already-supported
`exclude_lines` pattern in `pyproject.toml` — no config change needed.
Added `tests/test_min_by.py`, `tests/test_max_by.py`,
`tests/test_reducing.py`: extremum selection, empty-stream `None`,
tie-break, async comparator/mapper/operator awaiting, `TypeError` on a
bool-returning comparator, and all three `reducing` overloads including
empty-stream/single-element edge cases. Updated README's `Collectors`
table with three new rows. No breaking changes. See
`openspec/changes/archive/2026-08-17-add-collectors-minby-maxby-reducing`.

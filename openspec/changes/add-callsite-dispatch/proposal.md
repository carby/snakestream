> **STATUS: REJECTED (2026-08-18).** Measured at the task 3.2 gate and abandoned;
> the duplication described below is real but costs less to keep than to remove.
> See `benchmark-findings.md` and the roadmap's **Done** entry.

## Why

`callable_dispatch.py` documents its dispatch pattern as a 40-line comment
("Canonical shape for the 26 per-element call sites…") and then every call site
retypes that shape by hand. A documented pattern that must be hand-copied is a
missing abstraction: there are 24 per-element dispatch sites across
`stream.py`, `collector.py` and `sort.py`, each independently maintaining an
`is_async` flag, a `checked` flag, a `fn(...)` call, an `isawaitable()` safety
net and a `cast(...)` — and any future operation must copy it correctly a 25th
time from a comment rather than call something.

The pattern has already started deforming under its own weight. `_classify_step`
exists only because inlining the shape three times in `to_map` and twice in
`reducing` pushed those functions past the mccabe complexity gate; it returns a
`(result, is_async, checked)` tuple the caller must unpack and then separately
`await`, which is harder to read than the inline version it replaces.
`sort.py`'s `merge_sort` needed the same state shared across sibling `_merge`
calls and reached for a two-element list (`state = [is_async, checked]`) indexed
positionally as `state[0]`/`state[1]`.

## What Changes

- Add a `CallSite` class to `callable_dispatch.py`: a small object wrapping one
  user-supplied callable together with its `is_async`/`checked` classification
  state, exposing an `async __call__(*args)` that performs the classify-and-await
  step and returns the settled value.
- Convert all 24 per-element dispatch sites to construct a `CallSite` where they
  currently initialize an `is_async`/`checked` pair, and to `await` it where they
  currently inline the five-branch shape:
  - `stream.py` — `_FilterSink`, `_MapSink`, `_PeekSink`, `_collect_mutable`,
    `reduce`, `for_each`, `for_each_ordered`, `_min_max`, `_match`
  - `collector.py` — `summing_int`/`summing_long`/`summing_double`,
    `averaging_int`/`averaging_long`/`averaging_double`, `_extremum`,
    `reducing` (mapper and binary operator), `to_map` (key, value and merge
    functions), `grouping_by`, `partitioning_by`
  - `sort.py` — `merge_sort`/`_merge_sort`/`_merge`, whose `comparator, state`
    parameter pair collapses into a single `CallSite` threaded through the
    recursion
- Delete `_classify_step`, whose only reason to exist was the mccabe pressure
  that inlining creates; `to_map` and `reducing` become one `CallSite` per
  callable with no tuple unpacking.
- Replace the 40-line canonical-shape comment with the class itself plus a short
  docstring stating the one rule callers must still honor: construct the
  `CallSite` per composition, never per operation.
- Keep `is_async_callable` as `CallSite`'s classifier (still the single place
  that recognizes an `async def` function and an async-`__call__` object) and
  keep `_maybe_await` for the once-per-composition sites where specialization
  buys nothing (`collect()`'s `supplier`).
- No public API change, no behavior change, no breaking change.

## Capabilities

### New Capabilities

None. This change introduces no new observable behavior.

### Modified Capabilities

- `callable-dispatch`: one ADDED requirement — classification state SHALL be
  per callable, so an operation taking several user-supplied callables (`to_map`'s
  key/value/merge functions, `reducing`'s mapper and binary operator) classifies
  each independently and may mix sync and async freely among them.

Everything else in the spec is unchanged: uniform dispatch across all four
sync/async callable shapes, classification made at most once per composition and
confirmed against the first result, no leaking across compositions or parallel
branches, homogeneity of user-supplied callables, and unchanged operation
coverage. `CallSite` is a different implementation of exactly those requirements,
so the existing spec is this change's verification target rather than its
subject.

The one addition is worth stating normatively precisely because this refactor is
where violating it becomes easy: today per-callable independence is enforced by
the accident of each callable owning a separately-named pair of local flags
(`key_is_async`/`value_is_async`/`merge_is_async`), whereas after the change it
depends on constructing one `CallSite` per callable rather than reusing one — a
mistake that would silently break a `to_map` with, say, a sync `key_mapper` and
an async `value_mapper`.

## Impact

- `src/snakestream/callable_dispatch.py` — gains `CallSite`, loses
  `_classify_step` and the canonical-shape comment
- `src/snakestream/stream.py` — 9 dispatch sites rewritten; three sinks lose two
  `__init__` lines and a `cast(...)` each
- `src/snakestream/collector.py` — 14 dispatch sites rewritten
- `src/snakestream/sort.py` — the `state` list-box removed; `_merge_sort`/
  `_merge` signatures change from `(arr, comparator, state)` to `(arr, cmp)`
- `tests/test_callable_dispatch.py` — gains direct `CallSite` coverage; existing
  per-operation async-callable-object tests are the regression net and should
  need no changes
- Internal only. No public API, no dependency, and no CI configuration change.
  Performance must not regress against the 2.6x gain
  `optimize-callable-dispatch` measured.

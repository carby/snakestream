## Why

Roadmap item 1 (**Now**, unblocked since 2026-08-19). `collector.py` is the
last consumer group still written as monolithic generator-draining closures,
and the cost is not stylistic: it holds a **second, independent implementation
of `terminals.py`**. `_extremum` duplicates `_MinMaxSink` (the tie-keeping
comment is copy-pasted verbatim between them), `counting()` duplicates
`_CountSink`, `reducing()` duplicates `_ReduceSink`, `to_list` duplicates
`GeneratorBridgeSink`, and there are two separate `_UNSET` sentinels
(`collector.py:25`, `terminals.py:23`). Giving the collectors Java's
`Collector<T,A,R>` shape — supplier / accumulator / combiner / finisher —
lets one `TerminalSink` adapter drive all of them, which deletes that second
implementation. That, not the interface shape, is the case for doing it;
Java parity is the bonus.

Now, because the terminal-sink conversion this was waiting on has landed and
`terminals.py` already exposes exactly the template a `Collector` adapts onto
(`begin`≡supplier, `accept`≡accumulator, `end`/`result()`≡finisher), and
because roadmap item 2 (`mapping`, `collectingAndThen`, `summarizing*`,
`to_collection`) is downstream-collector work that would otherwise be built
twice.

## What Changes

- **Add a public `Collector` class** — `Collector(supplier, accumulator,
  combiner=None, finisher=None)`, mirroring Java's `Collector<T,A,R>`. The
  accumulator is a `BiConsumer`-style `(container, element) -> None`, mutating
  its container, matching the `collect(supplier, accumulator, combiner)` form
  that already ships. Every part may be sync or async and is dispatched with
  the same classification every other user callable in the library gets.
- **Add a `_CollectorSink`** — one `TerminalSink` that adapts any `Collector`:
  `_create_container()` calls the supplier, `accept()` calls the accumulator,
  `_finish()` calls the finisher. Every collector in the library then runs
  through this one drive path instead of its own `async for` loop.
- **Rewrite every `collector.py` factory as a `Collector`.** `to_list`,
  `joining`, `counting`, `summing_int`/`long`/`double`,
  `averaging_int`/`long`/`double`, `min_by`, `max_by`, `reducing` (all three
  overloads), `to_map`, `to_set`, `grouping_by`, `partitioning_by`. Their
  names, arities, results and error behavior are unchanged; what they *return*
  changes from an `async def` closure to a `Collector`. `_extremum`,
  `_generator_of`, and the per-factory draining loops are deleted, as is
  `collector.py`'s `_UNSET`.
- **`to_list` stays a bare name, not a factory.** It becomes a module-level
  `Collector` instance, so `collect(to_list)`, `to_array()`'s implementation
  and every README example keep working verbatim. A `Collector` holds only its
  four callables, so one shared instance is safe to reuse across streams.
- **BREAKING: `collect(collector)` accepts a `Collector`, not any callable.**
  A plain callable other than `to_generator` raises `StreamBuildException`
  with a message naming `Collector`. `to_generator` is the one exception —
  it is lazy and streaming, so it can never be expressed as
  supplier/accumulator/finisher; it keeps its current `(composition) ->
  AsyncGenerator` shape and `collect()` recognizes it explicitly. The 3-arg
  `collect(supplier, accumulator, combiner)` form is untouched.
- **BREAKING: `grouping_by`/`partitioning_by`'s `downstream` must be a
  `Collector`.** Passing one of this library's collector factories —
  `grouping_by(len, joining(", "))` — is unaffected, since those now return
  `Collector`s; passing a hand-written closure is not supported. Groups
  accumulate into one downstream container *per key as elements arrive*,
  rather than buffering `list`s and replaying each through a fresh generator
  at the end. This is what makes per-key results combinable once real
  partitioned execution exists.
- **`combiner` is accepted, stored, and never invoked**, exactly as
  `Stream.collect(supplier, accumulator, combiner)` and `reduce`'s combiner
  already are — there are no independent partitions to merge until real
  parallelism lands (see the **Later** roadmap bucket). `ParallelStream`
  accumulates serially into one container.
- **`type.py` gains the new callable aliases** (`Finisher`, and the
  accumulation-type `TypeVar`), replacing the inline
  `Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, Any]]` annotations
  at `collector.py:348` and `:359` and the ~20 similar inline return
  annotations across the module.
- **README**: the Collectors table's "Collector" column becomes a real type;
  `collect(collector: Callable)`'s row is rewritten; the two breaking changes
  are added to the migration log.

## Capabilities

### New Capabilities
- `collector-protocol`: the `Collector(supplier, accumulator, combiner,
  finisher)` shape itself — what each part is, that any part may be sync or
  async, that `combiner` is accepted-but-unused, that one instance is
  reusable across streams and across compositions, that `collect()` accepts a
  `Collector` and rejects a plain callable, and that `to_generator` is the
  documented exception to that rule.

### Modified Capabilities
- `terminal-sinks`: the requirement "Operations that need a generator keep
  using the bridge" states that *collectors SHALL be plain callables taking a
  composed `AsyncGenerator`* and that `collect(collector)` obtains its input
  through the generator bridge. Both cease to be true: collectors are
  `Collector`s driven through a `TerminalSink`, and only `to_generator`,
  `iterator()`, `concat()` and the mode handoff still use the bridge.
- `collector-grouping-by`: `downstream` is a `Collector` rather than "any
  existing `collector.py` collector factory's returned closure", and each
  group is accumulated into its own downstream container as elements arrive.
- `collector-partitioning-by`: same `downstream` change, with both partitions'
  containers created up front so an empty partition still gets a finished
  downstream result.
- `collector-counting-summing-averaging`: the spec pins the returned collector
  as "an `async def` callable accepting an `AsyncGenerator[Any, None]`"; it
  becomes a `Collector`. Results are unchanged.
- `collector-joining`: same wording change — "an `async def` callable
  accepting an `AsyncGenerator[str, None]`" becomes a `Collector`.
- `collector-min-max`: same wording change, plus the tie-keeping and
  comparator-result-type rules now hold via the shared step used by
  `_MinMaxSink` rather than `_extremum`'s copy.

`collector-to-map`, `collector-to-set` and `collector-reducing` are *not*
listed: their requirements never pinned the returned object's type, and their
observable behavior does not change.

## Impact

- `src/snakestream/collector.py` — the whole module is rewritten. Expect it to
  shrink substantially: fourteen draining loops collapse to declarations over
  one adapter.
- `src/snakestream/sink.py` — `_UNSET` moves here from `terminals.py` (both
  `collector.py` and `terminals.py` now need it, and `collector.py` must not
  import `terminals.py`), plus a mutable value box for scalar accumulations
  alongside the existing `Counter`.
- `src/snakestream/terminals.py` — import-level only: `_UNSET` is re-homed.
  No sink is changed, added or deleted here. `Stream.count()`, `min()`,
  `max()` and `reduce()` keep their existing zero-extra-call per-element path;
  this change deliberately does **not** re-express them on top of collectors.
- `src/snakestream/stream.py` — `collect()`'s single-arg branch drives
  `_CollectorSink` instead of calling the argument, and rejects a non-
  `Collector` callable. `to_array()` is unaffected.
- `src/snakestream/type.py` — new aliases.
- `tests/` — no existing test passes a hand-written callable to `collect()` or
  as a `downstream`, so the two breaking changes cost no test rewrites; the
  457 existing tests are the regression gate. New tests are needed for the
  `Collector` class, for a user-defined `Collector` (sync and async parts),
  for the rejection of a plain callable, and for `to_generator` still working.
- `README.md` — Collectors table, `collect()` row, migration log.
- **Non-goal**: the four missing Java 8 `Collectors` (roadmap item 2) are not
  added here; this change is what makes them cheap.

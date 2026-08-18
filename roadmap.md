# Roadmap

Now/Next/Later view of open code-quality and test-rigor items, generated from
the review-pass notes below. Completed items from that review remain in
**Done** for history.

## Now

Actively being picked up. Mostly low-risk and self-contained, but may
include a public-API item once there's a specific, near-term plan to do
the design work.

Ordered by dependency — items with no blockers first, items that depend on
an earlier item or on a Next-bucket decision last.

| # | Item | Why this position |
|---|---|---|

`Stream.reduce(identity, accumulator, combiner)` (3-arg, with a combiner for
parallel merging) has moved to **Later** below — see the resolved
`.parallel()` entry.

## Next

Real design/implementation work, but contained — mostly additive or scoped to
one area.

| Item | Why next |
|---|---|
| **Redesign pipeline execution from nested async-generator delegation to a push-based (Sink-chain) model** — every intermediate op in `stream.py` (`filter`, `map`, `flat_map`, `sorted`, `peek`, `_DistinctOp`, `_LimitOp`, `_SkipOp`) is implemented as `async def fn(iterable): async for i in iterable: yield ...`, so pulling one element through a chain of *k* ops recurses *k* deep at `__anext__()`/`async for` delegation time — independent of and not fixed by the `_sequential()` build-time rewrite (see Done). A long enough `.map()` chain still hits `RecursionError` on consumption. | Discovered while implementing the `_sequential()` rewrite (see `rewrite-sequential-iterative` in Done), which fixed only the build-time half of that item's stated risk. Needs a design decision first: replacing generator-delegation with a single driving loop that threads each item through all ops via a plain `for op in ops:` loop (à la Java Stream's `Sink` chain) touches every op in `stream.py` plus `parallel_stream.py`'s per-branch consumption — highest blast radius alongside the mutable-builder decision above. |
| **Redesign `collector.py`'s collectors around a `Collector(supplier, accumulator, combiner, finisher)` shape**, matching Java's `Collector<T,A,R>` interface, instead of today's single monolithic `async def _collect(composition): async for n in composition: ...` closures. | Not actually blocked on real parallelism — `collect(supplier, accumulator, combiner)` already shipped with `combiner` accepted-but-unused for Java signature parity, ahead of any real partitioned execution (see Done), and this could follow the same precedent: build the `Collector` shape now, have `ParallelStream.collect()` ignore `combiner` and fall back to today's serial accumulation, and only wire it up once real per-branch execution exists. Real design cost instead: `grouping_by`/`partitioning_by`'s `downstream` parameter would need to become a `Collector` itself (so its per-key containers, not just final results, can be combined later), which is a breaking signature change to two collectors that just shipped — scope that decision before starting. |

## Later

Bigger, structural — needs explicit buy-in before starting since it changes a
core semantic.

| Item | Why later |
|---|---|
| **Implement real (multiprocess) parallelism for `.parallel()` / `ParallelStream` / `PROCESSES`** — today it's just `asyncio` tasks racing over a shared generator (I/O-bound only, GIL-bound, no multiprocessing). Decided to keep the `.parallel()`/`PROCESSES` naming as-is (see README) rather than rename to the more accurate `.concurrent()`/`CONCURRENCY`, specifically so that *if* real parallelism is ever implemented under the same names, it's not a second breaking rename. | No concrete use case for true CPU parallelism has come up yet, and the path there is blocked on a real problem, not just unscoped effort: a `ProcessPoolExecutor`-backed implementation needs to serialize the mapper/predicate/comparator/accumulator/combiner across the process boundary, and stdlib `pickle` can't handle lambdas or local closures (the idiomatic way to call every op in this library), can't pickle generators/async generators at all (so the source itself can never be shipped whole), and even picklable *sync* callables don't solve it since async user callables would need each worker to bootstrap its own event loop rather than just running a function. Revisit only once there's both a concrete need and an answer for lambdas/closures across the process boundary (`cloudpickle`/`dill`, or a restricted sync-only picklable-callable mode) and for running async user callables inside a worker process. |
| **`BaseStream.spliterator()`** — Java's parallel-decomposition iterator, used by `parallelStream()` to split a source into chunks shared threads can each work over. | Depends on the item above: Java's `Spliterator` assumes shared-memory thread decomposition, which only becomes meaningful once real (multiprocess) partitioned execution is decided — until then there's nothing for it to expose, and it may end up intentionally-skipped rather than implemented. Moved down from **Now**, where it was flagged as decision-blocked rather than ready to build. |
| **Wire up `reduce(identity, accumulator, combiner)` and `collect(supplier, accumulator, combiner)`'s `combiner`** — both accept a `combiner` for Java signature parity but never invoke it, since `stream.py` always folds over one composed stream, sequential or parallel, with no independent partitions to merge. | Same blocker as the item above: a real combine step only makes sense once real partitioned (multiprocess) execution exists, which is now explicitly parked until there's both concrete demand and a solution for the pickling/async-worker problem. See `openspec/changes/add-collect-supplier-accumulator-combiner`. |
| **Java 9 `Stream` additions** — `takeWhile(predicate)`, `dropWhile(predicate)`, `Stream.ofNullable(t)`, and the 3-arg `iterate(seed, hasNext, next)` overload (distinct from the already-implemented 2-arg `iterate(seed, next)`). | README states the project's intent explicitly: "once we reach some sort of feature parity with Java 8 then maybe we move on to implement the improvements in Java 9." The **Now**/**Next** buckets are still closing out Java 8 parity gaps (`unordered()`, the `Collectors` framework, etc.), so pulling Java 9 work forward would jump the stated sequencing rather than reflecting lower value — revisit once Java 8 parity is substantially done. |

## Done

- Decided and implemented the mutable-builder vs. immutable-pipeline
  question (the former top **Next**-bucket item, previously "Decide
  mutable-builder vs. immutable-pipeline semantics"). Explored three
  positions during a design session: (A) keep mutate-and-return-self and
  just document the aliasing risk; (B) copy-on-write with the old
  reference left silently usable (superficially "forkable," but still a
  footgun since the underlying `self._stream` is single-pass, so both
  forks would race it exactly like `ParallelStream` branches do); (C)
  Java-exact — new instance plus invalidating the old reference on reuse.
  Landed on a scoped version of (C): every intermediate op (`map`,
  `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) and
  both mode switches (`sequential()`, `parallel()`) now return a **new**
  `Stream`/`ParallelStream` instance via a new `BaseStream._derive()`
  helper (`base_stream.py`) instead of mutating and returning `self`;
  using an already-superseded old reference for any further
  pipeline-building or terminal call now raises a new
  `IllegalStateException` (`exception.py`), checked via a
  `self._consumed` flag set only by the ops that build a new instance.
  Deliberately did **not** go full Java-exact: terminal ops
  (`collect`, `reduce`, `for_each`, etc.) check `self._consumed` but never
  set it, so repeating a terminal op on a reference that was never used to
  build a further instance keeps today's exact behavior (an exhausted
  source yields an empty result rather than raising) — reversing that
  would have undone the already-shipped, tested `fix-stream-rerun-state`
  contract that `pipeline-composition` documents, which was judged a
  separate, already-settled decision this change shouldn't revisit.
  `on_close()`/`close()` were kept completely exempt from the new check,
  matching how Java itself tracks close handlers at the pipeline's source
  stage rather than per operation, independent of any per-op immutability
  question. Discovered during implementation: `BaseStream.__init__`'s
  `self._close_handlers = close_handlers or []` treated an *empty* list as
  falsy and silently created a new list instead of keeping the passed-in
  reference — invisible before since intermediate ops never re-invoked the
  constructor, but every op does now via `_derive()`, breaking
  close-handler continuity across the very first op called before any
  `on_close()`. Fixed to `[] if close_handlers is None else close_handlers`.
  Added `tests/test_pipeline_immutability.py`: new-instance-per-op checks
  and invalidation-raises checks for all 8 intermediate ops, invalidation
  checks across all terminal ops and both mode switches, derived-instance
  usability, the unextended-reference non-regression case, and the
  `on_close()`/`close()` exemption. Added a new `pipeline-immutability`
  spec. Updated README's migration log (**BREAKING**). See
  `openspec/changes/make-stream-ops-immutable`.
- Implemented `Stream.find_first()` (`stream.py`), matching Java's
  `Stream.findFirst()`. The previous body was a dead
  docstring-commented-out stub — a string literal, never executed — with a
  comment claiming it was blocked on "ordered parallel stream." That
  blocker didn't actually apply to `Stream`: `Stream._compose()` is already
  sequential, so `find_first()` there is identical in body to `find_any()`.
  The real gap was narrower and `ParallelStream`-specific:
  `ParallelStream._compose()` races `PROCESSES` branches via
  `asyncio.wait(..., FIRST_COMPLETED)`, so first-*arrival* isn't
  first-*encounter-order*. Fixed by adding a `ParallelStream.find_first()`
  override that checks `self.is_ordered()`: when ordered (the default),
  pulls via `self._sequential(self._chain[:], self._stream)` — the same
  building block `for_each_ordered()` uses — for a strictly ordered,
  single-flight pull through the chain, guaranteeing the true first element
  in encounter order at the cost of `.parallel()`'s concurrency for this
  one terminal call (the same trade-off Java's own `forEachOrdered()`/
  ordered `findFirst()` make); when the stream has been marked
  `unordered()`, delegates to `find_any()`'s existing racing behavior,
  matching Java's documented relaxation of `findFirst()`'s encounter-order
  guarantee for unordered streams. This is the first consumer of the
  `is_ordered()`/`unordered()` flag added by `add-stream-unordered`. Added
  `tests/test_find_first.py`: non-empty/empty `Stream`,
  first-element-only pulled, and — mirroring `test_for_each_ordered.py`'s
  jumbled-source-with-positional-delay pattern — ordered-`ParallelStream`
  coverage proving `find_first()` returns the true first element rather
  than the first to arrive, plus unordered-`ParallelStream` coverage
  showing it races without waiting for a full ordered pull. Updated
  README's parity table (`find_first()` row, previously "Not implemented
  yet"). No breaking changes. See
  `openspec/changes/add-stream-find-first`.
- Fixed three resource/lifecycle defects found in review: (a) `flat_map()`
  (`stream.py`) leaked the current inner stream's async generator when the
  outer chain short-circuited (e.g. a downstream `.limit()`) — each outer
  element's fresh `flat_mapper(i).collect(to_generator)` generator was only
  ever exhausted, never explicitly `.aclose()`'d, so an early `GeneratorExit`
  on the outer chain abandoned whatever inner generator was mid-iteration.
  Fixed by wrapping that inner generator in `contextlib.aclosing()`
  (`stream.py`). Discovered during implementation: `aclosing()` alone wasn't
  sufficient — `collect(to_generator)` returns a second-layer wrapper
  generator (`collector.py`'s `to_generator()`) whose `async for n in
  composition: yield n` body didn't propagate `.aclose()` to `composition`
  either, confirmed with a minimal repro showing a plain `async for` never
  auto-closes what it iterates. Fixed `to_generator()` to also wrap
  `composition` in `aclosing()`, guarded by `hasattr(composition, "aclose")`
  since `to_generator()` also accepts plain `AsyncIterable`/`AsyncIterator`
  objects without an `aclose` method (e.g. a custom `__anext__`-only
  iterator, already covered by `tests/test_of.py::test_input_async_iterator`).
  This closes the gap only as deep as `flat_map()`'s stated repro case (a
  single-level inner stream); N-layers-deep propagation across every op in
  `stream.py` remains out of scope, tracked under the **Next**-bucket
  Sink-chain redesign item. (b) `BaseStream.close()` (`base_stream.py`)
  iterated `_close_handlers` with a plain `for` loop and no `try`/`except`,
  so a raising handler stopped every handler after it from running, unlike
  Java's try-with-resources convention of running every closer regardless.
  Fixed by calling every handler inside a per-handler `try`/`except
  Exception`, collecting failures, then raising the first captured exception
  once every handler has run (not an `ExceptionGroup`, since this project's
  CI matrix still targets Python 3.10). (c) `StreamBuilder.build()`
  (`stream_builder.py`) passed `self._elements` into `Stream(...)` by
  reference rather than snapshotting it, so `add()`/`accept()` calls made
  *after* `build()` leaked into the already-built stream. Fixed by
  snapshotting via `list(self._elements)`. Added regression tests in
  `tests/test_close.py`, `tests/test_flat_map.py`, and a new
  `tests/test_stream_builder.py`. Added a new `stream-builder` spec
  capturing `StreamBuilder`'s previously-undocumented `add()`/`accept()`/
  `build()` contract, and extended `stream-close-handling` and
  `pipeline-composition` for the `close()`/`flat_map()` fixes. Updated
  README's migration log: `StreamBuilder.build()`'s snapshot behavior is
  tracked as **BREAKING** per `CLAUDE.md`'s convention (relying on
  post-build mutation leaking into a built stream was never a documented
  feature). See `openspec/changes/fix-resource-lifecycle-defects`.
- Fixed three `type.py` callable-alias defects found in review: (a)
  `Mapper = Callable[[T], R | None]` now includes `Awaitable[R | None]`,
  matching `Predicate`/`Comparator`'s existing sync-or-async pattern and
  `map()`'s actual `_maybe_await`-based dispatch, which already supported
  async mappers without the type declaring it; (b) `Consumer` changed from
  `Callable[[T], T]` (wrong return type — a consumer's return value is
  discarded, not a `T`) to `Callable[[T], None | Awaitable[None]]`, and
  `for_each()`/`for_each_ordered()` (`stream.py`), which previously inlined
  their own `Callable[[T], Any]` instead of using the alias, now use
  `Consumer[T]`; (c) deleted `Filterer = Callable[[T], T]`, dead code never
  referenced anywhere in `src/` (`filter()` uses `Predicate`). Both alias
  widenings are additive to their unions, so no previously-valid sync usage
  is affected. Typing-only change, no runtime behavior differs. See
  `openspec/changes/fix-type-py-callable-alias-defects`.
- Added `groupingBy(classifier, [downstream])` / `partitioningBy(predicate,
  [downstream])`, implemented as `grouping_by`/`partitioning_by`
  (`collector.py`) — `collector.py`'s equivalent of `Collectors.groupingBy`/
  `partitioningBy`, closing out the roadmap's `Collectors`-parity effort.
  Both bucket elements first (`grouping_by` via a `classifier` mapper into a
  `dict[R, list[T]]`; `partitioning_by` via a `predicate` into a fixed
  `{True: [...], False: [...]}`, always populating both keys even when one
  partition is empty, matching Java's `Collectors.partitioningBy` exactly)
  then re-drives each bucket's elements through an optional `downstream`
  collector (default `to_list`) via a small `_generator_of(items)` helper
  that re-wraps the buffered list as a fresh `AsyncGenerator`, since
  downstream collectors are written to consume a composition, not a plain
  list — enabling `grouping_by(classifier, counting())`-style composition
  immediately, without downstream collectors needing to know they're being
  reused this way. `grouping_by`'s `classifier` and `partitioning_by`'s
  `predicate` reuse the same sync/async dispatch (`_maybe_await`) as every
  other collector. Added `tests/test_grouping_by.py`,
  `tests/test_partitioning_by.py`. Updated README's `Collectors` table with
  two new rows. No breaking changes. See
  `openspec/changes/archive/2026-08-18-add-collectors-groupingby-partitioningby`.
- Added `toMap(keyMapper, valueMapper, [mergeFunction])` / `toSet()`,
  implemented as `to_map`/`to_set` (`collector.py`) — structural collectors
  materializing into a `dict`/`set` instead of `to_list`'s `list`, matching
  `Collectors.toMap`/`Collectors.toSet`. `to_map` maps each element to a
  key/value pair via `key_mapper`/`value_mapper` (sync or async, dispatched
  through `_maybe_await`); a duplicate key raises `ValueError` unless a
  `merge_function` is given, in which case the collision resolves via
  `merge_function(existing, new)`, matching Java's
  `toMap(keyMapper, valueMapper, mergeFunction)` overload. `to_set()` takes
  no arguments and simply collects into a `set`, deduplicating via
  element `__hash__`/`__eq__` same as Java's `HashSet`-backed collector.
  Added `tests/test_to_map.py`, `tests/test_to_set.py`. Updated README's
  `Collectors` table with two new rows. No breaking changes. See
  `openspec/changes/archive/2026-08-18-add-collectors-tomap-toset`.
- Added `min_by(comparator)`, `max_by(comparator)`, and `reducing(...)`
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
- Added `counting()`, `summing_int`/`summing_long`/`summing_double`, and
  `averaging_int`/`averaging_long`/`averaging_double` (`collector.py`) —
  numeric reducing collectors, `collector.py`'s equivalent of the matching
  `Collectors` statics, following the same factory-returns-closure shape
  `joining()` established. `counting()` returns the `int` element count;
  `summing_int`/`summing_long`/`summing_double` map each element then sum
  the results (`int` for the first two, `float` for the last);
  `averaging_int`/`averaging_long`/`averaging_double` map each element and
  return the arithmetic mean as a `float` (`0.0` for an empty stream).
  Java's `Collectors` distinguishes `summingInt`/`summingLong`/
  `summingDouble` and the `averaging*` trio by primitive type — a
  distinction Python's numeric tower doesn't have — so each pair/trio is
  implemented identically apart from `summing_double`'s explicit `float()`
  coercion; kept as separate, Java-parity-named functions rather than
  collapsing to `summing(mapper)`/`averaging(mapper)`, since these are
  distinct Java method names (not one overloaded method, unlike `joining()`'s
  three arg-count variants). Added a new `NumberMapper` type alias to
  `type.py`. Mapper dispatch reuses the existing `_maybe_await` helper, so
  sync and async mappers both work. Added `tests/test_counting.py`,
  `tests/test_summing.py`, `tests/test_averaging.py`: non-empty/empty
  streams and sync/async mappers for each function, plus a `float`-type
  assertion for `summing_double`. Updated README's `Collectors` table with
  seven new rows. No breaking changes. See
  `openspec/changes/add-collectors-counting-summing-averaging`.
- Added `joining()` / `joining(delimiter)` / `joining(delimiter, prefix,
  suffix)` (`collector.py`) — a string-concatenation collector for use with
  `Stream.collect()`, `collector.py`'s equivalent of `Collectors.joining`
  and the first entry in the `Collectors`-parity effort tracked by this
  roadmap. Implemented as a single `joining(delimiter: str = "", prefix:
  str = "", suffix: str = "")` factory function, collapsing Java's three
  overloads into default arguments rather than `@overload`s, since the
  underlying behavior doesn't actually branch by argument count (contrast
  with `collect()`'s two genuinely different code paths, which do use
  `@overload`). It returns a plain `async def` closure over the composed
  `AsyncGenerator[str, None]`, matching `collector.py`'s existing
  plain-function collector shape (`to_list`/`to_generator`) rather than a
  callable class — no per-composition state is needed since
  prefix/delimiter/suffix are fixed at factory-call time. The join uses
  `delimiter.join(parts)`, so a non-`str` element naturally raises
  `TypeError` (matching Java's `Collectors.joining()`, defined only on
  `Stream<CharSequence>`) with no explicit `isinstance` check needed; an
  empty stream returns `prefix + suffix`, matching Java's Javadoc exactly.
  Added a new `Collectors` table section to README (none existed yet) to
  give this and future `Collectors`-family additions a place to be
  tracked. Added `tests/test_joining.py`: no-arg join, delimiter-only,
  delimiter+prefix+suffix, single-element (no delimiter applied), empty
  stream with and without prefix/suffix, and the `TypeError` regression for
  a non-`str` element. No breaking changes. See
  `openspec/changes/add-collector-joining`.
- Added `Stream.to_array()` (`stream.py`) — a terminal operation returning a
  `list` of every element pulled through the composed chain, functionally
  identical to `collect(to_list)`. Java's `toArray()`/`toArray(generator)`
  exist because arrays are a distinct, reified type from `List` and Java has
  no runtime generic-array construction; neither motivation applies to
  Python, where `list` is already the general-purpose ordered collection, so
  only the no-arg form was added — implemented as `to_array()` (snake_case),
  matching every other Java-name adaptation already in the class
  (`for_each`, `find_any`, `flat_map`), not the literal Java casing. The
  `toArray(generator)` overload was decided against and is documented in
  README as intentionally skipped rather than tracked as future work. Added
  `tests/test_to_array.py`: non-empty and empty streams, equivalence with
  `collect(to_list)`, `ParallelStream` coverage, and a `TypeError` regression
  for calling it with an argument. Updated README's parity table and
  removed the item from its "Left to do" list. No breaking changes. See
  `openspec/changes/add-stream-toarray`.
- Added `Stream.collect(supplier, accumulator, combiner)` (`stream.py`) —
  Java's 3-arg mutable-reduction overload of `collect()`, alongside the
  existing single-arg `collect(collector)` form. Implemented as an
  `@overload` pair dispatching on arg count, mirroring the precedent already
  set by `reduce()`'s identity/no-identity overloads: `supplier` is called
  once with no arguments to produce a fresh mutable container, `accumulator`
  is called once per pulled element as `accumulator(container, element)`,
  and both may be sync or async, dispatched via the existing `_maybe_await`
  helper. `combiner` is accepted for signature parity with Java but is
  never invoked — `collect()`, like the already-shipped `reduce()`, always
  folds over a single composed `AsyncGenerator` (sequential or parallel)
  with no independently-accumulated partitions to merge, so wiring up a real
  combine step is tracked separately in **Later** below, alongside the
  `.parallel()`/`PROCESSES` semantics decision it's blocked on. Added new
  `Supplier`/`BiConsumer` type aliases to `type.py`. Added 5 new tests in
  `tests/test_collect.py`: sync and async supplier/accumulator, an empty
  stream, and `combiner`-never-called coverage for both sequential `Stream`
  and `ParallelStream`. Updated README's parity table. No breaking changes.
  See `openspec/changes/archive/2026-08-17-add-collect-supplier-accumulator-combiner`.
- Added `Stream.for_each_ordered(consumer)` (`stream.py`) — an ordered variant
  of `for_each()`, invoking `consumer` in the stream's encounter order even
  when called on a `ParallelStream` instance, matching Java's
  `Stream.forEachOrdered()`. `for_each()` drives consumption via
  `self._compose()`, which `ParallelStream` overrides to fan the chain out
  across racing branches with no order guarantee; `for_each_ordered()`
  instead drives consumption via `self._sequential(self._chain[:],
  self._stream)` directly — the same building block `Stream._compose()`
  already uses — so it gets a strictly ordered, single-flight pull through
  the chain regardless of which subclass `self` is. This intentionally
  forfeits `.parallel()`'s concurrency for that one terminal call, the same
  trade-off Java's own `forEachOrdered()` makes on a parallel stream. The
  existing `BaseStream._ordered`/`unordered()` flag (see below) is not
  consumed here — every snakestream source has a real underlying order, and
  Java's own `forEachOrdered()` Javadoc ties the "if the stream has one"
  caveat to streams with no defined encounter order to begin with, which
  `unordered()` doesn't currently model. `for_each()`'s existing behavior is
  unchanged. Added `tests/test_for_each_ordered.py`: ordered/async-consumer
  coverage on sequential `Stream`, plus a same-chain-and-timing pair of
  parallel tests using a jumbled source and a positional (not value-based)
  per-element delay in a `.map()` step — one showing plain `for_each()` on a
  `ParallelStream` can come out scrambled under that reordering pressure, the
  other showing `for_each_ordered()` on the identical chain stays in source
  order. See `openspec/changes/add-stream-foreach-ordered`.
- Removed duplicate `_close_handlers` initialization. `BaseStream.__init__`
  (`base_stream.py`) always set `self._close_handlers = []`, but both
  `Stream.__init__` (`stream.py`) and `ParallelStream.__init__`
  (`parallel_stream.py`) immediately overwrote it with
  `close_handlers or []` right after `super().__init__(source)`, making the
  base assignment dead code on every instantiation. Fixed by giving
  `BaseStream.__init__` a `close_handlers` parameter and having it perform
  `self._close_handlers = close_handlers or []` directly; `Stream`/
  `ParallelStream` now just forward their own `close_handlers` argument via
  `super().__init__(source, close_handlers)` instead of reassigning the
  field themselves. No change to `on_close()`/`close()` or any observable
  behavior. Added a new `stream-close-handling` spec capturing the
  previously-undocumented `on_close()`/`close()`/construction/mode-switch
  contract, and new tests in `tests/test_close.py` covering scenarios not
  already exercised: registration order preserved across multiple
  `on_close()` calls, `close()` as a no-op with zero handlers registered,
  `Stream(source, [handler])` construction invoking the handler, and close
  handlers surviving a `.sequential()` switch (a `.parallel()` switch was
  already covered). See
  `openspec/changes/remove-duplicate-close-handlers-init`.
- Rewrote `BaseStream._sequential()` (`base_stream.py`) from recursion +
  `list.pop(0)` to an iterative loop over the queued closures. The old
  implementation recursed once per chained intermediate operation and
  popped from the front of the list on each call, giving O(n) Python stack
  depth (risking `RecursionError` on a long `.map()/.filter()/...` chain)
  and O(n²) time (since `list.pop(0)` is itself O(n), called n times) for a
  chain of n ops. Fixed by iterating the closures in order with a plain
  `for` loop and threading `iterable` through each step, dropping the
  `pop(0)` entirely — `_compose()` (`_sequential()`'s only caller) needed
  no changes since it already passes a fresh list copy. No change to
  `_sequential()`'s signature, return value, or `state_map` per-closure
  state lookup. Added `test_sequential_long_chain_does_not_recurse_at_build_time`
  (`tests/test_sequential.py`), calling `_sequential()` directly with a
  chain of `sys.getrecursionlimit() * 2` identity closures to isolate the
  build-time traversal this fix addresses.

  **Scope note, discovered during implementation:** this only fixes
  *building* the pipeline. Each individual op in `stream.py` (`filter`,
  `map`, `flat_map`, `sorted`, `peek`, `_DistinctOp`, `_LimitOp`,
  `_SkipOp`) is itself implemented as `async def fn(iterable): async for i
  in iterable: yield ...`, so *consuming* a long chain still recurses once
  per chained op at the `async for`/`__anext__()` delegation level,
  confirmed unchanged before and after this fix by testing a long
  `.map()` chain end-to-end. Fully closing the original roadmap item's
  stated risk requires a push-based execution-model redesign across every
  op in `stream.py` and `parallel_stream.py` — out of scope here and
  tracked as a new **Next**-bucket item. See
  `openspec/changes/rewrite-sequential-iterative`.
- Fixed `ParallelStream` crashing on any source with a real `await`
  suspension point. `ParallelStream._parallel` (`parallel_stream.py`) fanned
  `PROCESSES` racing branches out over the *same* shared `self._stream`
  async generator, each calling `__anext__()` on it independently; a source
  with a genuine `await` inside `__anext__()` raised
  `RuntimeError: anext(): asynchronous generator is already running` as soon
  as two branches' pulls overlapped. Fixed by adding a `_guarded(source,
  lock)` wrapper generator (`parallel_stream.py`): each branch gets its own
  wrapper instance, but all wrappers serialize their calls into the shared
  source's `__anext__()` (and `aclose()`) through one `asyncio.Lock` created
  per `_parallel()` call, so only one pull is ever in flight while
  downstream per-branch processing (`map`/`filter`/etc.) still runs
  concurrently. Fixing this surfaced a second, previously-latent race in
  `_LimitOp` (`stream.py`): its check-then-pull-then-increment sequence
  against the shared `size_holder` wasn't atomic once the pull could
  genuinely cede control, letting multiple branches pass the size check
  before any incremented and yield more than `n` elements in total. Fixed
  by reordering to reserve the slot (increment) *before* pulling, so the
  check-and-reserve step has no `await` between them and stays atomic
  across racing branches. Added `tests/test_parallel.py` coverage using a
  source with a real `await asyncio.sleep(0)` suspension point: empty and
  non-empty chains no longer raise, `.limit(n)` stays at-or-under `n` and
  closes the shared source safely across branches, and downstream mapper
  invocations still overlap despite serialized upstream pulls (timing
  assertion). No public API change. See
  `openspec/changes/fix-parallel-stream-await-crash`.
- Added `BaseStream.unordered()` — marks a stream instance as not
  order-dependent, mirroring Java's `BaseStream.unordered()`. Implemented as
  a `self._ordered: bool` flag on `BaseStream` (`base_stream.py`), defaulting
  to `True`; `unordered()` sets it `False` and returns `self`, matching the
  mutate-and-return-self convention every other chainable method already
  follows; `is_ordered()` exposes the current value, mirroring the existing
  `is_parallel()` query method. `sequential()`/`parallel()` now copy the
  flag onto the new instance they construct rather than resetting it, so an
  `unordered()` declaration survives a mode switch. Purely additive
  bookkeeping — no change to actual iteration order in `Stream` or
  `ParallelStream`; it exists to unblock the planned `forEachOrdered()` and
  `find_first()`/`find_any()` distinction (`stream.py`'s disabled
  `find_first` stub), neither of which consume the flag yet. Added
  `tests/test_unordered.py` covering: ordered-by-default for both `Stream`
  and `ParallelStream`, `unordered()` mutation and chaining (returns `self`,
  composes with other intermediate ops), isolation across separate `Stream`
  instances, and flag propagation across `.parallel()`/`.sequential()` mode
  switches (both directions, with and without `unordered()` called). See
  `openspec/changes/add-stream-unordered`.
- Added `BaseStream.iterator()` — exposes the composed stream chain as a
  plain `AsyncGenerator` without going through a collector, so a caller can
  drive consumption directly via `async for`, `__anext__()`, or partial
  iteration. Implemented as a thin wrapper around the existing `_compose()`
  mechanism already used by terminal operations (`base_stream.py`), so it
  works identically for `Stream` (sequential) and `ParallelStream` (parallel)
  with no subclass-specific override, and — like other terminal ops —
  composes non-destructively, leaving `self._chain` intact for later reuse.
  Added `tests/test_iterator.py` covering: no elements pulled before
  iteration starts, same elements/order as `collect(to_list)` for an
  equivalent chain, partial consumption, `ParallelStream` behavior (racing
  branches, unordered), and non-destructive composition (a second terminal
  op after `iterator()` still sees the full chain). No public API removal;
  purely additive. See `openspec/changes/archive/2026-08-13-add-stream-iterator`.
- Added `Stream.reduce(accumulator)` — the 1-arg, no-identity overload,
  returning `T | None` (`None` for an empty stream) rather than a wrapped
  `Optional[T]` type, matching the existing `find_any()`/`max()`/`min()`
  convention already used elsewhere in `stream.py`. Implemented as a single
  `reduce()` method carrying two `@overload` signatures (identity form and
  no-identity form) with one runtime body: a private `_UNSET` sentinel
  distinguishes "no identity given," in which case the first pulled element
  seeds the fold and an empty stream short-circuits to `None` before the
  accumulator is ever called; a single-element stream likewise returns that
  element without calling the accumulator. Delegates to the same
  `_maybe_await`-based accumulator dispatch the 2-arg form already used, so
  sync and async accumulators both work with no duplicated dispatch logic.
  Added a new `BinaryOperator` alias to `type.py` for the no-identity
  accumulator's `T, T -> T` shape, following the project's convention that
  composite/callable type shapes used in public signatures live in
  `type.py` rather than being written inline. Added 6 new tests in
  `tests/test_reduce.py` (empty stream, single-element stream, multi-element
  fold order, async-accumulator awaiting, a hypothesis property test against
  `functools.reduce`, and a regression check that the existing 2-arg form is
  unchanged). No changes to the existing `reduce(identity, accumulator)`
  behavior. See `openspec/changes/add-reduce-no-identity`.
- Added `Stream.skip(n)` — drops the first `n` elements pulled from upstream
  and yields the rest, symmetric with the already-implemented `limit(n)`.
  Implemented as `_SkipOp` (`stream.py`), mirroring `_LimitOp`'s
  `make_state()`/shared-state pattern so `ParallelStream._parallel()`'s
  existing generic `make_state()`-detection wires up correct parallel
  behavior (exactly `n` total elements dropped across all racing branches,
  not per-branch) with no `parallel_stream.py` changes needed. Unlike
  `limit()`, `skip()` has no short-circuit available — the first `n`
  elements must actually be pulled and discarded to advance upstream past
  them. Added `tests/test_skip.py` plus parallel-specific regression tests
  in `tests/test_parallel.py` (drops exactly `n` across branches, state
  fresh across separate streams). No public API change to existing methods.
  See `openspec/changes/add-stream-skip`.
- Made `Stream` generic (`Stream[T]`): `BaseStream`/`Stream`/`ParallelStream` were
  plain classes, so the `T`/`R` in their method signatures were unbound
  `TypeVar`s and element types were `Unknown` end to end — `ty` accepted
  `Stream.of([1,2,3]).map(lambda s: s.upper())` without complaint despite
  `int` having no `.upper()`. Fixed by making `BaseStream`/`Stream`/
  `ParallelStream` `Generic[T]`; `map()`/`flat_map()` now return `Stream[R]`
  via a narrowly-scoped `cast(Stream[R], self)` since the chain-of-closures
  model mutates and returns the same `self` rather than a new instance
  (deliberately not revisiting the separate mutable-builder-vs-immutable-
  pipeline decision below); type-preserving ops (`filter`, `distinct`,
  `peek`, `limit`, `sorted`) return `Stream[T]` directly; terminal ops are
  typed against the stream's bound `T`. Also fixed `type.py`'s `FlatMapper`
  alias, which hardcoded an unparameterized `Stream` instead of `Stream[R]`,
  and `StreamBuilder.build()`, which dropped its already-declared `T`
  instead of returning `Stream[T]`. Typing-only change, no runtime behavior
  differs. Added `tests/test_static_typing.py` plus `tests/typing/`
  fixtures that shell out to `ty check` to regression-test that the
  motivating bug is now caught and that valid generic usage still
  type-checks cleanly. See `openspec/changes/make-stream-generic`.
- Made `limit(n)` a real short-circuit: `_LimitOp.__call__` (`stream.py`) pulled
  an element from upstream *before* checking whether `max_size` had already
  been reached, so every `limit(n)` pipeline pulled `n+1` elements instead of
  `n` — e.g. `Stream.of([1,2,3,4,5]).peek(seen.append).limit(2)` returned
  `[1, 2]` but left `seen == [1, 2, 3]`. Fixed by checking the size before
  pulling rather than after, so upstream is closed without ever pulling an
  `n+1`th element. Under `.parallel()`, the shared `size_holder` in
  `ParallelStream._parallel`'s `state_map` already gave a global (not
  per-branch) limit guarantee; the fix changes *when* the shared source gets
  closed — whichever branch observes the shared count reaching `max_size`
  closes it before pulling further — and closure was made idempotent so a
  second racing branch closing (or pulling from) an already-closed shared
  source doesn't raise out of the task loop. No public API change. See
  `openspec/changes/archive/2026-08-12-fix-limit-short-circuit`.
- Replaced the repeated `if iscoroutinefunction(x): await x(...) else: x(...)`
  dispatch pattern (10 sites across `filter`, `map`, `sorted`'s comparator,
  `peek`, `reduce`, `for_each`, `min`/`max` via `_min_max`, and the
  `all_match`/`any_match`/`none_match` family) with a single
  `async def _maybe_await(fn, *args)` helper in a new
  `callable_dispatch.py`, which calls first and awaits the result only if
  `inspect.isawaitable(result)`. Fixes a real bug: `iscoroutinefunction()`
  is `False` for a class instance with an `async def __call__`, so passing
  such a callable object as a predicate/mapper/etc. previously produced an
  un-awaited coroutine flowing downstream as if it were a real value, with
  only a `RuntimeWarning` — no exception. `flat_map`'s existing
  `iscoroutinefunction()` check, which *rejects* coroutine-returning
  mappers up front, is a distinct pre-call classification and was left
  untouched. Also collapsed `all_match`/`any_match`/`none_match`'s three
  near-identical bodies into one shared `_match(predicate, short_circuit_on,
  default)` helper built on `_maybe_await`.

  `sorted()`'s comparator dispatch turned out not to fit the same
  call-then-await shape: its `iscoroutinefunction()` check picks between
  two different sort algorithms (`merge_sort`, which unconditionally
  awaits the comparator, vs. `list.sort()` with a sync `cmp_to_key`
  wrapper) rather than gating a single await. Fixed by moving `_merge`
  (`sort.py`) onto `_maybe_await` internally and always routing `sorted()`
  through `merge_sort` when a comparator is given, dropping the
  `cmp_to_key`/`list.sort()` branch entirely — this also closes the same
  async-callable-object gap for `sorted()`/`min()`/`max()`. Added
  regression tests (`tests/test_callable_dispatch.py`) covering
  `_maybe_await` directly (sync/async function, sync/async callable
  object) and each affected operation with an async-`__call__` callable
  object.
- Fixed two compounding bugs that made a second terminal operation on the
  same `Stream`/`ParallelStream` instance silently return wrong (usually
  empty) results instead of repeating the first run's behavior. First,
  `BaseStream._sequential()` (`base_stream.py`) was handed `self._chain`
  directly and called `pop(0)` on it, draining the caller's own chain list
  during `_compose()`; fixed by passing `self._chain[:]` (a copy) from
  `_compose()` instead — matching the copy `ParallelStream._parallel()`
  already made for its own branches, so both subclasses now honor the same
  non-destructive contract. Second, `distinct()`/`limit()` (`stream.py`)
  each built their `seen`/`size` state in the outer function that runs once
  per `.distinct()`/`.limit()` call, rather than in the closure that runs
  once per composition, so that state silently persisted across separate
  compositions of the same chain; fixed by replacing the two closures with
  small callable classes (`_DistinctOp`, `_LimitOp`) whose `__call__` takes
  an optional external state and falls back to fresh per-call state via
  their own `make_state()` when none is given — giving `Stream` (sequential)
  fresh state on every composition by default. For `ParallelStream`, where
  multiple racing branches must share one `seen`/`size` per composition to
  stay globally correct (matching Java's guarantee that parallel `distinct`/
  `limit` never silently degrade into a per-partition, unreconciled result,
  even though it costs more to coordinate — see
  `openspec/changes/fix-stream-rerun-state/design.md`), `_parallel()` now
  builds one state map per composition via each op's `make_state()` and
  passes the same map into every racing branch's `_sequential()` call.
  Added regression tests covering: chain length unaffected by composition,
  a second terminal op after the first, `distinct()`/`limit()` state not
  leaking across separate `Stream`/`ParallelStream` instances or across
  separate compositions of one instance, and parallel `distinct()`/`limit()`
  staying globally correct (no cross-branch duplicates, no over-`limit()`)
  across racing branches.
- Simplified `Stream.of()` (`stream.py`) from a four-way branch on dict vs.
  list vs. multiple positional args vs. kwargs down to two cases: a single
  positional arg passes straight through to `Stream()`'s existing source
  normalization, multiple args wrap into a list (one element each). The
  dict/list `isinstance` special-casing turned out to be dead complexity —
  tracing all 15 existing `test_of.py` cases showed it always produced the
  same call as the generic path, since `_normalize()` already re-spreads
  lists/dicts on its own. Also fixed `_normalize()` (`base_stream.py`) to
  treat `str`/`bytes` as scalar values, matching how Java's `Stream.of(T...)`
  treats `String`/`byte[]` atomically (byte arrays can't decompose via
  varargs since `T` can't bind to a primitive type), instead of the previous
  silent char-by-char/byte-by-byte spreading. Both changes are **BREAKING**
  and tracked in README's migration log per `CLAUDE.md`: `**kwargs` support
  is removed from `Stream.of()` entirely (no Java equivalent, undiscoverable,
  no real use case over `Stream.of(*some_dict.items())`), and
  `Stream.of("abc")`/`Stream.of(b"ab")` now yield one element instead of
  spreading.
- Added property-based tests with `hypothesis` for `map`, `filter`, `reduce`,
  `sorted`, `distinct` against a plain-Python reference oracle, covering
  edge cases hand-written tests miss (empty/single-element streams,
  duplicate keys, async callables).
- Added a `check_comparator_result_type()` runtime guard (`sort.py`) that
  raises `TypeError` if a user-supplied `Comparator` returns `bool` instead
  of `int`, used by `Stream._min_max()` (backing `min()`/`max()`) and both
  branches of `Stream.sorted()` (sync `cmp_to_key` path and the async
  `merge_sort`/`_merge` path). Closes a gap the earlier `Comparator`
  contract fix (below) didn't cover: Python's `bool` is a subclass of `int`,
  so a bool-returning comparator like `lambda x, y: x > y` type-checks fine
  under `ty`/mypy/pyright and previously degraded silently instead of
  erroring — for `min()` it could never signal "orders before" (always
  returning the first element), while `max()`'s behavior happened to be
  correct by coincidence. No static-typing trick can close this gap since
  it's structural to Python, not a `type.py` alias choice. Also fixed 18
  pre-existing tests across `tests/test_min.py`/`tests/test_max.py` that
  were passing bool comparators and only passed today via first-element
  luck (`min()`) or coincidence (`max()`); added regression tests asserting
  the `TypeError` for `min()`/`max()`/`sorted()`, sync and async. Tracked as
  **BREAKING** in README's migration log per `CLAUDE.md`.
- Fixed the `Comparator` type alias mismatch (`type.py:16`): kept a single
  Java-style 3-way *int* `Comparator` (matching `sorted()`'s existing usage
  and Java's own `Stream.min/max(Comparator)`), rather than splitting into
  two aliases, and fixed `Stream.min()`/`max()`/`_min_max()` (`stream.py`)
  to interpret the comparator's sign directly instead of treating it as a
  bool. This also fixed the tie-break bug for free: both `min()` and `max()`
  now keep the first of equal elements. Tracked as **BREAKING** in README's
  migration log per `CLAUDE.md` since bool-returning comparators passed to
  `min()`/`max()` now behave differently.
- Added an `install_smoke_test` CI job (`.github/workflows/check.yml`) that,
  for each of Python 3.10–3.14, creates a clean venv (`uv venv`, not
  `uv sync`), runs `pip install .` against the built package, and imports
  `snakestream` from outside the repo checkout — catching packaging
  mistakes that the source-tree `pytest` job wouldn't.
- Added static type checking to CI using `ty`, Astral's newer Rust-based
  type checker — chosen over `mypy`/`pyright` since it fit the existing
  `uv`/`ruff` toolchain and handled the codebase's `Awaitable`-union type
  aliases without issue. Fixed the 6 genuine type errors it surfaced
  (`BaseStream.on_close`'s return type, `ParallelStream`'s task-list
  typing, `StreamBuilder`'s unbound `TypeVar`, `Stream.collect`'s generic
  return type, and `Stream._min_max`'s sentinel-return typing), plus one
  scoped `ty: ignore` for a case the checker can't narrow via the
  runtime `iscoroutinefunction()` check in `Stream.sorted`. Gated to the
  3.14 matrix leg only, matching the coverage-gate precedent.
- Verified `--cov-fail-under=98` already enforces combined line+branch
  coverage, not line coverage alone: `[tool.coverage.run] branch = true`
  folds branch-arc misses into the same "percent covered" figure the gate
  reads, confirmed by observing a deliberately partial branch drop the
  reported percentage. No code change needed; added a comment in
  `pyproject.toml` recording the finding so it doesn't need re-deriving.
- `min()`/`max()` used to silently skip falsy candidate values (`0`, `""`,
  `False`) because of a truthiness check in `Stream._min_max`. Fixed by
  replacing the `None`-as-sentinel logic with a proper `_UNSET` sentinel.
- `parallel()` pipelines left orphaned `asyncio` tasks (and "Task exception
  was never retrieved" warnings) when one branch raised mid-stream. Fixed in
  `ParallelStream._parallel` by cancelling and draining remaining tasks in a
  `finally` block.
- Test infra was silently dropping tests on a clean install: `pytest-mock`
  was missing from `setup.cfg`'s `testing` extra, and the `async_int_to_letter`
  fixture in `conftest.py` wasn't decorated for strict-mode `pytest-asyncio`.
  Both fixed; added regression tests for the two bugs above
  (`test_min.py`, `test_max.py`, `test_exception.py`).
- `Stream.of()` had a dead branch, `if args and len(args) == 0: pass`
  (`stream.py:40-41`), which could never be true and just duplicated the
  no-op fallthrough of the `else` branch. Removed.
- The `TYPE_CHECKING`-only import in `stream.py:17` used an unqualified
  `from stream_builder import StreamBuilder`, which would fail if ever
  actually evaluated. Fixed to `from snakestream.stream_builder import
  StreamBuilder`.
- Added tests covering the async-predicate short-circuit branches of
  `all_match`, `none_match`, and `any_match` (`stream.py:255,267,283`) that
  were previously only exercised by synchronous predicates.
- Added a `--cov-fail-under=98` gate so a coverage regression now fails CI
  instead of silently passing. Enforced only on the newest Python version
  in `check.yml`'s matrix (not via `setup.cfg`'s `addopts`), since
  `coverage.py`'s branch-arc measurement for `async for` loops differs
  across CPython versions and produced spurious failures on 3.8/3.9.
- Fixed `deliver.yml` to target `master` instead of `main`, since the repo's
  default branch is `master` and the workflow was never triggering.
- Pinned GitHub Actions to commit SHAs and added concurrency guards to CI
  workflows.
- Added `pip-audit` dependency-vulnerability scanning and `ruff format`
  enforcement to CI.

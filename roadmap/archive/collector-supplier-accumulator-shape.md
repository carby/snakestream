+++
id = "collector-supplier-accumulator-shape"
title = "Redesigned the collectors around a `Collector(supplier, accumulator, combiner, finisher)` shape"
filed = 2026-08-20
closed = 2026-08-20
outcome = "shipped"
+++

**Redesigned `collector.py`'s collectors around a `Collector(supplier,
accumulator, combiner, finisher)` shape**, matching Java's `Collector<T,A,R>`
interface. Every factory (`to_list`, `joining`, `counting`, `summing_*`,
`averaging_*`, `min_by`/`max_by`, `reducing`, `to_map`, `to_set`,
`grouping_by`, `partitioning_by`) now returns a `Collector` instead of a
monolithic `async def _collect(composition): async for n in composition:
...` closure, driven through one new `_CollectorSink` (`TerminalSink`
adapter) rather than each factory hand-rolling its own drain loop. This
deletes the second, independent implementation of `terminals.py` that
`collector.py` used to carry: `_extremum` (gone, replaced by a shared
`_extremum` collector factory using the same tie-break and
comparator-guard as `_MinMaxSink`), the duplicate `_UNSET` sentinel (now
one, in `sink.py`), and the separate counting/reducing bodies.

Two **BREAKING** changes, both pre-1.0 and both contained — no test in the
457-test suite exercised either pattern: `collect(collector)` now requires
a `Collector` (or `to_generator`, wrapped as the one `StreamingCollector`
exception) rather than an arbitrary callable, and `grouping_by`/
`partitioning_by`'s `downstream` now requires a `Collector` too. The second
break has a real behavioral consequence: each group/partition now
accumulates into its own downstream container as elements arrive, instead
of being buffered as a list and replayed through `downstream` in a
post-pass — invisible for a pure downstream, but a downstream with side
effects (e.g. `to_map`'s duplicate-key `ValueError`) now observes them
interleaved with the source. Both are logged in README's migration log.

**The central design problem was dispatch-state lifetime, not the adapter
shape.** A `Collector` is explicitly reusable across streams and
compositions (`to_list` is a single shared module-level instance), so its
accumulator is one fixed function — it cannot hold the
`is_async`/`checked` classification flags a per-element user callable
(a mapper, comparator, key function) needs, the way the old per-collection
closures could. Every such factory's supplier now returns a small
`__slots__` container carrying that state alongside the accumulation
itself, so classification is created fresh per collection and never leaks
across collections or across a `ParallelStream`'s racing branches. This
keeps the per-element dispatch shape exactly as `add-callsite-dispatch`
left it — no per-element method call was added on any user callable's
hot path.

`TerminalSink.begin()`/`end()` in `sink.py` now await what
`_create_container()`/`_finish()` return (via the existing `_maybe_await`),
so an async `Collector` supplier or finisher works without every sink
needing its own override — every existing sink's plain return value passes
through unchanged. `sink.py` also gained `Box` (`Counter` is now a `Box`
subclass) as the general mutable-value container the scalar collectors'
per-collection state boxes build on.

Measured (interleaved reps, one process, 200k elements, matching the
`collapse-collector-sink-duplication` benchmark protocol): `collect(to_list)`
-37%, `collect(counting())` -39%, `collect(summing_int(...))` -18% —
faster in every case, not just neutral, since `collect()`'s single-`Collector`
path no longer goes through the generator bridge at all (it drives a
terminal sink directly, like every other terminal operation). 477 tests
pass (20 new, covering the `Collector` class itself, reuse-safety across
sequential/concurrent/parallel collections, the unused-`combiner`
guarantee, both rejection paths, and downstream-container isolation) at
98% coverage. See `openspec/changes/redesign-collector-shape`.

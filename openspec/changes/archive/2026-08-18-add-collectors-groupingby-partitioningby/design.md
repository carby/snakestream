## Context

`collector.py` collectors are plain factory functions returning an
`async def _closure(composition: AsyncGenerator) -> R` (see `CLAUDE.md`) —
no separate Collector class hierarchy, no accumulator/combiner/finisher
protocol like Java's `Collector<T,A,R>` interface. Every existing collector
consumes its `AsyncGenerator` input directly and produces its result in one
pass. `grouping_by`/`partitioning_by` are the first collectors that need to
run *another* collector (`downstream`) over a subset of the elements —
composition wasn't needed by anything shipped so far.

**Java signature fidelity.** This change tracks
`java.util.stream.Collectors` in arg order, overload count, and semantics:
- `static <T,K> Collector<T,?,Map<K,List<T>>> groupingBy(Function<T,K> classifier)`
- `static <T,K,A,D> Collector<T,?,Map<K,D>> groupingBy(Function<T,K> classifier, Collector<T,A,D> downstream)`
- `static <T> Collector<T,?,Map<Boolean,List<T>>> partitioningBy(Predicate<T> predicate)`
- `static <T,D,A> Collector<T,?,Map<Boolean,D>> partitioningBy(Predicate<T> predicate, Collector<T,A,D> downstream)`

Java's `groupingBy` also has a 3-arg `groupingBy(classifier, mapFactory,
downstream)` overload for choosing the backing `Map` implementation —
skipped here for the same reason `to_map`'s 4-arg `mapSupplier` overload was
skipped (see `openspec/changes/archive/2026-08-18-add-collectors-tomap-toset`):
Python has one general-purpose `dict`.

## Goals / Non-Goals

**Goals:**
- `grouping_by(classifier)` (no downstream) returns `dict[K, list[T]]`,
  matching Java's default `groupingBy(classifier)` (which defaults its
  downstream to `toList()`).
- `grouping_by(classifier, downstream)` returns `dict[K, R]`, running
  `downstream` — any existing `collector.py` collector — over each group's
  elements, matching Java's 2-arg `groupingBy`.
- `partitioning_by(predicate)` (no downstream) returns `dict[bool, list[T]]`
  with both `True` and `False` keys always present, matching Java's default
  `partitioningBy(predicate)`.
- `partitioning_by(predicate, downstream)` returns `dict[bool, R]`, running
  `downstream` over each partition's elements, matching Java's 2-arg
  `partitioningBy`.
- Both sync and async user callables (`classifier`/`predicate`) work, via
  the existing `_maybe_await` dispatch helper. `downstream` collectors are
  themselves already sync/async-callable-agnostic since they dispatch their
  own mappers/comparators/operators internally — no new dispatch needed at
  this layer.

**Non-Goals:**
- No `groupingBy(classifier, mapFactory, downstream)` 3-arg overload — no
  Python equivalent need, same rationale as `to_map`'s skipped 4-arg form.
- No `Collectors.groupingByConcurrent` — no concurrent-map equivalent
  attempted; matches this project's existing choice not to model Java's
  thread-based concurrency primitives.
- No new `type.py` aliases — `Mapper` covers `classifier`'s `T -> K` shape
  and `Predicate` covers `predicate`'s shape, both already used elsewhere in
  `collector.py`. `downstream`'s shape is the same
  `Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, R]]` every
  existing collector factory already returns — no alias exists for that
  shape today (each collector spells it out inline), and introducing one
  now is out of scope; `downstream` is typed with the same inline
  `Callable[...]` shape for consistency with existing call sites.

## Decisions

**Two-pass grouping: first bucket every element into `dict[K, list[T]]` (or
the two `list[T]` partitions), then run `downstream` once per bucket over an
async generator rebuilt from that list — not a single streaming pass that
feeds elements into per-key downstream "accumulators" as they arrive.**
Java's real `Collector<T,A,D>` interface supports true single-pass streaming
because it exposes a `supplier()`/`accumulator()`/`finisher()` triple that
`groupingBy` can invoke incrementally per key. This project's collectors
have no such triple — each is just `AsyncGenerator -> R`, consumed whole.
Making `downstream` streamable per-key would mean redesigning every
existing collector's shape, which is far more invasive than this change's
scope (and no other roadmap item has asked for it). Buffering into a
`dict[K, list[T]]` first, then handing each group's `list[T]` to
`downstream` via a small `_generator_of(items)` helper (an
`async def` that just yields each item — the async-native equivalent of
`iter(items)`), keeps `downstream` working with zero changes to any
existing collector. Trade-off: `grouping_by`/`partitioning_by` hold the
entire stream in memory before `downstream` ever runs (one list per group),
which is worse than Java's incremental accumulation but consistent with
this project's existing precedent — `sorted()` (`stream.py`) and
`to_list`/`to_map`/`to_set` already fully materialize their input, and nothing
in `collector.py` claims constant-memory streaming today.

**`grouping_by`/`partitioning_by` both default `downstream` to `to_list`,
matching Java's documented default (`groupingBy(classifier)` is defined as
`groupingBy(classifier, toList())` in the Javadoc, same for
`partitioningBy`).** `to_list` (`collector.py:29`) already exists and has
exactly the right shape (`AsyncGenerator -> list[Any]`) — reused directly,
no new default-list collector needed.

**`partitioning_by` always returns both `True` and `False` keys, even when
one partition is empty (`downstream` is still called once per key with an
empty async generator).** Matches Java's `Collectors.partitioningBy`
Javadoc guarantee that the resulting map always has two entries — unlike
`grouping_by`, which (matching `groupingBy`'s Javadoc) only includes keys
that were actually produced by `classifier` for at least one element.

**`grouping_by`/`partitioning_by` are two separate functions, not one
generalized `classifier`-returning-`bool` shortcut for partitioning.**
Mirrors Java's own choice to keep `partitioningBy` a distinct method from
`groupingBy` despite `bool` being expressible as a two-valued key — Java's
Javadoc calls out `partitioningBy` as more efficient for the boolean case
(the two-key structure needs no dict growth or key discovery), and this
project already follows Java's distinct-method-per-distinct-behavior
convention elsewhere (`min_by`/`max_by` staying separate rather than one
`extremum_by(asc)`).

## Risks / Trade-offs

[Two-pass buffering means the entire stream is held in memory as
`dict[K, list[T]]` before any `downstream` collector runs, unlike Java's
incremental per-key accumulation] → Accepted as a known, documented
limitation consistent with existing `collector.py`/`stream.py` precedent
(`to_list`, `to_map`, `to_set`, `sorted()` already fully materialize their
input); revisit only if a real streaming-memory need surfaces, which would
require redesigning every collector's shape, not just these two.

[Silently deviating from Java's exact overload arity/arg order/default
downstream would break the parity contract this library is built around] →
Mitigated by pinning the exact Java signatures and default-downstream
behavior in this document and writing tests asserting both the no-downstream
and downstream-given forms against Java's documented semantics, including
the always-both-keys guarantee for `partitioning_by`.

## Migration Plan

Purely additive — no existing call site changes, no deploy/rollback
concerns beyond a normal release.

## Open Questions

None.

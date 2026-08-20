## Context

See proposal.md — Why. The constraints that actually shape the approach:

- **`terminals.py` is the template, not the target.** `TerminalSink` already
  splits a terminal into container-creation (`begin`), per-element
  accumulation (`accept`) and finishing (`end`/`result()`). A Java `Collector`
  is the same three-way split expressed as data instead of as a subclass. The
  adapter is therefore small; the work is in rewriting fourteen factories.
- **Scope decision taken before planning** (confirmed with the user): this
  change de-duplicates in *one* direction only. `collector.py`'s copies go;
  `terminals.py`'s sinks stay exactly as they are, so `Stream.count()`,
  `min()`, `max()` and `reduce()` keep a per-element path with no extra call
  in it. Re-expressing those four on top of collectors is a separate,
  benchmark-gated question.
- **Compatibility decision taken before planning**: `collect()` takes a
  `Collector`, not any callable. Breaking, pre-1.0, and contained — no test in
  the suite passes a hand-written callable collector or `downstream`.
- **The hot-path precedent is binding.** `add-callsite-dispatch` was proposed,
  measured and rejected for adding a per-element wrapper coroutine around the
  dispatch triple (+32–75%). Nothing here may reintroduce that: the collectors'
  accumulators keep the canonical inlined shape or the plain-sync
  `_classify_step`, never an object whose `await`ed method is called per
  element.
- **`callable_dispatch.py`'s comment is a hard rule**, not a style note:
  classification state (`is_async`/`checked`) must never live anywhere that
  outlives one composition. Today each factory returns a fresh closure and
  keeps that state in the *inner* generator body. A `Collector` inverts this —
  its accumulator is one fixed function shared by every collection — so the
  state has to move somewhere per-collection. That is the central design
  problem below (Decision 5).

## Goals / Non-Goals

**Goals:**
- One drive path for every collector, so `collector.py` stops carrying a
  second implementation of `terminals.py`.
- The `Collector` value is public, documented, reusable and user-constructible
  — a user can write one without touching a sink.
- `grouping_by`/`partitioning_by` accumulate per key into downstream
  containers, which is the shape a future combiner can merge.
- No per-element regression; `collect(to_list)` should get slightly *faster*,
  since the generator bridge drops out of its path.

**Non-Goals:**
- Touching any sink in `terminals.py`, or routing `Stream.count()`/`min()`/
  `max()`/`reduce()` through a `Collector`.
- Invoking `combiner`. It is stored and unused, exactly as the two combiners
  already shipped are.
- Adding `mapping`, `collectingAndThen`, `summarizing*` or `to_collection`
  (roadmap item 2). This change is what makes them cheap; it does not do them.
- Making `to_generator` a `Collector`. It cannot be one.

## Decisions

### 1. `Collector` is a value holding four callables, not an ABC to subclass

`Collector(supplier, accumulator, combiner=None, finisher=None)`, a small
public class with `__slots__`, generic in `[T, A, R]`.

*Alternative rejected — an ABC with `supplier()`/`accumulator()`/`finisher()`
methods, subclassed per collector.* That is Java's literal interface, and it
would put us back to fourteen classes — the exact shape the `collapse-op-
classes` change spent effort removing from `ops.py`. Java itself does not
subclass per collector either: every `Collectors` static goes through
`Collector.of(supplier, accumulator, combiner, finisher)`, which is the
four-callable value form. A value also makes the collectors composable by
construction, which is what item 2's `mapping`/`collectingAndThen` need.

`__eq__`/`__hash__` are left at identity: a `Collector` is used as a key
nowhere, and structural equality over closures is meaningless.

### 2. The accumulator mutates its container and its return value is ignored

Java's `BiConsumer<A,T>`, and identical to the accumulator
`Stream.collect(supplier, accumulator, combiner)` already takes — which is the
decisive argument: two accumulator conventions in one library would be worse
than either.

*Alternative rejected — a fold-style `(container, element) -> container`.* It
reads better for scalars (`lambda acc, e: acc + e`) but diverges from both
Java and the shipped 3-arg `collect()`, and it forces every accumulator's
result to be awaited-and-stored on the per-element path even when it mutates.

The cost is that scalar accumulations need a mutable box (Decision 3).

### 3. `sink.py` grows a `Box`, and `Counter` becomes a `Box` with an `int` default

`counting()`, `summing_*`, `averaging_*`, `min_by`/`max_by` and `reducing`
accumulate a scalar, which a mutating accumulator cannot rebind. `sink.py`
already has exactly the right object for this — `Counter`, a `__slots__`
mutable `.value` box — but typed to `int` and named for one use.

Add `Box` (`__slots__ = ("value",)`, any value) and make `Counter(Box)` a
subclass whose default is `0`. `Counter` keeps its name and docstring, since
op shared-state is a real and distinct use of it, and nothing that imports it
changes.

### 4. `_UNSET` moves to `sink.py`; `_CollectorSink` lives in `collector.py`

The two `_UNSET` sentinels named in the roadmap collapse into one. It cannot
stay in `terminals.py`, because `collector.py` must not import
`terminals.py` — `collector.py` is imported by `stream.py` alongside it, and a
dependency between them would make the "collectors and terminals share an
implementation" direction harder to take later, not easier. `sink.py` is the
module both already sit on. `stream.py`'s existing `from snakestream.terminals
import _UNSET` moves to `sink.py`; no re-export is left behind, so there is
one home for it.

For the same reason `_CollectorSink` — the `TerminalSink` that adapts a
`Collector` — lives in `collector.py`, beside the thing it adapts, rather than
in `terminals.py`. The import graph stays one-way: `collector.py` → `sink.py`,
`base_stream.py`, `callable_dispatch.py`.

### 5. Per-collection dispatch state lives in the container, not in the factory closure

This is the crux. A `Collector` instance is reusable across streams and
compositions, so its accumulator is one fixed function. Any user callable that
accumulator invokes per element — `summing_int`'s mapper, `min_by`'s
comparator, `to_map`'s key/value/merge, `grouping_by`'s classifier — carries
`is_async`/`checked` classification state that **must** be per collection, or
classification leaks between collections and, worse, between a
`ParallelStream`'s branches.

The supplier is the only per-collection hook, so the container is where that
state goes: each such factory's supplier returns a small private `__slots__`
container holding both the accumulation and the classification flags. The
accumulator reads and writes those attributes through `_classify_step` (the
plain sync helper) or the inlined canonical shape — never through an object
whose method is awaited per element, per the `add-callsite-dispatch`
rejection.

*Alternative rejected — hold the flags on `_CollectorSink`.* The sink is
per-collection too, so it would work, but the sink is generic over all
collectors and would need to carry an arbitrary number of dispatch triples for
callables it knows nothing about. `_CollectorSink` keeps exactly one
`AsyncDispatch` — for the accumulator itself — and every collector-specific
callable is the container's business.

*Alternative rejected — classify eagerly in the factory.* `is_async_callable`
is cheap and could run once at factory time, but the `checked` safety net (a
plain `def __call__` returning a coroutine) fundamentally cannot: it can only
fire on a real first result, and that result belongs to a collection.

### 6. `TerminalSink._create_container()` and `_finish()` may return an awaitable

A `Collector`'s supplier and finisher may be `async def`. Rather than have
`_CollectorSink` override `begin()`/`end()` — which would leave the abstract
`_create_container()` implemented-but-never-called and dent the coverage gate
— `TerminalSink.begin()`/`end()` in `sink.py` await what the hook returns via
the existing `_maybe_await`. Every current sink returns a plain value, which
passes straight through the `isawaitable` check unchanged. The cost is two
`isawaitable` checks and two wrapper coroutines **per collection**, not per
element.

This also gives `grouping_by`/`partitioning_by` what they need: their finisher
awaits each key's downstream finisher, which may itself be async.

### 7. `to_generator` becomes a `StreamingCollector`, so `collect()` dispatches on type only

`collect()` needs three branches: a `Collector` (drive a sink), `to_generator`
(compose through the bridge and return the generator, un-awaited), and
anything else (`StreamBuildException`). Making the middle branch an identity
check — `arg is to_generator` — hardcodes one module-level name into
`Stream.collect()`.

Instead, `collector.py` exposes a tiny public `StreamingCollector` wrapping a
`(composition) -> AsyncGenerator` callable, and `to_generator` is an instance
of it. `collect()` then tests two types and raises otherwise. `to_generator`
stays directly callable via `__call__`, so `to_generator(gen)` and
`collect(to_generator)` both read exactly as they do today.

*Alternative considered — the identity check.* One line versus roughly six,
but it means any future lazy collector reopens `Stream.collect()`. The type
form also gives the rejection message something honest to say.

### 8. `to_list` stays a bare name; `to_set()` stays a factory

`to_list` becomes a module-level `Collector` instance so `collect(to_list)`,
`to_array()` and every README example are untouched. This is safe precisely
because a `Collector` holds no per-collection state — the supplier makes a
fresh `list` each time — and it is the reason Decision 5 matters.

`to_set()` keeps its parentheses: it already ships that way, matching Java's
`toSet()`, and changing it would be a second, gratuitous break. The
inconsistency between the two is pre-existing and not this change's to fix.

### 9. `grouping_by`/`partitioning_by` accumulate per key as elements arrive

The container is `{key: downstream_container}` plus the classifier's dispatch
flags. On each element: classify the key, `setdefault` the key's container
from `downstream.supplier()`, then run `downstream.accumulator`. The finisher
maps `downstream.finisher` over the values. `_generator_of` and the
buffer-then-replay round trip are deleted; `_group_into` survives as the
shared accumulator step, with `partitioning_by` keeping its separate
`coerce_key` (the `bool()`-wrapper trap that `tests/test_partitioning_by.py:37`
already catches is unchanged by this redesign).

**Observable consequence, accepted:** a downstream collector's accumulator now
runs interleaved with the source rather than in a post-pass. For a pure
downstream this is invisible. For one with side effects the interleaving is
visible, and `grouping_by(k, to_map(...))`'s duplicate-key `ValueError` now
raises mid-stream rather than after it. This is the behavior that makes
per-key results mergeable later, and matches Java, where `groupingBy` feeds
its downstream accumulator directly.

### 10. Rejection uses `StreamBuildException`

`flat_map()` already rejects a wrongly-shaped user callable with
`StreamBuildException` at build time; the same exception for "this is not a
`Collector`" keeps one story. The message names `Collector` and points at
`to_generator` as the exception.

### 11. `type.py` gains `A`, `Finisher` and `Combiner`

Per the project's convention that composite/callable types live in `type.py`,
not inline. `Supplier` and `BiConsumer` already exist and are reused as the
supplier/accumulator aliases. This also retires the inline
`Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, Any]]` annotations at
`collector.py:348`/`:359` and the ~20 similar return annotations across the
module — every factory's return type becomes `Collector[...]`.

## Risks / Trade-offs

- **Dispatch-state leaks between collections** (the failure mode Decision 5
  exists to prevent) → every stateful container gets a test that collects the
  same `Collector` instance twice, and one that collects it on a
  `.parallel()` stream, asserting the second result is not contaminated by the
  first.
- **Per-element cost of the extra accumulator call.** Today's factories inline
  their loop body; the new shape calls `accumulator(container, element)` once
  per element. Against that, every collector loses the generator bridge, the
  `_drive` buffer/yield round trip and the `async for` in the closure →
  measure `collect(to_list)`, `collect(counting())` and
  `collect(summing_int(len))` before and after, interleaved reps in one
  process, as `collapse-collector-sink-duplication` did. Expectation is
  neutral-to-faster; a regression on the scale that sank `add-callsite-
  dispatch` is the stop condition.
- **Two breaking changes at once** (callable collectors, callable
  `downstream`) → contained: no test uses either, every library collector
  keeps working as a `downstream`, and both get migration-log entries. The
  rejection raises rather than silently misbehaving.
- **`grouping_by`'s interleaved downstream** (Decision 9) → documented in the
  spec delta and the migration log; the only realistic breakage is error
  *timing*, not error presence.
- **Coverage gate.** Fourteen factories collapsing to declarations removes
  statements faster than tests; the 98% floor must hold. New tests for the
  `Collector` class and the rejection paths are part of the change, not a
  follow-up.
- **`ty` on a generic `Collector[T, A, R]` with a module-level `to_list`
  instance** → a bare instance cannot be generic in the element type, so
  `Stream[int].collect(to_list)` types as `list[Any]`. That is exactly what it
  types as today (`to_list` returns `list[Any]`), so this is a
  non-regression, not an improvement; `generic-stream-typing`'s scenario
  stays as aspirational as it already was.

## Migration Plan

Pre-1.0, so no deprecation window; both breaks are announced in README's
migration log under `0.3.5 -> next`, matching the seven entries already there:

1. `collect(collector)` requires a `Collector`. A hand-written
   `async def my_collector(composition)` becomes
   `Collector(supplier, accumulator, finisher=...)`, or keeps its old shape
   wrapped in `StreamingCollector` if it is genuinely lazy.
2. `grouping_by`/`partitioning_by`'s `downstream` requires a `Collector`.
   Every `collector.py` factory already satisfies this; only hand-written
   closures need converting.

Rollback is a revert: nothing persists, and no on-disk or wire format is
involved.

## Context

Today `BaseStream._chain` is a list of closures, each an async generator of
the shape `async def fn(iterable): async for i in iterable: yield ...`.
`_sequential()` nests them by feeding each closure the previous one's output,
and `_compose()` returns the outermost generator. Consumption is therefore
pull-based: the terminal `async for` drives `__anext__()` down through every
op.

Three consequences motivate the redesign (see `proposal.md`):

1. Stateful ops carry state through an ad-hoc convention — an optional second
   positional argument plus a `make_state()` attribute that
   `ParallelStream._parallel()` discovers via `getattr`. Only `_DistinctOp`,
   `_LimitOp` and `_SkipOp` implement it.
2. `limit()` short-circuits by reaching *up* and calling
   `await iterable.aclose()` on its own upstream from inside the op.
3. There is no interface for a terminal operation to plug into, which is why
   the planned `Collector(supplier, accumulator, combiner, finisher)` work is
   currently scoped as a second, independent redesign.

Benchmarking on 2026-08-18 (Python 3.14, 20,000 elements, chain of 8 ops)
measured a Java-faithful `Sink` chain at 4,806 ns/element against today's
5,681 — a 15–17% gain — while a flat driving loop measured *slower*. The
earlier `RecursionError` justification was retired: Java's own
`Sink.ChainedReference.accept()` calls `downstream.accept()` and is equally
O(k) stack-deep per element.

## Goals / Non-Goals

**Goals:**

- Replace nested async-generator delegation with a push-based `Sink` protocol:
  `begin(state_map)` / `accept(element)` / `end()` / `cancellation_requested()`.
- Reimplement all eight intermediate ops (`filter`, `map`, `flat_map`,
  `sorted`, `peek`, `distinct`, `limit`, `skip`) as sinks.
- Define the **terminal seat** — a sink with no downstream that accumulates
  and produces a result — and ship one implementation of it, so the follow-on
  Collector redesign occupies an existing seat rather than inventing one.
- Make per-composition and cross-branch shared state first-class via
  `begin(state_map)`, retiring the `make_state()`/`getattr` convention.
- Preserve every observable behavior currently specified in
  `pipeline-composition`, `pipeline-immutability`, and `stream-ordering`.

**Non-Goals:**

- Changing any public API. No signature, return type, or documented behavior
  changes; this is not a **BREAKING** change.
- Pushing all the way to the terminal. `_compose()` continues to return an
  `AsyncGenerator[T, None]`, so all 11 terminal ops, every collector,
  `iterator()`, and `_concat` are untouched. This deliberately avoids needing
  a pull bridge (`Spliterator`), which is parked in **Later**.
- Fixing `RecursionError` on very long chains. The per-element `accept()`
  chain is O(k) stack-deep, exactly as today and exactly as Java. The measured
  ceiling (~1,000 ops) is unchanged.
- Rewriting `collector.py`. Collectors keep consuming an `AsyncGenerator`;
  the Collector redesign is a separate, sequenced follow-on.
- Implementing real parallelism or wiring up `combiner`. Both stay in
  **Later**.

## Decisions

### Decision 1: The chain holds op objects; sinks are built per composition

**Chosen:** `_chain` becomes a list of *op* objects, each exposing
`link(downstream) -> Sink` and (optionally) `make_shared_state() -> Any`.
`_sequential()` walks the op list right-to-left, calling `link()` to build a
fresh sink instance per op per composition, terminating at the terminal sink.

**Why:** Sinks are stateful per composition; ops are not. Keeping the chain
made of stateless, reusable op objects preserves the existing
`pipeline-composition` guarantee that composing never mutates the chain, and
gives `ParallelStream` a stable identity (the op) to key shared state on, the
same role `state_map` plays today.

**Alternative considered:** make `_chain` a list of sinks directly and clone
them per composition. Rejected — cloning stateful objects correctly is
strictly harder than constructing them from a stateless descriptor, and the
op/sink split is what Java does (`ReferencePipeline` stage vs. `Sink`).

### Decision 2: `begin(state_map)` propagates; each sink extracts its own slice

**Chosen:** one argument, propagated down the chain. Each sink's `begin()`
looks up its own op in the map, stores whatever it finds (or builds fresh
local state if absent), then awaits `downstream.begin(state_map)`.

`Stream._compose()` builds a **fresh** state map on every composition, so
sequential per-composition state reset is preserved by construction.
`ParallelStream._parallel()` builds **one** state map and passes it into every
branch's `begin()`, so `distinct`/`limit`/`skip` stay globally correct across
racing branches — the same guarantee, delivered by an explicit protocol call
rather than `getattr(fn, "make_state", None)` introspection.

**Alternative considered:** pass each sink its state at `link()` time.
Rejected — it splits initialization across two phases, and `begin()` is the
call whose signature must match a `Collector`'s `supplier`.

### Decision 3: Push internally, bridge back to a generator at the tail

**Chosen:** `_compose()` builds the sink chain onto a *bridge* terminal sink
whose container is a buffer, then drives it:

```
async with aclosing(source) as src:
    await head.begin(state_map)
    async for item in src:
        await head.accept(item)
        drain buffer -> yield
        if head.cancellation_requested(): break
    await head.end()
    drain buffer -> yield
```

One `accept()` may push zero elements (`filter`), one (`map`), or many
(`flat_map`), and `sorted` pushes everything from `end()` — the buffer absorbs
all three cases uniformly.

**Why:** it confines the change to three files plus one new module, and needs
no `Spliterator`. The bridge sink is a genuine terminal sink (container from
`begin`, accumulate in `accept`, finish in `end`), so it validates the
terminal seat rather than sidestepping it.

**Alternative considered:** push all the way to the terminal (Java-faithful).
Rejected for this change — `iterator()` and `to_generator()` are inherently
pull-shaped, and bridging back is exactly what Java uses `Spliterator` for,
which is parked in **Later**.

### Decision 4: Ship the terminal seat now

**Chosen:** the protocol defines a terminal sink as one with no `downstream`,
whose `begin()` creates a container, whose `accept()` accumulates into it, and
whose `end()` finishes it into a result retrievable via `result()`. The bridge
sink is the one implementation shipped here.

**Why:** `begin`/`accept`/`end`/`result` is exactly
`supplier`/`accumulator`/`finisher`. Defining the seat now means the Collector
redesign is a plug-in, not a protocol change. The cost is small — the bridge
sink has to exist regardless, and giving it the terminal shape is nearly free.

**Alternative considered:** intermediate sinks only, let the Collector work
retrofit a terminal seat. Rejected per the user's scoping decision; retrofitting
would mean designing the seat against a protocol already frozen without it.

### Decision 5: `limit()` short-circuits via `cancellation_requested()`

**Chosen:** `limit`'s sink increments and checks the shared counter inside
`accept()` with no `await` between check and increment, and reports
cancellation upward via `cancellation_requested()`, which each intermediate
sink forwards to its downstream. The driving loop in `_compose()` checks it
after each `accept()` and stops pulling.

**Why:** this preserves the "pull at most `n`, never `n+1`" guarantee (the nth
`accept()` sets the flag; the loop breaks before pulling again) without the op
reaching up to close its own upstream. It also makes the reserve-before-pull
atomicity that today's `_LimitOp` comment describes structural rather than
incidental, since `accept()` has no suspension point between the two.

**Consequence:** source closing moves from inside `limit` to the driving
loop's `aclosing(source)`, and `ParallelStream`'s `_guarded()` wrapper keeps
serializing pulls and closes under the shared lock as it does today. The
existing "a second branch pulling from a closed shared source terminates
cleanly" guarantee is preserved.

### Decision 6: `flat_map()` drops `to_generator`, keeps `aclosing`

**Chosen:** `flat_map`'s sink pushes the inner stream's elements downstream by
iterating `flat_mapper(i)`'s own composition directly, dropping the
`collect(to_generator)` second-layer wrapper. It still wraps that composition
in `aclosing()`.

**Why:** the proposal's framing that push "sheds the `aclosing()`/
`to_generator` machinery" is only half right, and this design corrects it. One
wrapper layer does go away. But the inner stream remains pull-shaped, so when
downstream cancellation breaks the inner loop mid-iteration, the inner
generator is still abandoned unless explicitly closed — and
`pipeline-composition` has an explicit requirement that it be closed. Dropping
`aclosing()` would regress a shipped, tested guarantee.

### Decision 7: New module `sink.py`

Per the project's module-naming convention (name for what's inside, no
`util.py`), the protocol and the bridge/terminal sinks live in
`src/snakestream/sink.py`. Per-op sinks stay in `stream.py` alongside the
methods that construct them. New composite/callable type aliases go in
`type.py`.

## Risks / Trade-offs

- **The bridge gives back part of the measured 15–17% gain.** → The 4,806
  ns/element figure was measured pushing straight to a terminal, with no
  buffer-and-yield step per element. Buffering plus a generator `yield` per
  element re-introduces some of the cost the benchmark removed. Mitigation:
  benchmark the real implementation against today's before merging and record
  the actual number; if it lands at parity or worse, the architectural
  argument (the Collector seat, first-class state) still stands on its own and
  should be stated as the sole justification rather than a performance claim.

- **Element-arrival timing shifts slightly.** → Today a `yield` deep in the
  chain surfaces immediately; with the bridge, elements produced by one
  `accept()` surface after that `accept()` returns. For every op in the chain
  this is unobservable (they all run inside the push), but a consumer
  interleaving work with `async for` sees a marginally different suspension
  pattern. No spec asserts on this; flagged so it is not mistaken for a bug.

- **`sorted()` still blocks the whole stream.** → Unchanged: it buffers in
  `accept()` and emits from `end()`. Not a regression, but also not fixed here.

- **Long-chain `RecursionError` is not fixed and could look like a
  regression.** → The per-element `accept()` chain is O(k) deep just as
  today's `__anext__()` delegation is. `pipeline-composition`'s existing note
  scoping the recursion requirement to *build* time remains accurate and
  should be carried forward verbatim in the delta spec.

- **Broad blast radius across three core files with no public API change to
  signal it.** → The entire existing test suite is the regression gate, and it
  is substantial (per-op suites, `test_parallel.py`, `test_sequential.py`,
  `test_pipeline_immutability.py`, hypothesis property tests against plain
  Python oracles). Requirement: the full suite must pass unmodified — any test
  that needs editing to pass is evidence of a behavior change and must be
  justified, not accommodated. The 98% coverage gate applies as usual.

- **`ParallelStream` is the highest-risk surface.** → Its racing branches,
  shared lock, shared state and early-close interactions are where the current
  design's subtleties live (three separate shipped fixes touch them).
  Mitigation: port `_parallel()` last, after sequential is green, and treat
  the existing parallel scenarios in `pipeline-composition` as the acceptance
  bar.

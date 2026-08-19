## Context

The Sink-chain redesign (`2026-08-18`) split every intermediate operation into a pair: an **op** object, held in `BaseStream._chain`, which carries the user's arguments and knows how to build a sink; and a **sink**, built by `op.link(downstream)` at drive time, which does the per-element work. The sink half got real ABCs in `sink.py` (`Sink`, `IntermediateSink`, `TerminalSink`). The op half got nothing — it is a convention enforced only by the fact that all eight ops happen to be written the same way.

Two visible consequences today:

1. `base_stream.py` types the chain as `list[Any]` throughout (`_chain: list[Any]`, `_derive(op: Any)`, `_sequential(intermediaries: list[Any], ...)`), so `ty` — gated in CI on the 3.14 leg — can see nothing about what flows through the pipeline's central data structure.
2. `parallel_stream.py:36` cannot simply ask an op for its shared state; it has to sniff for the method:
   ```python
   make_shared_state = getattr(op, "make_shared_state", None)
   if make_shared_state is not None:
       state_map[op] = make_shared_state()
   ```
   because five of the eight ops are stateless and don't define it.

Three ops are stateful (`_DistinctOp` → a `set`, `_LimitOp` → `[0]`, `_SkipOp` → `[0]`); five are not (`_FilterOp`, `_MapOp`, `_PeekOp`, `_SortedOp`, `_FlatMapOp`). The shared-state mechanism exists for `ParallelStream`, which builds N sink chains from the *same* op list and needs the stateful sinks in those chains to share one state instance — see `sink-protocol`'s "Shared state is delivered through begin".

## Goals / Non-Goals

**Goals:**

- Give the op half of the op/sink convention a real ABC, so the protocol the redesign introduced is fully typed.
- Type `_chain` and everything that takes or passes it against that ABC.
- Turn the `getattr` sniff into an ordinary method call.
- Zero behavior change; zero public API change.

**Non-Goals:**

- Collapsing the eight op classes onto a shared implementation base (`*args` + `_sink_cls`), giving the three stateful sinks a `StatefulSink` base, or replacing the one-element-list counter boxes. That is the roadmap's *next* item and depends on this one; keeping them separate keeps this change a pure type addition with no logic edited.
- Moving op/sink definitions out of `stream.py` into `ops.py` (roadmap item after that).
- Anything about terminal operations or collectors.
- Making `Op` generic in the element type. The sinks are `Generic[T]` but the chain is heterogeneous (a `map` changes the element type mid-chain), so a `list[Op[T]]` would be a lie; `Op` stays non-generic, matching how `link` already returns `Sink[Any]`.

## Decisions

### `make_shared_state()` is concrete on `Op`, returning `None`

`Op` gets one abstract method, `link(downstream: Sink[Any]) -> Sink[Any]`, and one concrete method:

```python
def make_shared_state(self) -> Any:
    return None
```

Stateless ops inherit it and say nothing. `ParallelStream._parallel` then calls it unconditionally and only records a map entry when the result is not `None`:

```python
for op in intermediaries:
    state = op.make_shared_state()
    if state is not None:
        state_map[op] = state
```

*Alternative considered:* make `make_shared_state()` abstract and force all eight ops to implement it. Rejected — it makes five ops carry a `return None` stub for no gain, and the roadmap's next item wants those five to collapse to a class attribute each.

*Alternative considered:* keep the `None` sentinel out of it and add a separate `is_stateful` flag or have `_parallel` check `type(op).make_shared_state is not Op.make_shared_state`. Rejected — the flag duplicates information already carried by the return value, and the identity check is the `getattr` sniff wearing a different hat.

*Consequence worth stating:* `None` is now reserved as "no shared state". No shipped op returns `None` as a meaningful state, and a future op that wants one should use an empty container instead (`set()`, `[]`, a counter object) — which is what all three stateful ops already do. This is written into the spec delta so it is a contract, not an accident.

### `Op` lives in `sink.py`, not a new module

`sink.py` already holds the other half of the same protocol, and `Op.link` returns a `Sink`, so the dependency points that way anyway. A separate `op.py` would be two files that always import each other.

*Note:* the roadmap's later item moves the op/sink *implementations* (`_FilterOp`/`_FilterSink` and friends) from `stream.py` to a new `ops.py`. That is about the concrete pairs, not the ABCs — the ABCs stay in `sink.py` either way, and this decision does not pre-empt that move.

### `Op` is an ABC, matching `Sink`

`Sink` is `ABC` with `@abstractmethod`s rather than a `typing.Protocol`. `Op` follows it for consistency, and because the ops are all first-party classes we control — there is no third-party op to structurally type against. Making `Op` a nominal base also means `isinstance(op, Op)` is available to tests.

### The chain's type is `list[Op]`

`BaseStream._chain: list[Op]`, `_derive(op: Op)`, `_sequential(intermediaries: list[Op], terminal: Sink[Any])`, `_drive(chain: list[Op], ...)`, `ParallelStream._parallel(intermediaries: list[Op], ...)`. `_sequential`'s body (`sink = op.link(sink)`) becomes checkable rather than an `Any` call.

## Risks / Trade-offs

- **`ty` surfaces pre-existing type errors once the chain stops being `Any`.** → Expected and part of the point; the chain's own call sites are only `op.link(...)` and `op.make_shared_state()`. If `ty` flags something beyond those two, fix it if it is a one-liner and note it in the change if it is not — do not let scope creep into the ops' internals, which the next roadmap item rewrites anyway.
- **`None` as the no-state sentinel forecloses a legitimately-`None` shared state.** → Accepted and specified; every real state is a mutable container, and a container is what shared state has to be for sharing to mean anything.
- **Adding a base class to eight classes is a wide diff for zero behavior change.** → The diff is mechanical: one base class per op, and no method bodies touched — the three stateful ops keep their `make_shared_state` overrides verbatim. Full suite (394 tests) must pass unmodified apart from the new `Op` tests; that is the check that nothing moved.
- **`ParallelStream` state-map behavior changes shape even though it should not change outcome.** → The old sniff and the new call select exactly the same three ops today. Covered by keeping the existing parallel `distinct`/`limit`/`skip` tests green plus an explicit test that a stateless op contributes no state-map entry.

## Migration Plan

Not applicable — internal, no persisted state, no public API. Rollback is reverting the commit.

## Open Questions

None.

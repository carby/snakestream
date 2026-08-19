## Why

The Sink-chain redesign defined `Sink`/`IntermediateSink`/`TerminalSink` as real ABCs in `sink.py`, but gave the *op* half of the op/sink pair no type at all: it exists only as convention. `base_stream.py` types the chain as `list[Any]` (`_chain`, `_derive(op: Any)`, `_sequential(intermediaries: list[Any], ...)`) and `parallel_stream.py:36` discovers an op's shared state by sniffing with `getattr(op, "make_shared_state", None)`. Half the protocol the redesign introduced is therefore invisible to `ty`, which is already gated in CI on the 3.14 leg.

## What Changes

- Add an `Op` ABC to `sink.py` with an abstract `link(downstream: Sink[Any]) -> Sink[Any]` and a concrete `make_shared_state() -> Any` that returns `None` by default.
- Make the eight existing op classes in `stream.py` (`_FilterOp`, `_MapOp`, `_PeekOp`, `_SortedOp`, `_FlatMapOp`, `_DistinctOp`, `_LimitOp`, `_SkipOp`) subclass `Op`. The three stateful ones (`_DistinctOp`, `_LimitOp`, `_SkipOp`) keep their `make_shared_state()` overrides; the other five inherit the `None`-returning default.
- Type the chain against `Op`: `BaseStream._chain: list[Op]`, `_derive(op: Op)`, `_sequential(intermediaries: list[Op], ...)`, and `ParallelStream._parallel(intermediaries: list[Op], ...)`.
- Replace the `getattr(op, "make_shared_state", None)` sniff in `ParallelStream._parallel` with a plain `op.make_shared_state()` call, keying the state map only for ops that return a non-`None` state.
- No public API change, no behavior change: this is a typing and protocol-completion change.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `sink-protocol`: the requirement "Shared state is delivered through begin" currently says only that operations requiring shared state "SHALL expose a factory". This change adds a requirement that operations are a typed protocol (`link`, `make_shared_state`) that every operation implements — including the stateless ones, via a default returning no state — so callers can call the factory unconditionally rather than probing for its presence.

## Impact

- `src/snakestream/sink.py` — new `Op` ABC.
- `src/snakestream/stream.py` — eight op classes gain a base class; no logic change.
- `src/snakestream/base_stream.py` — `_chain`, `_derive`, `_sequential` annotations.
- `src/snakestream/parallel_stream.py` — `_parallel` annotation; `getattr` sniff becomes a method call.
- `tests/` — a test for the `Op` protocol (default `make_shared_state()` returns `None`; every shipped op is an `Op`).
- No dependency, packaging, or public-API impact. Unblocks the roadmap's next item (collapsing the seven near-identical `*Op` classes onto a shared base).

## Why

`BaseStream._drive()`, `BaseStream._drive_to_sequential()` and
`ParallelStream._drive_to()` each implement the same sequence: `begin(state_map)`,
a cancellation guard before the first pull, `async for ... accept ... check
cancellation`, `end()`. The guard exists for a specific reason — a chain can
already be cancelled before it has seen anything (`limit(0)`), and pulling even
one element would run every upstream op on a value nobody wants — but that
reasoning is carried by a comment in only one of the three copies. This is the
code most likely to drift: the two undocumented copies read like defensive
`if`s that a later reader could delete.

## What Changes

- Add a module-level `_copy_into(head, src, state_map)` helper in
  `base_stream.py` holding the begin/guard/loop/end sequence once, with the
  `limit(0)` reasoning as its only home. Named after Java's
  `AbstractPipeline.copyInto()`, which is the same operation.
- `BaseStream._drive_to_sequential()` and `ParallelStream._drive_to()` call it
  instead of each spelling the loop out.
- `ParallelStream._drive_to()`'s `_maybe_aclosing` scope widens to cover the
  whole drive rather than only the loop, so it matches
  `_drive_to_sequential()`'s shape. Behaviour-preserving: the widened region
  only adds constructing (never starting) the composed generator on the
  already-cancelled path, and `aclose()` on a never-started async generator is a
  no-op.
- **Out of scope, deliberately:** `_drive()` keeps its two verbatim
  bridge-buffer flush blocks and its own copy of the loop. It has to `yield`
  mid-body, so it cannot call the helper, and every single-flush-site form costs
  per element on a hot path. Measured on this repo's established harness
  (Python 3.14.5, 20,000 elements, chain of 8 `.map()` ops, best of 5, three
  runs): baseline 1929/2091/1907 ns/element; async-generator closure
  3002/2932/3009 (**+50%**); sync-generator closure 2137/2123/2217 (**+10%**).
  This is the same trade `GeneratorBridgeSink`'s docstring already records
  rejecting for a `drain()` returning a fresh list. The figures are recorded in
  `design.md` and in the roadmap **Done** entry so the dedup is not re-proposed.
- No behaviour change, no public API change, no new or changed requirement.

## Capabilities

### New Capabilities

None. This is a behaviour-preserving internal refactor, so the change sets
`skip_specs: true` in its `.openspec.yaml` — the same treatment as
`split-ops-into-ops-module` and `collapse-collector-sink-duplication`.

### Modified Capabilities

None. `sink-protocol` and `pipeline-composition` state the begin/accept/end
contract and the cancellation semantics the drives must honour; this change
moves where that sequence is written, not what it does. Every existing
requirement holds unchanged, which is the acceptance criterion for the refactor.

## Impact

- `src/snakestream/base_stream.py` — new private `_copy_into()`;
  `_drive_to_sequential()` shrinks to the sink-wrapping plus the call.
- `src/snakestream/parallel_stream.py` — `_drive_to()` shrinks to the same
  shape; imports `_copy_into` alongside the existing `_maybe_aclosing`.
- `src/snakestream/stream.py`, `sink.py`, `ops.py`, `collector.py`,
  `terminals.py` — untouched. Every `_drive_to()` / `_drive_to_sequential()`
  call site in `stream.py` keeps its current signature.
- `tests/` — no test should need editing; the existing suite is the regression
  gate. `tests/test_sink.py`'s local `_drive()` double is left as-is: it drives
  a *sync* iterable and exists to exercise sinks without a stream, so it is not
  a fourth copy of the production loop.
- `README.md` — no edit. Every name involved is private and unexported, and no
  parity table entry changes.
- `roadmap.md` — item 1 moves from **Now** to **Done**, carrying the benchmark
  figures above.

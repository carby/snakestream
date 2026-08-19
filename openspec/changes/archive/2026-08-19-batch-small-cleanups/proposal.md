## Why

The Sink-chain redesign and the four follow-up changes that finished converting the pipeline to it (`introduce-op-abc`, `collapse-op-classes`, `split-ops-into-ops-module`, `convert-terminals-to-sinks`) each left small residue behind: a helper whose name no longer describes what it does, copies that nothing mutates, a hot-path allocation, a redundant guard, two pass-through constructors, a hand-rolled version of an existing helper, two identical method bodies, and one type alias that was explicitly scoped out of the last typing fix. Individually each is trivial; collectively they are why a code-quality read of `src/` after the redesign felt messy. This is roadmap item 1, and it goes first because every remaining roadmap item moves code in the same files — doing it now keeps those items' line references from going stale a third time.

## What Changes

Ten cleanups, batched. Nine are behavior-neutral; one fixes a real over-pull.

**Behavior fix**

- The driving loops (`BaseStream._drive()`, `BaseStream._drive_to_sequential()`) query `cancellation_requested()` only *after* an `accept()`, never before the first pull. An op that is already cancelled when the loop starts therefore consumes and discards one source element and runs every upstream operation's side effects on it. Verified against the tree: `Stream.of([1, 2, 3]).peek(seen.append).limit(0).to_array()` returns `[]` but leaves `seen == [1]`. Fixed by checking cancellation once after `begin()`, before the first pull.

  **Correction to the roadmap's framing.** Item 1 states this as "a satisfied `limit()` still pulls one extra element from the source". That is not what the tree does: `_LimitSink` sets `_cancelled` inside the `accept()` that fills the last slot, so the loop's post-`accept()` check already breaks without an extra pull. The only reachable over-pull is the pre-settled case above — `limit(0)`, or any op cancelled before the first element. The fix is smaller than the roadmap implies but is a genuine defect, and it is the one entry in this batch with observable behavior.

**Renames and deletions**

- `BaseStream._sequential()` (`base_stream.py:67`) does no sequential execution — it links a list of ops onto a terminal sink — and never touches `self`. Renamed to `_wrap_sink()` (Java's `AbstractPipeline.wrapSink()`, which is exactly this operation) and moved to module level.
- `_compose()` copies the chain with `self._chain[:]` (`base_stream.py:120`) and `ParallelStream._parallel()` copies again per branch (`parallel_stream.py:43`), but `_drive()` never mutates it and `_derive()` already builds a fresh list. Both copies removed.
- `Stream.to_array()` (`stream.py:177-179`) calls `_check_not_consumed()` and then `collect()`, which checks again. The redundant call is removed.
- `Stream.__init__` (`stream.py:62`) and `ParallelStream.__init__` (`parallel_stream.py:28`) are pure `super().__init__(...)` pass-throughs. Both deleted.

**Deduplication**

- `GeneratorBridgeSink.drain()` (`sink.py:175`) allocates a fresh list on every call, and both driving loops call it once per element. Reworked to drain in place, so the per-element path allocates nothing.
- `collector.to_generator()` (`collector.py:28-35`) hand-rolls the same "close it only if it has `aclose()`" branch that `_maybe_aclosing` (`base_stream.py:31`) exists for. Replaced with `_maybe_aclosing`.
- `BaseStream.sequential()` and `BaseStream.parallel()` (`base_stream.py:122-140`) are identical five-line bodies differing only in the class they construct. Factored onto one private helper.

**Typing**

- `Accumulator` (`type.py:24`) is `Callable[[T, T | R], T | R]` with no `Awaitable` in its return, but `_ReduceSink.accept()` awaits it and `tests/test_callable_dispatch.py` covers async accumulators. Widened to include `Awaitable[T | R]`. `fix-type-py-callable-alias-defects` scoped the terminal aliases out explicitly, which is why this one was never fixed. Additive to the union, so no previously-valid usage is affected.

No public API changes and no README edit: every name touched is private except `Accumulator`, whose widening is additive and whose README appearance is only the alias name in `reduce()`'s parity-table row.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sink-protocol`: the driving-loop cancellation requirement gains the pre-first-pull check — a loop SHALL NOT issue its first pull when the head sink already reports cancellation after `begin()`.
- `pipeline-composition`: the same no-over-pull guarantee is extended to cancellation that is already in effect before the first element; plus the three prose/scenario references to the `_sequential()` helper are re-pointed to `_wrap_sink()`.
- `stream-iterator`: one prose reference to `_sequential()` re-pointed to `_wrap_sink()`.

## Impact

- **Code**: `base_stream.py`, `sink.py`, `stream.py`, `parallel_stream.py`, `collector.py`, `type.py`.
- **Tests**: `tests/test_sequential.py:36` calls `Stream.of([])._sequential(intermediaries, sentinel)` as a method and must move to the module-level `_wrap_sink()`. New regression tests for the pre-settled-cancellation fix. Every other test in the suite is expected to pass unmodified — that is this change's primary regression signal.
- **Public API**: none. **Dependencies**: none. **Performance**: `drain()`'s per-element allocation goes away on the generator path; the rest is neutral.

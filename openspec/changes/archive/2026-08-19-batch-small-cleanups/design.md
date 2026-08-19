## Context

See `proposal.md` — Why. This is a batch of ten independent one-to-ten-line edits across six modules. There is no architecture to design; what needs deciding up front is the handful of choices where an obvious-looking edit has a non-obvious constraint behind it (a hot path, an import direction, a name that has to survive the next three roadmap items). Everything below is one of those. The edits not listed here — deleting the two pass-through `__init__`s, dropping `to_array()`'s duplicate `_check_not_consumed()`, widening `Accumulator` — have no alternatives worth recording.

Constraints that shape the whole batch:

- **The test suite is the regression signal.** 448 tests currently pass at 99% coverage. Nine of the ten edits must leave every one of them passing unmodified; the exceptions are `tests/test_sequential.py:36`, which calls the renamed helper as a method, and the new tests for the cancellation fix.
- **`accept()` and the per-element half of the driving loop are measured hot paths.** `optimize-callable-dispatch` bought 2.6x there and the rejected `add-callsite-dispatch` change was killed for giving ~32% of it back. No edit in this batch may add a Python-level call or an allocation to a per-element path.
- **CI gates on `ruff`, `ty`, and `--cov-fail-under=98` across 3.10–3.14.**

## Goals / Non-Goals

**Goals:**

- Close the ten entries in roadmap item 1, leaving `src/` in a state where the next three roadmap items are not re-pointing line references.
- Fix the pre-settled-cancellation over-pull, and pin it with tests at both the sink-protocol level and the `Stream` level.
- Keep the specs' internal-helper references accurate through the rename.

**Non-Goals:**

- Any change to `collector.py` beyond swapping `to_generator()`'s hand-rolled branch for `_maybe_aclosing` — the collector dedup is roadmap item 2 and the `Collector` redesign is item 3.
- Reworking `ParallelStream`'s per-branch `_LimitSink._cancelled` so a branch can observe another branch's cancellation. That is a real second-order over-pull (branch A pulls one element that the shared counter has already spoken for) but it is inherent to the racing design, needs shared-state cancellation to fix, and is out of scope here. Recorded in Risks.
- Benchmarking. Nothing here is expected to move the needle beyond `drain()`'s removed allocation, and the batch has no performance claim to defend.

## Decisions

### 1. `_sequential()` becomes a module-level `_wrap_sink()`

**What it is:** the function walks `reversed(intermediaries)` calling `op.link(sink)`, threading a terminal sink up through the chain. It reads `self` never.

**Name.** `_wrap_sink` is Java's own name for exactly this operation — `AbstractPipeline.wrapSink(Sink)` walks the pipeline stages in reverse calling `opWrapSink` on each. The project's convention is to prefer the Java name over an invented one, and `_link_chain`/`_build_chain` are inventions. `_sequential` has to go regardless: it names an execution mode this function has nothing to do with, and it sits three lines from `_drive_to_sequential()`, which *does* mean the execution mode.

**Module-level over `@staticmethod`.** Nothing overrides it, nothing dispatches on it, and a module-level function is the honest signature. The cost is that `tests/test_sequential.py`'s recursion test can no longer reach it through an instance; it imports `_wrap_sink` from `snakestream.base_stream` instead. That test is explicitly internals-facing (it is the one test the Sink-chain redesign already had to update for the same reason), so this is the expected kind of edit, not a regression.

**Alternative rejected:** leaving it a method and only renaming. Half the fix, and the roadmap entry calls out both halves.

### 2. Cancellation is checked once after `begin()`, before the loop

Both `_drive()` and `_drive_to_sequential()` currently read:

```
await head.begin(state_map)
async for item in src:
    await head.accept(item)
    ...
    if head.cancellation_requested():
        break
await head.end()
```

An `async for` pulls before the body runs, so a chain that is *already* cancelled at `begin()` pulls and pushes one element before anyone asks. Verified: `Stream.of([1,2,3]).peek(seen.append).limit(0).to_array()` yields `[]` with `seen == [1]`.

**The fix is a guard around the loop, not a restructure:**

```
await head.begin(state_map)
if not head.cancellation_requested():
    async for item in src:
        ...
await head.end()
```

**Why not check at the top of the loop body instead.** `async for item in src: if head.cancellation_requested(): break` is one line shorter but wrong: the pull has already happened by the time the body runs, so the wasted pull — the actual defect — survives. It would also add a `cancellation_requested()` call to every element of every stream, on a hot path, to fix a case that can only arise before the first element.

**Why not a `while True` / `__anext__()` restructure.** Checking before each pull, rather than after each accept, would be the uniform shape. It buys nothing (after the first element the two orderings are equivalent — the post-`accept()` check is exactly a pre-pull check, one iteration earlier) and costs the `async for`, which is the faster construct.

**`end()` still runs**, outside the guard, so the spec's "end() still runs after cancellation" scenario holds for a loop that pulled nothing. A `limit(0)` chain therefore still gets a full `begin()`/`end()` lifecycle.

**The guard needs a second half: `_LimitSink` must be able to report cancellation from `begin()`.** `_LimitSink._cancelled` starts `False` and is set only inside `accept()` (`ops.py:162,166,174`), so a `limit(0)` sink reports `cancellation_requested()` as `False` right after `begin()` and the loop guard on its own would never fire. `_LimitSink.begin()` therefore also settles the flag once the shared counter is resolved:

```
async def begin(self, state_map):
    await super().begin(state_map)
    self._cancelled = self._state.value >= self._max_size
```

This is once per composition, not per element, so it costs nothing on the hot path, and it makes the sink's state consistent — the invariant "`_cancelled` iff the reserved count has reached `max_size`" now holds from `begin()` rather than only from the first `accept()`. It also covers a `ParallelStream` branch built from an op whose shared counter is already full when the branch begins. `super().begin()` must run first: `StatefulSink.begin()` is what resolves `self._state`.

`accept()` is left byte-identical — the existing `if self._state.value >= self._max_size: self._cancelled = True; return` head stays, because a shared counter can fill after this sink's `begin()` and before its next `accept()`.

**`ParallelStream._drive_to()`** gets the same loop guard for consistency of the protocol, even though no terminal sink currently settles in `begin()` — `_FindSink` and `_MatchSink` settle only in `accept()`. It is two lines and it stops the next terminal sink from re-introducing the bug.

### 3. `GeneratorBridgeSink` drains in place

`drain()` returns `self._container` and rebinds a fresh `[]`, so every element in a `_drive()` loop allocates a list — including the overwhelmingly common case where the bridge holds exactly one element or none.

**Chosen shape:** keep the buffer as the sink's own list and have the driving loop yield from it and clear it, guarded on non-emptiness:

```
if bridge.buffer:
    for out in bridge.buffer:
        yield out
    bridge.buffer.clear()
```

Zero allocations, and the empty case (a `filter()` that dropped the element) costs one truth test. `list.clear()` after the yields is safe: the generator is suspended at each `yield`, and nothing can push into this bridge while it is suspended — the only thing that drives `head.accept()` is this same loop, and in `ParallelStream` each branch has its own bridge.

**Alternatives rejected.** (a) `if self._container:` inside `drain()`, returning a shared empty singleton otherwise — still allocates whenever there *is* an element, which is the common case. (b) Making `drain()` a generator — trades a list allocation for a generator-frame allocation, which is worse. (c) Yielding from `accept()` directly — that is the fully-pushed-to-terminal design the redesign explicitly scoped out.

`drain()` has one caller pattern (twice in `_drive()`, in-loop and post-`end()`), so exposing the buffer is a two-site change. It is renamed from `_container` usage to a plain `buffer` attribute on the bridge, since it is now read by the driving loop by name rather than through a method.

### 4. `to_generator()` uses `_maybe_aclosing`, which stays in `base_stream.py`

`to_generator()`'s `hasattr(composition, "aclose")` branch and `_maybe_aclosing.__aexit__`'s `hasattr(self._thing, "aclose")` are the same idea written twice, for the same reason (a source that is a bare `__anext__`-only async iterator).

**Import direction is fine:** `base_stream.py` imports `exception`, `sink`, `type` — never `collector`. `collector.py` importing from `base_stream` adds no cycle, and `parallel_stream.py` already imports `_maybe_aclosing` from there, so the precedent for it being the shared home exists.

**Alternative rejected:** moving `_maybe_aclosing` to its own module so `collector` need not reach into `base_stream`. That is a new module for one 14-line class, and the project has an explicit rule against modules that exist only as a place to put things. It stays where its main caller is.

Behavioural note: `to_generator()` currently closes only on the `hasattr` branch and duplicates the loop body on both. `_maybe_aclosing` collapses that to one loop, and closes on the same condition — identical behaviour, and `tests/test_collect.py`'s no-`aclose()`-source test pins it.

### 5. `sequential()` and `parallel()` share one helper

Both are: check not consumed, `_compose()`, construct, copy `_ordered`, mark consumed, return. Only the class differs, and each imports its class locally to dodge the cycle.

**Chosen shape:** a private `_handoff(cls)` on `BaseStream` taking the class as an argument, with the two public methods keeping their local imports and their return annotations:

```
def sequential(self) -> Stream[T]:
    from .stream import Stream
    return cast("Stream[T]", self._handoff(Stream))
```

The local import must stay in the caller — hoisting both imports into `_handoff` would make it import `parallel_stream` on a `sequential()` call.

**Alternative rejected:** one method with a boolean flag. It would read `_handoff(parallel=True)`, which is worse than passing the class, and `cast` is needed either way for `ty`.

### 6. The two chain copies go

`_compose()`'s `self._chain[:]` and `_parallel()`'s `intermediaries[:]` both defend against a mutation that does not happen: `_drive()` only iterates the list (through `_wrap_sink`), and `_derive()` already builds a fresh list with `self._chain + [op]`, so no two streams share one list object anyway. Removing them is why the `pipeline-composition` delta states the no-defensive-copy expectation explicitly — that spec's "chain is not consumed by composition" guarantee now rests on the loop's behaviour rather than on a copy hiding a violation, and the existing "chain length unaffected" scenarios are what would catch a future regression.

The roadmap names only `_compose()`'s copy. `_parallel()`'s is the same defect on the hotter path (once per branch, `PROCESSES` times per composition) and is included.

## Risks / Trade-offs

- **Ten unrelated edits in one commit makes bisection coarser.** → Tasks are ordered so the one behaviour-changing edit (the cancellation guard) is its own step with its own tests, ahead of the eight neutral ones; if something regresses, the neutral edits are verifiable by "the suite passes unmodified".
- **The cancellation guard changes observable behaviour: upstream side effects that used to fire once for a `limit(0)` chain no longer fire.** → It is the same class of fix `limit()` and the terminal sinks already got, in the direction the specs already require ("at most `n` elements SHALL be pulled" — for `n = 0`, one was). No signature or return value changes, so it is a behaviour note, not a migration-log **BREAKING** entry.
- **Removing the defensive copies is only safe while nothing mutates a chain list.** → A future op that wanted to rewrite the chain during composition would now corrupt the stream instead of a copy. The spec delta states the invariant so it is a documented contract rather than an accident, and `_derive()`'s copy-on-extend means the realistic case (two streams derived from one) is still isolated.
- **`ParallelStream`'s branches still over-pull relative to a shared `limit(n)`.** A branch whose own `_LimitSink` has not settled will pull an element that another branch's increment has already spent. → Pre-existing, unchanged by this batch, out of scope; noted here so it is not mistaken for a regression introduced by the guard.
- **`buffer.clear()` after yielding assumes nothing pushes into a suspended bridge.** → True by construction today (one driving loop per bridge, one bridge per branch), and a violation would show as dropped elements in the existing `to_list`/`iterator()`/`flat_map` coverage rather than silently.

## Migration Plan

None. No public API, signature, or return value changes; no data or config to migrate. `Accumulator`'s widening is additive to its union, so every previously-valid annotation still type-checks.

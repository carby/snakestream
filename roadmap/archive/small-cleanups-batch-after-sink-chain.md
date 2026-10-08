+++
id = "small-cleanups-batch-after-sink-chain"
title = "Landed the small-cleanups batch after the Sink-chain redesign"
filed = 2026-08-19
closed = 2026-08-19
outcome = "shipped"
+++

**Landed the small-cleanups batch**, the ten-entry residue left by the
Sink-chain redesign and its four follow-up changes. Nine entries were
behaviour-neutral; one was a real defect.

**The one behaviour change: a chain cancelled before its first element no
longer pulls one.** `BaseStream._drive()` and `_drive_to_sequential()`
queried `cancellation_requested()` only *after* an `accept()`, so a chain
already cancelled at `begin()` consumed one source element and ran every
upstream op's side effects on it. Both loops now check once after `begin()`
and skip the `async for` entirely; `end()` stays outside the guard, so the
lifecycle still completes. `ParallelStream._drive_to()` got the same guard.

**The roadmap's framing of this item was wrong and is corrected here.** It
said "a satisfied `limit()` still pulls one extra element from the source".
It did not: `_LimitSink` sets `_cancelled` inside the `accept()` that fills
the last slot, so the existing post-`accept()` check already broke without an
extra pull. The only reachable over-pull was the *pre-settled* case —
`limit(0)`, or any op cancelled before the first element. Verified before
starting: `Stream.of([1,2,3]).peek(seen.append).limit(0).to_array()` returned
`[]` but left `seen == [1]`.

**The fix needed a second half not in the original write-up.** The loop guard
alone does nothing, because `_LimitSink._cancelled` was only ever set inside
`accept()` — a `limit(0)` sink reported `False` right after `begin()`. Added
`_LimitSink.begin()`, which calls `super().begin()` (that is what resolves
`self._state`) and then settles `self._cancelled = self._state.value >=
self._max_size`. Once per composition, not per element. `accept()` was left
byte-identical, since a shared counter can still fill between one sink's
`begin()` and its next `accept()`.

**The nine neutral entries.** `BaseStream._sequential()` — which did no
sequential execution and never touched `self` — became a module-level
`_wrap_sink()`, after Java's `AbstractPipeline.wrapSink()`, which is exactly
this operation; the old name sat three lines from `_drive_to_sequential()`,
which *does* mean the execution mode. `_compose()`'s `self._chain[:]` and
`_parallel()`'s per-branch `intermediaries[:]` were dropped (nothing mutates
the chain, and `_derive()` already copies on extend). `GeneratorBridgeSink`
now exposes a plain `buffer` attribute the driving loop clears in place,
replacing a `drain()` that allocated a fresh list once per element on the
generator path — a plain attribute, not a `@property`, since the loop reads
it twice per element and a descriptor call would give back most of what the
removed allocation buys. `to_generator()` dropped its hand-rolled
`hasattr(composition, "aclose")` branch for the existing `_maybe_aclosing`
(no import cycle: `base_stream.py` never imports `collector`, and
`parallel_stream.py` already imported it from there). `sequential()`/
`parallel()`, identical but for the class they construct, were factored onto
`_handoff(cls)`, each keeping its own local import so a `sequential()` call
does not import `parallel_stream`. `Stream.__init__` and
`ParallelStream.__init__`, both pure `super().__init__` pass-throughs, were
deleted, as was `to_array()`'s duplicate `_check_not_consumed()`. And
`Accumulator` (`type.py`) was widened to
`Callable[[T, T | R], T | R | Awaitable[T | R]]` — `_ReduceSink.accept()`
awaits it and the suite already covered async accumulators, but
`fix-type-py-callable-alias-defects` had scoped the terminal aliases out.

No public API change and no README edit: every name touched is private except
`Accumulator`, whose widening is additive to its union and whose README row
names only the alias. All 448 pre-existing tests pass, with three mechanical
edits: `tests/test_sequential.py` calls the module-level `_wrap_sink()`
instead of reaching for it through an instance, and `tests/test_sink.py` and
`tests/test_op_protocol.py` assert on `bridge.buffer` where they had asserted
on `bridge.drain()`. 457 tests pass at 99% coverage — 9 new, covering
`limit(0)` on `Stream` and `ParallelStream`, that no source pull happens, the
full `begin()`/`end()` lifecycle on a chain that pulled nothing, the
protocol-level cancelled-at-`begin()` case against both the test double and
the real driving loop, and the bridge's in-place clear and buffer identity.
`sink-protocol` gained the pre-first-pull requirement; `pipeline-composition`
gained the `limit(0)` guarantee and the no-defensive-copy invariant; the
`_sequential()` references in `pipeline-composition` and `stream-iterator`
were re-pointed. See `openspec/changes/batch-small-cleanups`.

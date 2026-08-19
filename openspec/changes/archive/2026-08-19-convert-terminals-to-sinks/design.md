## Context

See proposal.md — Why. The relevant current state:

- `BaseStream._drive(chain, source, state_map)` is an `async def ... yield` generator: it links `chain` onto a `GeneratorBridgeSink`, pushes each source element into the head, then drains the bridge's buffer and yields. `_compose()` is `_drive(self._chain[:], self._stream)`.
- Every terminal in `stream.py` is `async for n in self._compose(): ...` plus a hand-inlined copy of `callable_dispatch.py`'s five-branch sync/async shape.
- `ParallelStream._compose()` is `_parallel(...)`, which builds `PROCESSES` independent `_drive(...)` generators over a lock-guarded shared source and races their `__anext__()` calls. Each branch has its own bridge and its own sink chain; only the state map is shared.
- `sink.py`'s `TerminalSink` already defines the seat: `begin()` → `_create_container()`, `accept()`, `end()` → `_finish(container)`, `result()`. `Sink.cancellation_requested()` defaults to `False` and `IntermediateSink` forwards it downstream — so a terminal reporting `True` already propagates to the head with no protocol change.

Constraints: Python 3.10–3.14; `ty` gated on 3.14; 98% coverage gate; no public API change; the existing terminal test suites are the regression signal and should pass unmodified.

## Goals / Non-Goals

**Goals:**

- Terminals push, with nothing buffered between the last intermediate sink and the terminal.
- Short-circuiting terminals participate in `cancellation_requested()`, so `limit()` and `flat_map()` stop on their behalf.
- Make the `TerminalSink` seat load-bearing — real subclasses that use `_create_container`/`_finish`/`result()` as intended, giving the **Next**-bucket `Collector` redesign a template that is not `GeneratorBridgeSink`.
- Keep the hand-inlined dispatch shape at each per-element site (the `add-callsite-dispatch` finding: abstracting it costs 32–75%). Terminal sinks carry `_is_async`/`_checked` as instance attributes, the way `_MapSink` and `_FilterSink` already do.

**Non-Goals:**

- Real per-branch pushing in `ParallelStream`. The terminal sits outside the race (see Decision 3).
- Converting collectors. `collect(collector)` stays generator-based; the `Collector` redesign is the separate **Next** item.
- Removing `GeneratorBridgeSink` or `_drive()`. Four callers genuinely need a generator.
- Any change to `sink.py`'s protocol classes beyond documentation. `TerminalSink` already supports everything needed.

## Decisions

### Decision 1: `_drive_to(terminal)` as a coroutine returning `result()`

```python
async def _drive_to(self, terminal: TerminalSink[Any]) -> Any:
    return await self._drive_to_sequential(terminal)


async def _drive_to_sequential(self, terminal: TerminalSink[Any]) -> Any:
    self._check_not_consumed()
    head = _link(self._chain, terminal)
    async with _maybe_aclosing(self._stream) as src:
        await head.begin({})
        async for item in src:
            await head.accept(item)
            if head.cancellation_requested():
                break
        await head.end()
    return terminal.result()
```

Structurally identical to `_drive()` minus the buffer/yield/drain steps. It is a plain coroutine, not a generator, so the terminal's `async for` disappears entirely.

**Why two methods.** `_drive_to()` is the dispatching form that `ParallelStream` overrides; `_drive_to_sequential()` is the never-overridden ordered form. This is the same split `_compose()` / `_drive()` already has, and it is what `for_each_ordered()` and `ParallelStream.find_first()` need — today they reach for `self._drive(self._chain[:], self._stream)` to bypass the race, which is exactly `_drive_to_sequential` in the new shape. *Alternative rejected:* a `ordered: bool` flag on one method — reads worse at every call site and hides which of the two paths a terminal takes.

**Why `_check_not_consumed()` moves inside.** Every terminal calls it first today, and two (`to_array`) call it twice. Folding it into `_drive_to_sequential` states it once. `to_array()` keeps its own check because it routes through `collect()`, not `_drive_to` — and that double check is a **Now**-bucket small-cleanups item, deliberately left alone here.

**Why `{}` for the state map.** `_drive()` already defaults to a fresh empty map for sequential drives; stateful sinks then fall back to their op's `make_shared_state()`. Nothing changes.

### Decision 2: A new `terminals.py`, mirroring `ops.py`

The eleven-ish terminal sinks go in `src/snakestream/terminals.py`, importing from `sink.py`, `callable_dispatch.py`, `sort.py` and `type.py` — the same import set `ops.py` has, and the same no-cycle argument. `stream.py`'s terminal methods become two lines each: construct the sink, `return await self._drive_to(sink)`.

*Alternative rejected:* putting them in `sink.py`. That file is the protocol; the `split-ops-into-ops-module` change already settled that concrete op/sink implementations do not belong there, and the same reasoning applies one file over. *Alternative rejected:* keeping them in `stream.py` — that file just came down from 485 to 312 lines by moving implementations out; putting eleven sink classes back in reverses it.

**Naming** follows `ops.py`: `_ReduceSink`, `_CountSink`, `_ForEachSink`, `_MatchSink`, `_MinMaxSink`, `_FindSink`, `_MutableReductionSink`. All private, none exported, so no README parity edit.

**Shape.** Most are direct `TerminalSink` subclasses:

- `_CountSink`: `_create_container` → `Counter()` (reuse `sink.py`'s existing box), `_finish` → `.value`.
- `_ReduceSink(identity, accumulator)`: `_create_container` returns the identity, or `_UNSET` for the no-identity overload, seeding from the first `accept()`. `_finish` maps a still-`_UNSET` container to `None`, which is exactly today's `return None` on the empty no-identity case.
- `_MinMaxSink(comparator, asc)`: container is `_UNSET`-seeded like `_ReduceSink`; the per-element comparison and `check_comparator_result_type` call move over verbatim from `Stream._min_max`.
- `_ForEachSink(consumer)`: no container; `_finish` returns `None`.
- `_MutableReductionSink(container, accumulator)`: the supplier is awaited once by the caller (it is a once-per-composition site where `_maybe_await` is correct and cheap), and the resulting container is handed to the sink's constructor. `_create_container` returns it.
- `_FindSink` and `_MatchSink` are the short-circuiting pair (Decision 4).

`_UNSET` currently lives in `stream.py`. It moves to `terminals.py` and `stream.py` imports it from there — `reduce()`'s overload dispatch still needs it, and `terminals.py` must not import `stream.py`.

### Decision 3: `ParallelStream` drives the terminal over the racing generator

```python
async def _drive_to(self, terminal: TerminalSink[Any]) -> Any:
    self._check_not_consumed()
    await terminal.begin({})
    async with _maybe_aclosing(self._compose()) as src:
        async for n in src:
            await terminal.accept(n)
            if terminal.cancellation_requested():
                break
    await terminal.end()
    return terminal.result()
```

The terminal sits *outside* the race, accumulating what the branches produce. Semantics are therefore byte-identical to today's parallel terminals; the bridge's buffer-and-yield cost stays in parallel mode, and the performance win is sequential-only.

*Alternative rejected:* linking all `PROCESSES` branch chains into one shared terminal sink. That is the "real" push-all-the-way answer, but it turns `begin()`/`end()` into refcounted calls (each branch would call them), makes the accumulator concurrently mutated by racing branches, and would need `_ReduceSink`/`_MinMaxSink` to define a merge across partitions — which is precisely the `combiner` work parked in **Later** behind real partitioned execution. Out of scope, and it would import a new class of race into a change whose value is elsewhere. Confirmed with the user.

*Consequence, stated deliberately:* cancellation on a `ParallelStream` reaches only the outer loop. A short-circuiting terminal stops consuming the race, but an in-flight branch's `_LimitSink` or `_FlatMapSink` does not see the terminal's cancellation — the terminal is not in those branches' chains. The `finally:` block in `_parallel()` already cancels and gathers the pending tasks, so teardown is clean; this is a missed optimization on the parallel path, not a correctness gap. The spec's parallel requirement is written to that.

### Decision 4: Short-circuiting terminals set a flag in `accept()`

`_FindSink` stores the first element and sets `self._cancelled = True`; `_MatchSink(predicate, short_circuit_on, default)` evaluates the predicate and sets `self._cancelled = True` when `bool(r) is short_circuit_on`. Both override `cancellation_requested()` to return that flag — the same shape `_LimitSink` already uses, so there is one recognizable idiom for short-circuiting in the codebase.

Both still receive `end()`, so `_finish` runs normally: `_FindSink._finish` returns the stored element or `None`; `_MatchSink._finish` returns `short_circuit_on` if it fired, else `default`. `none_match()` keeps its `not await self._match(...)` inversion at the `Stream` level.

`find_first()` and `find_any()` on `Stream` are the same sink — `Stream._compose()` is already sequential, which is why they have identical bodies today. `ParallelStream.find_first()` keeps its `is_ordered()` branch, but the ordered arm becomes `self._drive_to_sequential(_FindSink())` and the unordered arm still delegates to `find_any()`.

**Why this is a behavior change worth flagging.** Today `any_match` on `.flat_map(...)` keeps expanding the current inner stream after the answer is known — user-supplied mappers get called for elements nobody looks at. After this change they do not. Fewer side effects from user callables is strictly the intended behavior (it is what `limit()` was fixed for), but a user relying on `peek()` or a side-effecting mapper firing for elements past the short-circuit point would see the difference. It is not a signature or return-value change, so it is not tracked as **BREAKING** in README's migration log; it is a behavior note in the roadmap's Done entry.

### Decision 5: `for_each_ordered()` and `for_each()` share one sink

They differ only in which drive they call — `_drive_to()` vs `_drive_to_sequential()` — which is what the **Now**-bucket small-cleanups item flagged as verbatim duplication between them (and between `ParallelStream.find_first` and `Stream.find_first`). Converting the terminals dissolves both duplications for free, since the drive choice is now a one-word difference rather than a copied loop body. That item stays open for the rest of its list.

## Risks / Trade-offs

- **[No measured win, or a regression]** → The change is justified by the cancellation fix and the `Collector` seat independent of speed, but the roadmap claims a performance recovery. Tasks place a benchmark gate on the same harness the previous three changes used (Python 3.14.5, 20,000 elements, best of 5, interleaved before/after rounds), with the result recorded either way. A measured regression on the sequential path is a stop-and-reassess, as it was for `add-callsite-dispatch`.
- **[`reduce()`'s no-identity seeding changes shape]** → Today it does `identity = await anext(composed)` before the loop; a pushed sink cannot pull, so seeding moves into the first `accept()` via an `_UNSET` container. The empty-source case (`return None`) and the single-element case (return that element without calling the accumulator) both need explicit tests; they are the two places this rewrite could silently differ.
- **[Coverage gate]** → Eleven new classes with `_create_container`/`_finish` overrides add branches. `TerminalSink._finish`'s default body may become dead if every subclass overrides it; check coverage on `sink.py` and delete or keep-with-a-test rather than adding a pragma.
- **[`ty` on the terminal's result type]** → `TerminalSink.result()` is `-> Any` and `_drive_to` returns `Any`, so each terminal method's declared return type (`int`, `bool`, `T | None`) is unchecked at the boundary. Acceptable — it matches how `collect()` already types — but do not add casts that paper over a genuine mismatch.
- **[Parallel path unchanged in cost]** → Accepted and documented above; revisit only if real partitioned execution ever lands.

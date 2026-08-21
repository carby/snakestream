## Context

See `proposal.md` — Why. Four independent edits, three of them behaviour-neutral
and one a public-API shape change. The constraints that shape the approach:

- The suite is 512 tests with a 98% coverage gate. For (b), (d) and (e) the
  suite must stay green **with no test file edited** — that is the tripwire the
  `collapse-terminal-drive-loop` change established for behaviour-neutral work.
  For (a) the test edits are mechanical and mass-applied, so the tripwire is
  inverted: only `collect(to_list)` -> `collect(to_list())` may change.
- `_maybe_aclosing` is private but load-bearing: it wraps every terminal drive
  in `base_stream.py`, `to_generator`'s streaming path in `collector.py`, and
  `ParallelStream._drive_to()`. It is what lets the library accept a bare
  `__anext__`-only async iterator as a source.
- `_parallel()`'s race loop is on the per-element path in parallel mode; the
  project's convention (see the roadmap's **Done** entries) is that per-element
  changes are measured, not asserted.

## Goals / Non-Goals

**Goals:**
- One consistent shape for the public collector surface: every collector is
  obtained by calling a factory.
- Remove per-element allocation and linear scanning from the race loop without
  touching its semantics.
- `_maybe_aclosing` expressed in the stdlib primitive that already exists for it.
- No private type name reachable from a public signature.

**Non-Goals:**
- Any change to racing semantics, ordering, or cancellation behaviour in
  `_parallel()`. The `finally` block's cancel-and-gather stays exactly as is.
- Any change to the accumulator boxes themselves — (e) is a signature change
  only; `_SumBox` and friends keep their names, slots and privacy.
- Reworking `to_generator`/`StreamingCollector`, which stays the documented
  non-`Collector` exception.
- The wider executor-value redesign in the roadmap's **Later** bucket, which
  also touches `parallel_stream.py`. (b) is deliberately scoped to two lines so
  it does not collide with it.

## Decisions

### (a) `to_list` becomes a factory, rather than `to_set` becoming an instance

The inconsistency has two possible resolutions, and both are breaking. Chose
`to_list()`:

- Java's `Collectors.toList()` and `Collectors.toSet()` are both factories, and
  the project's standing preference is to stay close to the Java API.
- The rule becomes stateable without an exception: *every collector in
  `collector.py` is a factory.* The reverse resolution would produce a second
  rule — "stateless collectors are instances, stateful ones are factories" —
  requiring every caller to know which is which, and requiring a judgement call
  on each future collector.
- It breaks loudly. An unmigrated `collect(to_list)` passes a function object,
  which is not a `Collector`, so the existing `collect()` guard raises
  `StreamBuildException` naming `Collector`. No silent misbehaviour, and no
  custom error or deprecation shim needed — the same posture as the
  `Stream.concat` break in **Done**.

Rejected: keeping both forms working via a callable `Collector` subclass whose
`__call__` returns itself. Same objection as `concat`'s rejected `__await__`
shim — it makes the type permanently worse to spare a one-line migration.

The existing comment at `collector.py:123` justifying the bare instance
("a Collector holds no per-collection state, so one instance is safe to reuse")
is still true and stops being a justification for the shape. The reuse property
moves into the spec as a scenario instead: a value returned by one `to_list()`
call remains safe to pass to two collections.

Internal call sites use the called form. `grouping_by`/`partitioning_by`'s
`downstream` default becomes `to_list()` evaluated once at definition time —
a shared default instance, which the reuse property above makes safe, and which
avoids a per-call allocation on the default path. `stream.py:185`'s
`to_array()` calls `to_list()` per invocation; a module-level private instance
is available if measurement says the allocation matters, but the default is the
straightforward call.

### (b) A `{task: index}` map, and a live count instead of a per-iteration scan

Two independent fixes to the same loop:

- `while any([n is not None for n in tasks])` builds a full throwaway list per
  iteration before `any()` sees it. Replaced by a live count of non-`None`
  entries decremented where a slot is set to `None`. Dropping the brackets
  alone (`any(n is not None for n in tasks)`) removes the allocation but keeps
  an O(processes) scan; with `PROCESSES` defaulting to 4 that scan is small,
  but the counter is the same number of lines and removes it outright.
- `tasks.index(task)` is O(processes) per element and, worse, compares by
  equality on `Task` objects. A `{task: idx}` dict maintained alongside
  `tasks` gives O(1) identity-keyed lookup; the entry for a completed task is
  removed as its replacement is registered.

Alternative considered and rejected: restructuring the loop around
`asyncio.as_completed` or a queue. That is a rewrite of the race, not a
cleanup, and it belongs to the executor-value item — which explicitly notes the
race loop survives that change untouched.

Per project convention this is measured, not asserted: with `PROCESSES = 4` the
saving per element is small, and the honest possible outcome is "no measurable
difference, taken for clarity". The measurement is a task, and its result is
recorded either way rather than assumed.

### (d) `@asynccontextmanager`, with the close in a `finally`

```python
@asynccontextmanager
async def _maybe_aclosing(thing: AsyncGenerator) -> AsyncIterator[AsyncGenerator]:
    try:
        yield thing
    finally:
        if hasattr(thing, "aclose"):
            await thing.aclose()
```

The `try`/`finally` is not optional and is the one real trap here: the class
form closes in `__aexit__`, which the interpreter calls on both the normal and
the exception path. A decorator body without `finally` would throw the
exception into the generator at the `yield` and never reach the close, silently
leaking the source on every error path — including the `break`-driven
short-circuit paths (`limit`, `find_any`, `any_match`) that rely on close.
`hasattr(thing, "aclose")` stays exactly as it is; narrowing it to an
`isinstance` check against `AsyncGenerator` would reject the duck-typed sources
the guard exists for.

The name keeps its leading underscore and its call-site shape
(`async with _maybe_aclosing(x) as src`), so no call site changes — that is what
makes "green with no test edited" a meaningful check for this part.

### (e) Widen `A` to `Any` in public return annotations

`Collector` is `Generic[T, A, R]` where `A` is the accumulation container.
Public factories currently pin `A` to a private box type, so
`summing_int(...) -> Collector[Any, _SumBox, int]` forces any caller writing an
explicit annotation to import a private name. `A` becomes `Any` in every public
signature; `T` and `R`, the parameters callers actually reason about, are
unchanged. Affected: `counting`, `summing_*`, `averaging_*`, `summarizing_*`,
`min_by`/`max_by`, `reducing` (including its overloads), `to_map`,
`grouping_by`, `partitioning_by`, `mapping`, `collecting_and_then`. Private
helpers (`_summing`, `_averaging`, `_summarizing`, `_extremum`) keep their
precise box types — they are the internal contract, and that is where the type
checker should still see it.

`counting() -> Collector[Any, Counter, int]` is included even though `Counter`
lacks a leading underscore: it lives in `sink.py`, is not exported from
`__init__.py`, and is an accumulator box by any other name.

Rejected: making the boxes public. They exist so a collector can carry
per-collection dispatch state; publishing them commits the library to their
layout for no caller benefit.

## Risks / Trade-offs

- **(a) breaks the single most-used call in the README, the docs and 300-odd
  places in the tests.** → Mechanical and mass-applicable; the break is loud,
  not silent (`StreamBuildException`); a migration-log entry lands with it, per
  the pre-1.0 convention. Verify by grep after the edit that no bare
  `collect(to_list)` remains anywhere including `README.md` and `CLAUDE.md`.
- **(a) risks a silent behaviour change if `to_list()` is placed as a mutable
  default in a way that leaks state.** → It cannot: a `Collector` holds four
  callables and nothing else, and the container is created per collection by
  `supplier()`. Pinned as a spec scenario (one returned collector, two
  collections, independent results).
- **(d) risks losing close-on-exception if the `finally` is omitted.** →
  Explicit above; the branch-coverage gate plus the existing close tests are
  the check. Confirm a test actually exercises the exception path through
  `_maybe_aclosing` before landing, and add one if not — coverage of the happy
  path alone would not catch this.
- **(b) risks the dict and the counter drifting from `tasks`.** → The three
  mutation points (initial fill, replacement on a yielded result, `None` on
  `StopAsyncIteration`) are all inside one ~15-line loop; each keeps the dict
  and count updated in the same statement group that touches `tasks`.
- **(b) may show no measurable win.** → Accepted outcome, recorded as such; the
  clarity of O(1) lookup over `list.index` on `Task` objects stands on its own.
  Gate: it must not be a *regression*.
- **Four unrelated edits in one change.** → Each is independently revertable
  and lands as its own task group; nothing in (b), (d) or (e) depends on (a).

## Migration Plan

Pre-1.0 hard break, no deprecation window — the convention established by
`stream_of()` -> `Stream.of()`, the `Stream.of()` kwargs removal, the
`str`/`bytes` change and `Stream.concat`. Callers change `collect(to_list)` to
`collect(to_list())`, and `grouping_by(f, to_list)` to `grouping_by(f, to_list())`
if they passed it explicitly. Unmigrated call sites raise
`StreamBuildException` at the `collect()` call, naming `Collector`. A new
`0.3.5 -> next` migration-log entry in `README.md` records it alongside the
other entries in that release band. Rollback is a revert of the (a) task group
alone.

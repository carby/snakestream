## Context

See `proposal.md` — Why. Three details of the current state shape the approach:

1. `_drive()` (`base_stream.py:88-116`) is an **async generator**: it yields the
   bridge buffer's contents mid-loop. The other two are plain coroutines that
   push into a terminal sink and return `terminal.result()`.
2. The two terminal drives differ only in what they pass and where the source
   comes from — `_drive_to_sequential()` wraps `self._chain` around the terminal
   and drives `self._stream`; `ParallelStream._drive_to()` has no chain to link
   (each racing branch owns its own sink chain) and drives `self._compose()`,
   the composed race, with the terminal standing alone at the head.
3. This project gates structural changes on benchmarks. `add-callsite-dispatch`
   was rejected outright on them, and `GeneratorBridgeSink`'s docstring records a
   `drain()` form already rejected for allocating once per element.

## Goals / Non-Goals

**Goals:**

- One home for the begin/guard/loop/end sequence used by both terminal drives,
  and therefore one home for the `limit(0)` cancellation-guard reasoning.
- Zero measurable cost. A refactor that makes the code read better and the
  library run slower is not an improvement here.
- Zero test edits. The existing suite is the regression gate; if a test has to
  change, behaviour changed, and the change is wrong.

**Non-Goals:**

- Folding `_drive()` into the shared helper. It has to `yield` from inside the
  loop, so it cannot delegate the loop to a coroutine at all.
- Removing `_drive()`'s duplicated bridge-flush block. See Decisions.
- Touching `tests/test_sink.py`'s local `_drive()` double. It drives a sync
  iterable so sinks can be exercised without a stream; it is a test fixture that
  happens to mirror the shape, not a fourth copy of production code.
- Any change to the `_drive_to()` / `_drive_to_sequential()` split. The
  dispatching/never-overridden distinction is load-bearing (`for_each_ordered`
  and `find_first` rely on it) and stays exactly as documented.

## Decisions

### `_copy_into()` as a module-level function, not a `BaseStream` method

```python
async def _copy_into(head: Sink[Any], src: AsyncGenerator, state_map: StateMap) -> None:
    await head.begin(state_map)
    # a chain can already be cancelled before it has seen anything (limit(0));
    # pulling even one element would run every upstream op on a value nobody wants
    if not head.cancellation_requested():
        async for item in src:
            await head.accept(item)
            if head.cancellation_requested():
                break
    await head.end()
```

It touches no instance state — head, source and state map are all arguments — so
it sits beside `_wrap_sink()`, the other module-level helper of exactly this
kind. A method would additionally be overridable, which is the opposite of what
is wanted: `_drive_to()` is the designated override point, and the loop underneath
it must not become a second one.

Named after Java's `AbstractPipeline.copyInto()`, which is the same operation
(push every element of a source into a wrapped sink, honouring cancellation).
`_wrap_sink()` already cites `wrapSink()` in its docstring, so this follows the
established naming.

*Alternative considered:* a `_DriveMixin`, or a template-method
`_drive_to_sequential()` with hook methods. Both add a class to express what one
four-argument function expresses, and both re-open the override question above.

### Widening `_maybe_aclosing` in `ParallelStream._drive_to()`

Today the parallel drive opens the source *inside* the cancellation guard:

```python
await terminal.begin({})
if not terminal.cancellation_requested():
    async with _maybe_aclosing(self._compose()) as src:
        async for n in src:
            ...
await terminal.end()
```

The helper puts `begin`/`end` inside the loop's scope, so the call site becomes:

```python
async with _maybe_aclosing(self._compose()) as src:
    await _copy_into(terminal, src, {})
```

which is byte-for-byte the shape `_drive_to_sequential()` gets. The only
behavioural delta is on the already-cancelled path, where `self._compose()` is
now constructed and closed rather than never constructed. `_compose()` calls
`_parallel()`, an async generator function — calling it runs none of its body,
and `aclose()` on a never-started async generator returns without scheduling
anything. Nothing observable changes, and the two drives stop differing in a way
that has no reason behind it.

*Alternative considered:* keep the narrow scope by having `_copy_into()` take an
already-open source and calling it inside the guard — but the guard is precisely
what moved into the helper, so this would put the guard back at the call site and
defeat the change.

### `_drive()`'s duplicated flush block stays

The two four-line blocks at `base_stream.py:106-109` and `113-116` are identical.
Every form that gives a single flush site puts a per-element object on the
`iterator()` / `to_generator()` / parallel-branch path. Measured on this repo's
established harness — Python 3.14.5, 20,000 elements, chain of 8 `.map()` ops,
best of 5, three independent invocations; the baseline reproduces the
1,907 ns/element recorded by `add-callsite-dispatch`:

| Variant | ns/element (3 runs) | vs baseline |
|---|---|---|
| **Baseline** — duplicated block, as shipped | 1929, 2091, 1907 | — |
| Single site via **async-generator** closure | 3002, 2932, 3009 | **+50%** |
| Single site via **sync-generator** closure | 2137, 2123, 2217 | **+10%** |

The in-loop flush runs once per element; only the post-`end()` flush is once per
stream. So both closure forms pay per element to remove eight lines that run at
most a few hundred nanoseconds of straight-line code. This is the same trade
`GeneratorBridgeSink`'s docstring already records rejecting for a `drain()`
returning a fresh list.

The `_copy_into()` half, by contrast, is entered once per stream and measures
free: baseline 1686/1620/1741 vs. helper 1625/1654/1739 ns/element on a
`count()` terminal, same harness — within run-to-run noise, in both directions.

*Decision:* ship the helper, keep the flush blocks, and record these figures in
the roadmap **Done** entry so the flush dedup reads as decided rather than
overlooked.

## Risks / Trade-offs

- **A reader sees `_drive()` still spelling the loop out and "finishes the job"
  by routing it through `_copy_into()`.** → Impossible to do accidentally — the
  helper cannot yield, so the attempt does not compile into working code. The
  residual risk is someone re-attempting the *flush* dedup; mitigated by the
  roadmap **Done** entry carrying the figures, which is this project's
  established rejection log.
- **The widened `_maybe_aclosing` scope changes parallel cancellation
  behaviour.** → Argued above to be unobservable; task 3 pins it with an
  explicit `.parallel().limit(0)` check against existing tests, and the whole
  suite plus the 98% coverage gate must stay green with no test edited.
- **The helper costs something the `count()` benchmark does not show.** → It is
  one coroutine call per terminal drive, independent of element count, so its
  cost per element falls as the stream grows; the 20,000-element measurement is
  the pessimistic-enough case at this project's benchmark size.

## Migration Plan

None needed. Every name involved is private and unexported; there is no public
API change, no signature change at any call site in `stream.py`, and no
persisted state. Rollback is `git revert` of a single commit touching two files.

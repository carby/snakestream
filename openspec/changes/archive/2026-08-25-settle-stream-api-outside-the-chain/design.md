## Context

See proposal.md — Why. Three independent edits in `stream.py`, all outside the
op chain. What shapes the design:

- **The canonical dispatch shape is already written down.** `callable_dispatch.py`
  carries it as a comment block: `is_async = is_async_callable(fn)` plus a
  `checked` one-time `isawaitable` safety net, both hoisted inside the
  per-composition generator body so classification never leaks. `iterate()` is
  a fourth kind of site — once per *stream*, not per composition or per element
  — but it wants exactly that shape.
- **`close()`'s first-exception rule is specified and tested.** `stream-close-handling`
  says the first exception is raised, and `tests/test_close.py`'s
  `test_close_with_multiple_raising_handlers_runs_all_and_raises_first` pins it.
  The story is to stop losing the others, not to change which one propagates.
- **`Stream.__init__` already takes `close_handlers`,** and `stream-close-handling`
  specifies that constructor argument, so `concat()` needs no new mechanism —
  only to pass a list it currently leaves empty.
- **Python 3.10 is supported** (`requires-python = ">=3.10"`, CI runs 3.10–3.14),
  and `BaseException.add_note()` landed in 3.11. The coverage gate and `ty`
  run only on the 3.14 leg.

## Goals / Non-Goals

**Goals:**

- One commit per part, in the order (a) `iterate`, (b) `concat`, (c) `close`,
  so a bisect lands on one behaviour.
- `iterate()`'s dispatch is recognisably the same shape as the other 26 sites,
  not a variant — a reader who knows one knows this one.
- Keep the three edits genuinely independent: none of them should need to
  touch the intermediate-op block that story 3 rewrites next.

**Non-Goals:**

- No change to composition, execution mode, or any op in the chain.
- No change to which exception `close()` raises.
- No new exception type, and no `ExceptionGroup` (see Decisions).
- No new type alias — `Mapper[T, T]` already exists and already permits async.

## Decisions

### 1. `iterate()` dispatches `nxt` rather than rejecting an async one

`_make_iterator` becomes an `async def` generator carrying the canonical
`is_async`/`checked` locals, and `nxt`'s type moves from `Callable[[T], T]` to
the existing `Mapper[T, T]`.

*Why over rejecting a coroutine function up front* (the `flat_map`
pre-call-rejection shape, the other option the roadmap named): `flat_map`
rejects because its callable must return a `Stream` *synchronously* — an async
`flat_mapper` is structurally impossible, not merely unsupported. `nxt` has no
such constraint: it is an ordinary element-to-element mapper, and every other
mapper in the library accepts async. Rejecting would also only half-fix the
bug — `iscoroutinefunction` does not catch a callable object with an async
`__call__`, which would keep yielding un-awaited coroutines silently. Dispatch
fixes all four forms at once, which is what the `stream-iterate` spec now
requires.

*Cost, accepted:* `iterate()` today builds a **sync** generator that
`_normalize` wraps; after this it builds an async generator that `_accept`
takes directly. One fewer wrapping layer, no observable difference, and
`Stream.of(single_arg)` already routes through the same `Stream(args[0])` path
for both.

*Classification lifetime:* the locals live inside the async generator body, so
they are per generator object — i.e. per stream, since `iterate()` builds
exactly one and it is the shared source that racing branches pull from. That
satisfies `callable-dispatch`'s "classified once, does not leak" requirement
without a per-branch story, because there is only ever one `nxt` caller.

### 2. `concat()` passes `a`'s handlers then `b`'s to the constructor

`Stream(_concat(a, b), a._close_handlers + b._close_handlers)`. The `+` builds
a new list, so neither operand's list is aliased into the result — which is
what makes "registering after `concat()` does not affect the result" true, and
it is the behaviour the spec now pins rather than an accident of the
expression.

*Why not close the operands lazily as the concatenated generator exhausts each
side:* that would make `concat` the one place in the library where close
handlers fire without an explicit `close()`, contradicting the AutoClose model
(`contextlib.closing`-paired, explicit). Java's `Stream.concat` likewise
composes the two close handlers onto the result, it does not run them during
iteration.

### 3. `close()` preserves the later exceptions with `add_note()`, version-guarded

```python
if exceptions:
    first = exceptions[0]
    if sys.version_info >= (3, 11):
        for later in exceptions[1:]:
            first.add_note(f"close() also raised: {later!r}")
    raise first
```

*Why `add_note` over the alternatives:* it is the interpreter's own mechanism
for exactly this — extra detail on an exception that must keep its identity —
and it shows up in the default traceback with no caller opt-in. Attaching a
custom attribute would preserve the objects but print nothing, so the detail
would still be lost to anyone reading a traceback. An `ExceptionGroup` (or
`raise first from ExceptionGroup(...)`) would change what propagates, breaking
the specified first-exception rule and the existing test, and is 3.11+ anyway.
Manually chaining `__context__` prints all of them but fabricates a
during-handling relationship that never happened.

*Why `sys.version_info` over `hasattr(first, "add_note")`:* `ty` narrows on a
`sys.version_info` comparison, so the 3.10 leg type-checks without a cast; a
`hasattr` guard does not narrow and would need one.

*3.10, stated plainly:* on 3.10 the later exceptions are still lost. This is a
deliberate floor, not an oversight — the alternative is a backport shim for a
one-line diagnostic. The spec scenario "Interpreters without note support are
unaffected" pins that as intended behaviour rather than a latent bug.

*Coverage:* the guarded body is skipped on 3.10 and taken on 3.14, but the
coverage gate only runs on 3.14, so it is the `if` that is measured and no
pragma is needed for the taken branch. Branch coverage on 3.14 will see the
`sys.version_info` condition as constant-true; if the gate flags the untaken
edge, mark that line `# pragma: no cover` — the repo already uses that spelling
in `type.py` and `collector.py`.

## Risks / Trade-offs

- **`iterate` with an async `nxt` under `.parallel()` awaits inside the shared
  source's lock** → `race_through()` wraps the one shared iterator in
  `_guarded(shared, lock)`, so concurrent advance is already prevented and this
  does not introduce a `RuntimeError`. What is new is that `nxt`'s `await` now
  happens while a branch holds that lock, so branches cannot overlap during it
  — a slow async `nxt` serialises racing more than a sync one does. That is
  inherent to a source that is itself the async work, not a defect, and the
  affected tests (`tests/test_parallel.py:59`, `tests/test_limit.py:58`) use a
  sync `nxt` and are unchanged. **The spec scenario "Racing executor over an
  async-nxt iterate" exists to prove the combination works at all** rather than
  to measure it; no benchmark gate applies (roadmap: story 4 only).
- **Coverage of the async-`nxt` branch** → The one-time `isawaitable` safety net
  branch needs the sync-signatured-returns-a-coroutine case to be exercised, or
  the 98% gate on 3.14 may slip. The spec has a scenario for it; the tasks list
  it explicitly.
- **`concat` handler-order test could pass by accident** → With one handler per
  side, `a + b` and `b + a` are indistinguishable in effect for most assertions.
  The two-handlers-per-side ordering scenario is what actually pins it.
- **`test_close.py`'s existing multi-raise test must not be edited** → It is the
  guard that the first-exception rule survived. If the change makes that test
  need an edit, the change overreached (roadmap tripwire for this story).

## Migration Plan

No caller migration. The only call shape whose behaviour changes —
`iterate()` with an async `nxt` — previously produced un-awaited coroutine
objects, so no working code depends on the old result. README's parity table
gains a note on the `iterate` row; **no migration-log entry**, since that log
is for breaking renames and this breaks nothing that worked.

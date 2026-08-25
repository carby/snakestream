## Context

See `proposal.md` — Why. The constraints that shape the approach:

- `race_through()` builds `workers` branches over **one** source object:
  `[stream_through(chain, _guarded(source, lock), state_map) for _ in range(workers)]`.
  Every branch's `_guarded()` receives the *same* object, and the shared `lock`
  is what makes exactly one branch pull at a time. That sharing is the whole
  point of the racing mode: N branches consuming one source, not N copies.
- `_maybe_aclosing()` (`execution.py:29`) already exists and already carries the
  reasoning for the conditional close, naming "a bare async iterator
  implementing only `__anext__`" in its docstring. The fix is to *use* it at the
  one close site that does not, not to invent a mechanism.
- `_normalize()`'s `hasattr(source, "__next__")` branch is load-bearing and
  documented in `proposal.md` — Impact as out of scope. This design does not
  touch it.

## Goals / Non-Goals

**Goals:**

- One shared iterator across racing branches, obtained through the same protocol
  a sequential pass uses.
- The classification of a source stated once per side (sync, async) rather than
  in two disagreeing spellings.

**Non-Goals:**

- Re-typing `Stream._source` from `AsyncGenerator[T, None]` to a wider
  `AsyncIterable`. It is already inaccurate for a source `_accept()` passes
  through unchanged, and widening it cascades through `_compose()`, both
  executors and all four execution primitives. That is its own story; this one
  widens exactly one annotation (see Decisions).
- Any change to what the racing mode guarantees about ordering.

## Decisions

### `aiter()` is called once in `race_through()`, not inside `_guarded()`

The obvious placement — `src = aiter(source)` as the first line of `_guarded()`
— is **wrong**, and quietly so. `_guarded()` runs once per branch, so with a
source whose `__aiter__` returns a *fresh* iterator per call (exactly the
`__aiter__`-only shape this story is fixing), each of the `PROCESSES` branches
would get its own independent iterator and consume the source from the start.
`.parallel()` over a 5-element source would yield 20 elements instead of 5 — a
silent wrong answer strictly worse than today's `AttributeError`.

So `race_through()` calls `aiter(source)` once, before the list comprehension,
and hands the resulting iterator to every `_guarded()`. `_guarded()` then keeps
pulling with `__anext__()`, which is now guaranteed to exist because `aiter()`
returns an iterator or raises `TypeError`.

For an async generator — the overwhelmingly common case, since `_normalize()`
produces one — `aiter(gen) is gen`, so this adds one builtin call per
`.parallel()` consumption and changes nothing else.

*Alternative considered:* make `_accept()` return `aiter(source)`, so the whole
library only ever sees a self-iterating source. Rejected: it moves `__aiter__()`
from consumption time to `Stream()` construction time, which is an observable
change in when a user's `__aiter__` side effects run, for no benefit — the only
site in the codebase that calls `__anext__()` directly is `_guarded()`.

### The `finally` routes through `_maybe_aclosing()`, keeping close under the lock

`_guarded()`'s body becomes the `_maybe_aclosing()` context manager wrapping the
pull loop, with the close still happening under the shared lock. Each of the N
branches closing the one shared iterator on the way out is unchanged from
today's behaviour (`aclose()` on an exhausted or already-closed async generator
is a no-op); the change is only that a source with no `aclose()` is now skipped
rather than crashed on.

`_maybe_aclosing()`'s parameter annotation widens from `AsyncGenerator` to
`AsyncIterator` — it never required generator-ness, its `hasattr` check is the
entire point, and the racing path now genuinely passes it a non-generator. This
is the one annotation this story widens.

### `_accept()` keeps returning the source unchanged; only the test collapses

`isinstance(source, AsyncGenerator) or isinstance(source, AsyncIterable)` ->
`isinstance(source, AsyncIterable)`. `AsyncGenerator` is registered as a
subclass of `AsyncIterable`, so the first arm can never decide the outcome. Pure
deletion, no behaviour change, verifiable by the suite passing untouched.

### `_normalize()` gains `bytearray`/`memoryview` and one ABC check

The scalar tuple becomes `(dict, str, bytes, bytearray, memoryview)` and
`hasattr(source, "__iter__")` becomes `isinstance(source, Iterable)`, importing
`Iterable` from `collections.abc` alongside the existing imports. The two edits
land in adjacent lines of the same `if`/`elif` ladder and are one diff.

Ordering within the ladder matters and is preserved: the scalar check stays
first, so a `bytearray` never reaches the `Iterable` branch.

## Risks / Trade-offs

- **Per-branch `aiter()` would silently multiply elements** → covered above; the
  call site is `race_through()`, and the `stream-execution-model` delta's
  "Racing over a source whose `__aiter__` returns a separate iterator" scenario
  is the test that catches a regression here. That test must assert the exact
  element multiset, not just absence of `AttributeError`, or it passes against
  the broken placement.
- **The `bytearray`/`memoryview` break is silent** → results change, nothing
  raises. Mitigated only by documentation: a README migration-log entry in the
  same style as the `str`/`bytes` entry directly above it, naming
  `Stream.of(*some_bytearray)` as the migration for callers who wanted the
  spread.
- **`memoryview` is not always a buffer of bytes** → a `memoryview` cast to
  another format iterates as that format's items, so treating it as one scalar
  is a genuine judgement call rather than a pure consistency fix. Accepted
  deliberately (decision recorded 2026-08-25): a caller who wants the items can
  spread them, and having `bytes` and `memoryview(bytes)` disagree is the worse
  surprise.
- **`_normalize()` looks like it is being systematically ABC-ified** → a future
  reader may finish the job on the `__next__` branch and reintroduce the bug
  fixed at `3554cc1`. Mitigated by the comment already sitting on that branch;
  the story adds a clause to it naming why it is a `hasattr` and not
  `isinstance(source, Iterator)`.

## Migration Plan

No deploy or rollback machinery — a library release. The only migration burden
is on callers passing a `bytearray` or `memoryview` as a source, addressed by
the README migration-log entry described above. Everything else in this change
either fixes a crash or is invisible.

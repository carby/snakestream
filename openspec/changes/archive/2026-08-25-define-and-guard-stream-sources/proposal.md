## Why

`.parallel()` crashes with `AttributeError` on sources the sequential path
accepts and consumes fine — any `AsyncIterable` that is not a full async
generator. `_guarded()` (`execution.py:67`) unconditionally calls
`await source.aclose()` and pulls with `source.__anext__()`, while `_accept()`
(`stream.py:73`) admits any `AsyncIterable`. That mismatch is the only crash in
the 2026-08-25 batch, and it cannot be fixed in isolation: the assumption it
violates — *what is a source, and what may the code assume about one* — is
written down at three more sites in the same two functions, in two spellings
that disagree with each other and one that disagrees with the spec's intent.

## What Changes

- **Racing accepts every source the sequential path accepts.** `_guarded()`
  takes its iterator with the `aiter()` builtin once before the loop (covering
  an `__aiter__`-only object whose `__aiter__` returns a separate generator) and
  routes its `finally` through the existing `_maybe_aclosing()` (covering an
  object with no `aclose()`), the way every other close site in the codebase
  already does. Fixes `AttributeError: 'X' object has no attribute 'aclose'` on
  `Stream(bare_async_iter).parallel()`.
- **`_accept()` asks one question instead of two.**
  `isinstance(source, AsyncGenerator) or isinstance(source, AsyncIterable)`
  collapses to `isinstance(source, AsyncIterable)` — `AsyncGenerator` is a
  subclass of `AsyncIterable`, so the first arm can never be the deciding one.
  No behaviour change.
- **`_normalize()` classifies the sync side the way `_accept()` classifies the
  async side.** `hasattr(source, "__iter__")` becomes
  `isinstance(source, Iterable)`, which is exactly equivalent. The neighbouring
  `hasattr(source, "__next__")` branch **stays a `hasattr`** and is explicitly
  out of scope — see Impact.
- **BREAKING: `bytearray` and `memoryview` become scalar sources**, joining
  `dict`/`str`/`bytes`. `Stream.of(bytearray(b"ab"))` yields one element (the
  `bytearray`) where it yields `[97, 98]` today; same for `memoryview`. A binary
  buffer is one value the way `bytes` is, and the mutable/view variants of the
  same bytes behaving differently from `bytes` is the surprise, not the
  consistency. This breaks silently — results change, nothing raises — so it
  needs a README migration-log entry alongside the `str`/`bytes` one.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-construction`: the "Scalar source normalization" requirement names
  exactly `dict`/`str`/`bytes`; it gains `bytearray` and `memoryview`, with a
  scenario for each. The "Iterable source spreading" requirement is narrowed by
  the same edit and restated so the two requirements stay consistent.
- `stream-execution-model`: an ADDED requirement stating that the set of
  accepted sources does not depend on execution mode — anything the sequential
  path consumes, the racing path consumes too. The spec today defines the
  executor protocol and which executor a terminal uses, but says nothing about
  source acceptance being mode-independent, which is exactly the gap the crash
  fell through.

## Impact

- `src/snakestream/execution.py` — `_guarded()`.
- `src/snakestream/stream.py` — `_accept()`, `_normalize()`.
- `README.md` — one new migration-log entry for the `bytearray`/`memoryview`
  break.
- `tests/` — new coverage for racing over a bare async iterator and over an
  `__aiter__`-only object, and for the two new scalar types. Existing tests
  should need no edits; a change to one outside those sites is a signal the
  work went wider than this story.

**Explicitly out of scope, recorded so it is not re-proposed as an oversight:**
converting the `hasattr(source, "__next__")` branch in `_normalize()` to
`isinstance(source, Iterator)`. It is **not** equivalent — `Iterator`'s
`__subclasshook__` requires *both* `__iter__` and `__next__`, so an object
exposing only `__next__` is neither `Iterable` nor `Iterator`. That branch
exists because of a bug fixed at `3554cc1`, and `stream-construction` requires
that object be spread ("Scenario: Iterator source exposing only `__next__`").

**No benchmark gate.** Every site here runs once per stream construction or
once per racing branch, never per element.

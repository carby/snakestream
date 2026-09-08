## Why

`Stream.__init__(self, source, close_handlers=None)` has exactly one production
caller: `Stream.concat()`. `of()`, `empty()`, `iterate()` and
`StreamBuilder.build()` pass a source alone, and `_derive()` never touches the
parameter, because `copy()` carries `_close_handlers` forward by reference.

**The parameter is a leftover, not a feature.** It was born in `0338397`
(2024-06-08) so that stage derivation could rebuild the next stage carrying
handlers forward — the line one commit before `derive-without-reinit` reads
`new_stream = type(self)(self._source, self._close_handlers)`. That was its
whole job: an internal calling convention that happened to sit in a public
signature. `derive-without-reinit` (`0d8a6b0`, 2026-08-31) replaced that call
with `copy()` and **deleted the parameter's only real caller**, which nobody
noticed because `concat()` was already holding it up — and `concat()`'s use is
borrowed rather than designed, added in `fded72c` (2026-08-25) to fix a genuine
bug where a concatenation discarded both operands' handlers, by reaching for a
hole that was already there.

No caller-facing situation was ever described for it, in this repo or in Java,
which has no such constructor at all. `derive-without-reinit`'s own proposal had
already named the shape "the signature contract, which nothing documents", and
fixed the half of the leak that broke subclassing while leaving the parameter
standing.

`make-stream-of-atomic` is what makes this worth acting on now. The parameter
was invisible while the constructor itself was; README documents `Stream(source)`
as the construction entry point, so a vestige serving one internal call site is
now part of the surface a caller reads.

The parameter is the symptom. The defect is that `concat()` sets three sibling
attributes by three different mechanisms with no principle picking between them —
handlers through the constructor, executor by direct assignment, ordering through
a `.unordered()` derive. `_close_handlers` is the only piece of stream state with
a constructor parameter, and its two siblings in the same function do without one.

See `roadmap/items/concat-inheriting-context.md`.

## What Changes

- **BREAKING**: `Stream.__init__` drops `close_handlers`. `Stream(source)` is the
  whole signature. `Stream([1, 2, 3], [handler])` raises `TypeError` — a **loud**
  break, unlike the silent one `make-stream-of-atomic` carried.
- `concat()` gains a private `_concatenate(a, b)` that folds the handler
  merge, the mode decision and the ordering derive into one named operation,
  replacing three idioms with one call.
- The concatenated stream's handler list is stated, and tested, as **its own** —
  not aliased to either operand's in either direction. The spec covers one
  direction today (registering on an operand after `concat()` does not reach the
  concatenation); the reverse is unspecified and untested.
- `on_close()` becomes the only way to give a stream close handlers, which is
  already the documented way.

Non-goals:

- No change to what `concat()` produces. Handlers, order, mode and ordering are
  all unchanged; this is about how the result is assembled, not what it is.
- No `_Stage`/state-object extraction. Rejected in the roadmap item, and the
  reason it was *not* rejected — performance — is recorded there so it is not
  re-litigated.
- No change to `_derive()`, which already solves "next stream from this stream"
  by copying.
- No widening of what `Stream(source)` accepts. That is
  `roadmap/items/spliterator-round-trip.md`, and it stays a question about the
  source *value*, not the signature.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-close-handling`: the requirement "A stream constructed with initial
  close handlers uses them" is removed and replaced by one stating that a stream
  is always constructed with no handlers and `on_close()` is the only way to
  register them. Half of the old requirement survives — `Stream(source)` starting
  empty — so the replacement keeps that scenario and drops the one exercising the
  argument.
- `stream-concat`: "The concatenated stream carries both operands' close handlers"
  keeps every guarantee it makes, but its justifying sentence cites "an ordinary
  `Stream` constructed with an explicit `close_handlers` list", a mechanism that
  will no longer exist. It is restated in terms of the concatenation owning its
  own list, and gains the missing reverse-aliasing scenario.

## Impact

**Source** — `src/snakestream/stream.py` only: the `__init__` signature and its
one assignment, the `concat()` body, and the new `_concatenate()`.

**Tests** — `tests/test_close.py::test_construct_with_initial_close_handlers`
tests the parameter itself and is deleted rather than migrated. Three subclasses
in `tests/test_execution_model.py` that declare `__init__(self, source,
close_handlers=None)` and pass both up to `super().__init__()` get simpler; they
exist to prove `derive-without-reinit` freed subclass `__init__` signatures, and
that freedom is untouched. One test is added for the reverse aliasing direction.

**Docs** — README's `Building a stream from a source` section (the signature is
quoted there as of `make-stream-of-atomic`), and a Migration entry for the loud
break.

**Specs** — two deltas, plus a direct edit to `stream-close-handling`'s
`## Purpose`, which names "an explicit `close_handlers` argument" and is not
reachable through a delta.

**Not affected**: `pipeline-immutability`. `_concatenate()` mutates a stream that
was constructed inside `concat()` and never handed to a caller, so the
derive-and-consume rule has nothing to say about it.

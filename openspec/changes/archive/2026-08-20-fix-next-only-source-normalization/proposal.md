## Why

`_normalize()` (`base_stream.py:18`) admits a source on `hasattr(source, "__iter__") or hasattr(source, "__next__")`, but its body is `for i in source`, which requires `__iter__`. A sync iterator that implements only `__next__` therefore passes the guard and then dies with `TypeError: 'X' object is not iterable` instead of streaming — confirmed by direct repro on 2026-08-20. The branch is dead as written: no source can reach it via `__next__` alone and survive.

Both the README ("Create a stream from a List, Generator, AsyncGenerator, Iterator, AsyncIterator or just an object") and the existing `stream-construction` spec ("any other object exposing `__iter__` or `__next__` ... custom iterators") already promise this works, and the async side of the same question is already settled in favour of support — `_maybe_aclosing`'s docstring exists specifically to accommodate "a bare async iterator implementing only `__anext__`". So the fix is to make the sync side match: drive `__next__`-only sources with `next()` rather than narrowing the advertised source set.

## What Changes

- `_normalize()` drives a source that has `__next__` but no `__iter__` by calling `next(source)` in a loop until `StopIteration`, yielding each value. Sources with `__iter__` keep the existing `for i in source` path unchanged.
- No public API change, no signature change, no breaking change. Sources that work today keep working identically; a source that raised `TypeError` today now streams.
- Add test coverage for a `__next__`-only sync source, which no test exercises today — including that it composes through intermediate ops and that an empty `__next__`-only source yields an empty stream.
- No README edit needed: README line 57 already advertises `Iterator` support, and this change makes that claim true rather than changing it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-construction`: the "Iterable source spreading" requirement already covers objects exposing `__iter__` **or** `__next__`, but has no scenario pinning the `__next__`-only case — the gap that let the implementation diverge from the spec unnoticed. Add explicit scenarios for a `__next__`-only source and for an exhausted/empty one.

## Impact

- **Code**: `src/snakestream/base_stream.py` — `_normalize()` only. Nothing else reads or branches on the source shape; `_accept()` handles the async side and is untouched.
- **Tests**: a new sync-iterator source test (new file or added to an existing construction test module), covering a `__next__`-only source standalone, through a chain, and empty.
- **APIs**: none. `Stream.of()` and `Stream()` signatures and semantics are unchanged for every source that works today.
- **Dependencies**: none.
- **Coverage**: the branch is currently unreachable-in-practice; the new tests bring it under the branch-coverage gate rather than leaving it as untested surface.

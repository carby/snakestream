## Why

`Stream.of()` (`stream.py:36-59`) branches on dict vs. list vs. multiple positional args vs. kwargs into one `source` list, but tracing the logic shows the dict/list special-casing is dead complexity: `Stream(source[0])` for a single-element `source` list always produces the same result as passing that element to `Stream()` directly, since `base_stream._normalize()` already re-spreads lists/dicts on its own. The branching adds confusion without changing behavior. Separately, `_normalize()` (`base_stream.py:15`) treats any `__iter__`-having object as a sequence, so `Stream.of("abc")` silently yields `['a', 'b', 'c']` and `Stream.of(b"ab")` yields `[97, 98]` instead of one scalar element — surprising for callers used to strings/bytes being atomic values.

## What Changes

- Simplify `Stream.of(*args, **kwargs)` to `Stream.of(*args)`: single positional arg is passed straight through to `Stream()` (letting `_normalize()` decide how to treat it); multiple positional args become one element each. No behavior change for existing list/dict/generator/multi-arg call sites — verified against all existing `test_of.py` cases.
- **BREAKING**: Remove `**kwargs` support from `Stream.of()`. `Stream.of(a=1, b=2)` currently produces `[("a", 1), ("b", 2)]`; this is non-Java-idiomatic, undiscoverable, and has no real use case over `Stream.of(*some_dict.items())`. Calling `Stream.of()` with keyword arguments will now raise `TypeError` from Python's own argument binding.
- **BREAKING**: Treat `str` and `bytes` as scalar values in `_normalize()` (`base_stream.py`), alongside the existing `dict` special-case, instead of spreading them character-by-character / byte-by-byte. `Stream.of("abc")` now yields a single element `"abc"`; `Stream.of(b"ab")` now yields a single element `b"ab"`.

## Capabilities

### New Capabilities
- `stream-construction`: How `Stream.of()` and the underlying `_normalize()` source-detection interpret positional arguments (scalars, dicts, str/bytes, lists, generators, iterators) into a stream's elements.

### Modified Capabilities
(none — no existing spec covers this behavior yet)

## Impact

- `src/snakestream/stream.py`: `Stream.of()` body simplified from ~20 lines to ~4.
- `src/snakestream/base_stream.py`: `_normalize()` gains `str`/`bytes` to its scalar special-case alongside `dict`.
- `tests/test_of.py`: kwargs-related tests removed; new tests added for str/bytes scalar behavior.
- `README.md`: update `of()` signature row and add two entries to the pre-1.0 migration log per `CLAUDE.md`.
- `roadmap.md`: move this item from **Now** to **Done** once implemented.

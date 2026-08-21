## Why

`Stream.concat(a, b)` is declared `async def` but its body only constructs
`Stream(_concat(a, b))` — it never awaits anything. The `async` is pure
ceremony: it forces every caller to write `await Stream.concat(a, b)` (and to
be inside a coroutine to call it at all), which is out of line with every other
static factory on `Stream` (`of()`, `empty()`, `builder()`, `iterate()`, all
plain `def`) and out of line with Java, where `Stream.concat` is an ordinary
static method. Concatenation is lazy by construction — `_concat` is an async
generator, so calling it does no work — which is exactly why there is nothing
for the `await` to wait on.

Taking it now: it is mechanical, independent of every other roadmap item, and
the longer the awaitable signature ships the more call sites a later fix
breaks.

## What Changes

- **BREAKING**: `Stream.concat(a, b)` becomes a plain `def` returning
  `Stream[T]` instead of an `async def` returning a coroutine that resolves to
  `Stream[T]`. Callers must drop the `await`: `await Stream.concat(a, b)`
  becomes `Stream.concat(a, b)`. Existing `await` call sites break loudly at
  runtime (`TypeError: object Stream can't be used in 'await' expression`),
  not silently.
- The returned stream's contents, laziness, and ordering are unchanged: all of
  `a`'s elements, in order, followed by all of `b`'s, each side composed
  through its own chain and pulled on demand.
- A migration-log entry is added to README alongside the other pre-1.0
  breaking renames (`stream_of()` -> `Stream.of()`, the `Stream.of()` kwargs
  removal, the `str`/`bytes` spreading change).
- No change to `_concat` itself, to when either input stream's chain is
  composed, or to the fact that `concat` obtains its generators through the
  generator bridge.

## Capabilities

### New Capabilities
- `stream-concat`: `Stream.concat(a, b)`'s call shape (a plain static factory,
  not a coroutine function) and the contents, ordering, and laziness of the
  concatenated stream it returns. No existing spec covers `concat`'s own
  behaviour — `terminal-sinks` mentions it only to say it composes via the
  generator bridge, which this change does not touch.

### Modified Capabilities

_None._ `terminal-sinks`' statement that `Stream.concat()` obtains an
`AsyncGenerator` through the bridge remains true verbatim.

## Impact

- `src/snakestream/stream.py`: the `concat` staticmethod signature (one line);
  `_concat` unchanged.
- `tests/test_concat.py`: two call sites drop their `await`.
- `README.md`: migration-log entry; the API table row for `concat` already
  documents it as returning `Stream`, so no correction needed there.
- Public API surface: `Stream` is the only export, so this is a user-visible
  breaking change with no internal callers to update — `grep` finds no other
  use of `Stream.concat` in `src/`.

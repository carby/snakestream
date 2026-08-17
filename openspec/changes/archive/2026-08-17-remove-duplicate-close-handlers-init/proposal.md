## Why

`BaseStream.__init__` (`base_stream.py:33`) unconditionally sets `self._close_handlers = []`, but both concrete subclasses — `Stream.__init__` (`stream.py:103-105`) and `ParallelStream.__init__` (`parallel_stream.py:25-27`) — immediately overwrite it with `close_handlers or []` right after calling `super().__init__(source)`. The base assignment is dead code on every instantiation: no `BaseStream` subclass ever observes the value it sets before overwriting it.

## What Changes

- `BaseStream.__init__` accepts an optional `close_handlers: list[CloseHandler] | None` parameter and sets `self._close_handlers = close_handlers or []` itself, becoming the single place this initialization happens.
- `Stream.__init__` and `ParallelStream.__init__` pass their `close_handlers` argument through to `super().__init__(source, close_handlers)` instead of redundantly overwriting `self._close_handlers` after the call.
- No change to `on_close()`, `close()`, or any other observable behavior — `self._close_handlers` ends up holding the exact same value it does today for every existing call site.
- No public API change: `Stream(source, close_handlers)` and `ParallelStream(source, close_handlers)` keep their existing signatures.

## Capabilities

### New Capabilities
- `stream-close-handling`: documents the existing (unchanged) `on_close()`/`close()` contract — registering close handlers, invoking them, and propagating them across `sequential()`/`parallel()` mode switches. Not currently governed by any spec in `openspec/specs/`; adding it here since this change touches exactly the code path that constructs `self._close_handlers`, and the constructor-level dedup is easiest to verify against an explicit baseline of the behavior it must preserve.

### Modified Capabilities
(none)

## Impact

- `src/snakestream/base_stream.py` — `BaseStream.__init__` gains a `close_handlers` parameter and performs the initialization directly.
- `src/snakestream/stream.py` — `Stream.__init__` passes `close_handlers` through to `super().__init__()` instead of reassigning `self._close_handlers`.
- `src/snakestream/parallel_stream.py` — `ParallelStream.__init__` does the same.
- No test behavior changes expected; existing tests exercising `on_close()`/`close()` (and any construction with/without `close_handlers`) serve as the regression check.

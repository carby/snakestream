## Context

`BaseStream.__init__(self, source)` (`base_stream.py:30-34`) always sets `self._close_handlers = []` with no parameter to override it. Both concrete subclasses re-derive the same field right after calling `super().__init__(source)`:

```python
# stream.py
def __init__(self, source, close_handlers=None):
    super().__init__(source)
    self._close_handlers = close_handlers or []
```

```python
# parallel_stream.py
def __init__(self, source, close_handlers=None):
    super().__init__(source)
    self._close_handlers = close_handlers or []
```

The base class's own assignment is always clobbered before anything reads it — dead code, duplicated identically in both subclasses.

## Goals / Non-Goals

**Goals:**
- Single place (`BaseStream.__init__`) owns `self._close_handlers` initialization.
- No change to `Stream(source, close_handlers)` / `ParallelStream(source, close_handlers)` call signatures or observable behavior.

**Non-Goals:**
- Not touching `on_close()`/`close()` or any other `BaseStream` method.
- Not changing how `sequential()`/`parallel()` (`base_stream.py:54-68`) pass `self._close_handlers` into newly-constructed streams — they already pass it positionally and that continues to work unchanged.

## Decisions

**Add `close_handlers` as an optional parameter on `BaseStream.__init__`, defaulting to `None`.** Mirrors the exact parameter shape both subclasses already expose, so `Stream`/`ParallelStream` just forward their own parameter instead of re-implementing the `or []` fallback. Alternative considered: leave `BaseStream.__init__` untouched and just have subclasses stop calling `super().__init__(source)` before their own assignment — rejected, since that still leaves the dead assignment in the base class for any future subclass to trip over, whereas threading the parameter through removes the duplication at its source.

## Risks / Trade-offs

- [A future `BaseStream` subclass forgets to pass `close_handlers` through] → Low risk, same as today: `BaseStream.__init__` already defaults to `[]` when `close_handlers` is `None`, so a subclass that only forwards `source` still gets a valid empty list, just without whatever handlers its own constructor parameter (if any) would have carried.

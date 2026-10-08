+++
id = "duplicate-close-handlers-init"
title = "Removed duplicate `_close_handlers` initialization"
filed = 2026-08-17
closed = 2026-08-17
outcome = "shipped"
+++

Removed duplicate `_close_handlers` initialization. `BaseStream.__init__`
(`base_stream.py`) always set `self._close_handlers = []`, but both
`Stream.__init__` (`stream.py`) and `ParallelStream.__init__`
(`parallel_stream.py`) immediately overwrote it with
`close_handlers or []` right after `super().__init__(source)`, making the
base assignment dead code on every instantiation. Fixed by giving
`BaseStream.__init__` a `close_handlers` parameter and having it perform
`self._close_handlers = close_handlers or []` directly; `Stream`/
`ParallelStream` now just forward their own `close_handlers` argument via
`super().__init__(source, close_handlers)` instead of reassigning the
field themselves. No change to `on_close()`/`close()` or any observable
behavior. Added a new `stream-close-handling` spec capturing the
previously-undocumented `on_close()`/`close()`/construction/mode-switch
contract, and new tests in `tests/test_close.py` covering scenarios not
already exercised: registration order preserved across multiple
`on_close()` calls, `close()` as a no-op with zero handlers registered,
`Stream(source, [handler])` construction invoking the handler, and close
handlers surviving a `.sequential()` switch (a `.parallel()` switch was
already covered). See
`openspec/changes/remove-duplicate-close-handlers-init`.

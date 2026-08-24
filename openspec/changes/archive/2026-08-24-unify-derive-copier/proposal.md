## Why

`stream.py`'s `_derive()` (around line 99-106) and `_derive_executor()`
(around line 132-137) are line-for-line the same five-field copy —
`self._stream`, `self._close_handlers`, `self._chain`, `self._ordered`,
`self._executor` — differing only in whether `_chain` or `_executor` is the
field that varies with the call. Two copies of a copy-constructor is where a
future sixth field gets added to one body and not the other, silently
breaking the invariant that an op-derived stream and a mode-switched stream
must carry the same source, close handlers, ordering flag and consumed
semantics.

## What Changes

- Collapse `_derive()` and `_derive_executor()` into a single private copier,
  `_derive(chain, executor)`, taking both the varying fields as parameters.
- `_derive_executor()` is removed as a separate method; `parallel()` and
  `sequential()` call the unified `_derive()` directly with
  `(self._chain, RACING)` / `(self._chain, SEQUENTIAL)` respectively, while
  intermediate ops call it with `(self._chain + [op], self._executor)`.
- Preserve the existing ordering constraint: `_check_not_consumed()` runs
  before the copy, and `self._consumed = True` is set after it, so a raising
  copy leaves the receiver valid.
- Move the load-bearing part of `_derive_executor()`'s docstring — "must not
  compose", "must not assign onto self" — onto `parallel()`/`sequential()`
  rather than deleting it with the method.
- No behaviour changes anywhere: this is a private-plumbing merge only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — this is a pure private refactor. `skip_specs: true` is set in
`.openspec.yaml` since no spec-level (observable) behavior changes; only
where the copy-constructor logic lives changes.

## Impact

- `src/snakestream/stream.py`: `_derive()`, `_derive_executor()`, and their
  call sites (`parallel()`, `sequential()`, and the eight intermediate ops
  that call `_derive()`).
- No public API change, no test behaviour change expected. Per the roadmap's
  standing tripwire for this batch, the full suite must pass with **no test
  file edited**.
- Off the per-element path (chain-building/mode-switch code only, run once
  per composition), so no benchmark gate applies.

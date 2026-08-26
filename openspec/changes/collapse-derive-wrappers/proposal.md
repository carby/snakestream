## Why

`stream.py` has three private methods where one would do. `_derive(chain,
executor)` is the copier; `_extend(op)` and `_derive_executor(executor)` are
one-expression wrappers over it, each passing one axis through unchanged. Every
call site varies exactly one of the two parameters and writes the other as
noise — `self._derive([*self._chain, op], self._executor)` on one side,
`self._derive(self._chain, executor)` on the other.

This cluster has been refactored in both directions already (see the two
**Done** entries `Merged _derive() and _derive_executor() into one copier`,
2026-08-24, and `Chain-building and dead-code smalls` (a), 2026-08-25), so the
bar here is not "fewer methods" but "fewer methods *without* re-creating what
killed the 2026-08-24 merge": nine repetitions of the chain-extension rule at
the op call sites, and a fifteen-line docstring copied verbatim onto
`sequential()` and `parallel()`. Both are avoidable independently of the layer
count, which is what makes this shape new rather than a revert of a revert.

## What Changes

- **`_extend()` and `_derive_executor()` are deleted.** `_derive()` becomes the
  single derivation method, taking the `Op` to append rather than a pre-built
  chain: `_derive(op: Op | None = None) -> Stream[Any]`.
- **The chain-extension rule moves from `_extend()`'s body into `_derive()`'s.**
  It still lives in exactly one place. The nine intermediate-op call sites keep
  their current terseness — `self._derive(_MapOp(mapper))` reads the same as
  today's `self._extend(_MapOp(mapper))` — so the 2026-08-25 finding that
  motivated `_extend` is not undone.
- **`sequential()` / `parallel()` set the executor on the derived stream in
  their own bodies**, rather than passing it into the copier: derive with no
  op, assign `_executor`, return. The mode switch becomes visible at the two
  places it happens instead of being taken on the copier's word.
- **The dead `cast()` in `_derive_executor()` goes.** `_derive()` returns
  `Stream[Any]` and `Any` is assignable to `Stream[T]`, so it narrows nothing —
  the same finding the 2026-08-25 batch made for the eight intermediate ops
  ("the `cast` was never necessary"), which never reached these two methods
  because they called `_derive()` directly at the time. Verified against the
  `ty` version CI runs on the 3.14 leg. The `cast` import stays: `iterate()`
  and the 3-arg `collect()` still use it.
- **The pipeline-immutability warning is re-sited, not deleted.** Half of
  `_derive_executor()`'s docstring ("must not compose") becomes structural — the
  new `parallel()` body has nowhere a `_compose()` could hide — while the other
  half ("must not assign onto self and return self") becomes *more* load-bearing,
  because the new body contains a working template for the forbidden move: delete
  one line and `derived._executor = RACING` becomes `self._executor = RACING`.
  That warning moves onto `sequential()`, with `parallel()` pointing at it.
- **`_derive()` stays a method on `Stream`.** Explicitly considered and rejected:
  moving it to module level beside `execution.py`'s `_wrap_sink` /
  `_copy_into` / `stream_through`. See design.md.
- **Documentation is corrected in the same change.** `CLAUDE.md` names
  `_derive_executor()` (line 61) and `_extend` is named in `roadmap.md`; the
  2026-08-24 **Done** entry at `roadmap.md:1195` records the rationale *by
  method name* ("so it is `_derive_executor()`, never `self._executor = X;
  return self`"). Leaving that stale is precisely how `_derive_executor()` came
  back the first time — it was resurrected because `CLAUDE.md` described a method
  that did not exist.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Purely internal restructuring of private methods: the derived stream's
source, chain, executor, ordering characteristic and close handlers are
identical in every case, the receiver is still invalidated, and
`_check_not_consumed()` still runs before the copy with `self._consumed = True`
still after it — so a raising copy still leaves the receiver valid. No public
name, signature, result or exception changes. `.openspec.yaml` sets
`skip_specs: true`; `pipeline-immutability` and `stream-execution-model`
already state the contracts this must continue to satisfy, and the existing
suite is the regression gate.

## Impact

- `src/snakestream/stream.py` — the only source file touched. Three private
  methods become one; eleven call sites change shape (nine intermediate ops,
  `sequential()`, `parallel()`).
- No test file should need editing. That is the tripwire: `git diff -- tests/`
  must be empty at the end.
- `CLAUDE.md` (line 34, line 61) and `roadmap.md` (the stale `_derive_executor`
  / `_extend` references, including the 2026-08-24 and 2026-08-25 **Done**
  entries) are updated to describe the shape that then exists.
- Off the per-element path — this is chain-building and mode-switch code, run
  once per composition, never per element — so no benchmark gate applies.

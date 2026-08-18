## Why

Every intermediate op on `BaseStream`/`Stream` (`map`, `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) and both mode switches (`sequential()`, `parallel()`) mutate `self._chain` (or construct a new instance while leaving the old one silently still usable) and hand back a reference with no signal that the original has been extended. Passing a `Stream` into a helper function, or keeping a pre-`.map()` reference around after chaining off it, silently aliases: further use of the "old" reference actually shares and grows the same chain the new one is building, or — for `sequential()`/`parallel()` — races the same underlying source generator. This is the top item in `roadmap.md`'s Next bucket, flagged as needing an explicit decision before any code moves since either direction is a breaking change.

## What Changes

- **BREAKING**: `map()`, `filter()`, `flat_map()`, `sorted()`, `distinct()`, `peek()`, `limit()`, `skip()`, `sequential()`, and `parallel()` now return a **new** `Stream`/`ParallelStream` instance (copying `self._chain` plus the new closure) instead of mutating and returning `self`.
- **BREAKING**: once an instance has been used to build a new instance via one of the ops above, or has been terminally consumed, any further call on that same old reference to one of those ops, or to a terminal op (`collect`, `reduce`, `for_each`, `for_each_ordered`, `find_any`, `find_first`, `max`, `min`, `all_match`, `any_match`, `none_match`, `count`, `to_array`, `iterator`), raises a new `IllegalStateException`-equivalent exception (exact type/name TBD in design.md).
- Repeating a terminal operation on a `Stream`/`ParallelStream` reference that has **not** been used to build a further instance keeps today's exact behavior: the chain recomposes against the (possibly exhausted) source, yielding an empty result on re-run rather than raising — matching the existing `fix-stream-rerun-state` contract in `pipeline-composition`. This proposal does not touch that contract.
- `on_close()` and `close()` are explicitly unaffected: they are lifecycle operations, not pipeline ops, never gated by the new invalidation check, and continue to operate on a shared-by-reference `_close_handlers` list exactly as today (matching how Java itself tracks close handlers at the source stage, independent of per-op immutability).
- `Stream.of()`/`Stream.empty()`/`Stream.concat()`/`StreamBuilder.build()` are unaffected — they construct fresh instances already.

## Capabilities

### New Capabilities
- `pipeline-immutability`: defines that intermediate ops and mode switches (`sequential()`/`parallel()`) return a new stream instance rather than mutating `self`, and that using an already-extended-or-consumed reference for further pipeline-building or terminal consumption raises, while leaving `on_close()`/`close()` and repeat-terminal-op-on-an-unextended-reference behavior unchanged.

### Modified Capabilities
(none — `pipeline-composition`'s existing chain-recomposition and stateful-closure-reset requirements are unaffected and remain the authority for repeat-terminal-op behavior)

## Impact

- `src/snakestream/base_stream.py`: `sequential()`/`parallel()` gain the invalidation check; new `_consumed`-style flag and exception type.
- `src/snakestream/stream.py`: every intermediate op (`map`, `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) changes from `self._chain.append(...); return self` to constructing and returning a new `Stream` instance; every terminal op gains the invalidation check.
- `src/snakestream/parallel_stream.py`: terminal-op overrides (e.g. `find_first()`) gain the same check.
- Existing tests that chain fluently (`Stream.of(...).map(...).filter(...)...`) are unaffected — none of them hold and reuse an intermediate reference. New tests needed for: new-instance-per-op, old-reference invalidation, exemption of `on_close()`/`close()`, and non-regression of repeat-terminal-op-on-unextended-reference behavior.
- README's parity table and migration log need a new **BREAKING** entry per `CLAUDE.md` convention.

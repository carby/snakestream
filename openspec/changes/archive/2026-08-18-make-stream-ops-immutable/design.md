## Context

`BaseStream`/`Stream` currently implement intermediate ops as `self._chain.append(fn); return self`. This means a reference kept around after being chained off (passed into a helper, or simply reused after building a derived pipeline from it) silently keeps growing the same chain any derived reference is building, or — for `sequential()`/`parallel()`, which already construct a new instance — silently still shares the same underlying source generator with the new instance. See `proposal.md` for the motivating aliasing bug and roadmap context.

Two existing, deliberately-shipped contracts constrain the solution and must not be reversed:
- `pipeline-composition`'s chain-recomposition guarantee: a terminal op (`collect`, etc.) can be called more than once on the same, unextended `Stream`/`ParallelStream` reference; if the underlying source is already exhausted, the second call yields an empty result rather than raising or reusing stale state (`fix-stream-rerun-state`).
- `stream-close-handling`'s shared-by-reference `_close_handlers` list: `on_close()`/`close()` must keep working across a mode switch (`test_close_after_stream_switch`, `test_close_after_sequential_switch`), matching how Java itself tracks close handlers at the source stage rather than per pipeline stage.

## Goals / Non-Goals

**Goals:**
- Every intermediate op (`map`, `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) and both mode switches (`sequential()`, `parallel()`) return a new `Stream`/`ParallelStream` instance instead of mutating `self`.
- Using an already-superseded reference — one that was already used to build a further instance — for any further pipeline-building or terminal call raises, matching Java's `IllegalStateException`-on-reuse behavior for that specific case.
- Zero change to: repeat-terminal-op-on-an-unextended-reference behavior, `on_close()`/`close()` semantics, `_close_handlers` sharing, or `pipeline-composition`'s chain-recomposition contract.

**Non-Goals:**
- Full Java-exact single-use-only semantics (raising on *any* reuse, including a second terminal op on a never-extended reference). Rejected during exploration — it would reverse the tested `fix-stream-rerun-state` contract, which is a separate, already-decided design choice this proposal doesn't revisit.
- Real forking/teeing of the underlying source generator. `self._stream` remains single-pass; this change only fixes reference-aliasing at the chain-building level, not data-level forking.
- The Sink-chain push-based execution redesign (separate Next-bucket roadmap item). This change touches only the *return value* of each op's outer method, not the `async def fn(iterable): ...` closure bodies, so it does not collide with that future redesign.

## Decisions

### 1. A `_consumed` flag on `BaseStream`, checked by pipeline ops, set only by chain-extending ops

Add `self._consumed: bool = False` in `BaseStream.__init__`.

- **Intermediate ops** (`map`, `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) and **mode switches** (`sequential()`, `parallel()`): check `self._consumed` first (raise if set), then construct and return a new instance, then set `self._consumed = True` on the old `self`.
- **Terminal ops** (`collect`, `reduce`, `for_each`, `for_each_ordered`, `find_any`, `find_first`, `max`, `min`, `all_match`, `any_match`, `none_match`, `count`, `to_array`, `iterator`): check `self._consumed` first (raise if set) but never set it themselves.
- **`on_close()`/`close()`**: no check, no set — completely outside this mechanism, matching Java's per-source-stage close tracking.

This means a reference is only ever invalidated by being used to build a *new* instance. A `Stream` that's only ever terminally consumed (never extended further) behaves exactly as today, including the empty-on-second-run case `pipeline-composition` already covers. This was the deciding factor over stricter alternatives (see Alternatives below).

**Alternatives considered:**
- *Set `_consumed` on any terminal op too* (closer to literal Java): rejected — breaks `test_distinct_state_fresh_on_second_composition` and its `limit`/`skip` siblings, which deliberately call `collect()` twice on the same reference and assert the second call returns `[]` rather than raising.
- *Copy-on-write with no invalidation at all* (plain immutability, old reference stays silently usable forever): rejected in the explore session — it launders the aliasing bug rather than fixing it; a stale reference would still silently build a *separate*, valid pipeline sharing the same underlying single-pass source, which races exactly like today's `ParallelStream` branches do, just later and more confusingly.

### 2. New-instance construction for intermediate ops shares `self._stream` by reference, copies `self._chain`

Each intermediate op's new-instance path is: `new = Stream(self._stream, self._close_handlers); new._chain = self._chain + [new_closure]; new._ordered = self._ordered`. Unlike `sequential()`/`parallel()`, intermediate ops must **not** eagerly call `_compose()` — that would break laziness (an intermediate op must stay a zero-cost enqueue until a terminal op drives consumption). Sharing `self._stream` by reference is safe specifically *because* `self` is simultaneously marked `_consumed`, so there's exactly one live reference capable of driving that generator going forward.

Extract this into a small `BaseStream._derive(new_closure)` helper (returns the new instance, handles the `_consumed` check/set) so each of the 8 intermediate ops in `stream.py` calls one shared helper rather than duplicating the four-line dance. `sequential()`/`parallel()` keep their own shape (they already build a new instance from a *composed* source) but gain the same check-and-set calls.

### 3. New `IllegalStateException` in `exception.py`

Add `class IllegalStateException(Exception): pass` to `snakestream/exception.py`, named after Java's actual `java.lang.IllegalStateException` (thrown by real `java.util.stream.Stream` on reuse-after-operation) rather than inventing a snakestream-specific name, consistent with this project's Java-parity naming convention. Raised with a message identifying which reference/operation was reused.

### 4. Terminal ops on `ParallelStream` overrides

`ParallelStream.find_first()` (the one terminal op with a subclass-specific override) gets the same `self._consumed` check at its top, inherited flag and all — no `parallel_stream.py`-specific state needed.

## Risks / Trade-offs

- **[Risk]** Missing the check on one of the 8+ intermediate ops or one of the terminal ops silently reintroduces the aliasing bug for that one method. → **Mitigation**: route every intermediate op through the single `_derive()` helper (impossible to forget the set-before-return step); add a parametrized test asserting *every* public intermediate/terminal method raises `IllegalStateException` on a pre-consumed instance (protects against a future new op forgetting the check too).
- **[Risk]** `self._stream` being shared-by-reference between an about-to-be-invalidated `self` and the new instance is only safe as long as nothing else keeps pulling from `self` after invalidation — if some internal code path bypassed the public API and pulled from `self._stream` directly after a `_derive()` call, it would race. → **Mitigation**: audit confirms `_compose()`/`_sequential()`/`_parallel()` are the only readers of `self._stream`, and all three are terminal-op-only paths already gated by the `_consumed` check.
- **[Trade-off]** One extra `Stream`/`ParallelStream` object allocated per intermediate op call, versus zero before. Given each op already allocates an `async def fn` closure, this is a marginal cost.

## Migration Plan

Single-PR breaking change (no runtime feature flag — matches this project's stated preference for simple over gradual migrations). Steps:
1. Add `IllegalStateException` to `exception.py`.
2. Add `_consumed` flag + `_derive()` helper to `BaseStream`.
3. Convert each of the 8 intermediate ops in `stream.py` to use `_derive()`.
4. Add the check-and-set pair to `sequential()`/`parallel()` in `base_stream.py`.
5. Add the check-only guard to every terminal op in `stream.py` and to `ParallelStream.find_first()`.
6. Add regression tests (new-instance-per-op identity checks, invalidation-raises tests, exemption tests for `on_close()`/`close()`, non-regression tests for repeat-terminal-op-on-unextended-reference).
7. Update README's parity table and **BREAKING** migration log per `CLAUDE.md`.

No rollback complexity beyond a normal revert — this is a pure library-code change with no persisted state or external migration.

## Open Questions

- Exact wording of the `IllegalStateException` message(s) — deferred to implementation (tasks.md), not a design-level decision.
- Whether `Stream.concat()` (which already builds a fresh instance from two others) needs any `_consumed` interaction — current read is no, since it consumes `a`/`b` via `_compose()` internally exactly once and returns a wholly new `Stream`, but worth a explicit test rather than an assumption.

## Why

`BaseStream._sequential()` (`base_stream.py:36-49`) builds the composed pipeline by recursing once per queued intermediate-operation closure and popping from the *front* of the closure list (`intermediaries.pop(0)`) on each call. This gives O(n) Python stack depth for a chain of n intermediate ops — risking `RecursionError` on long `.map()/.filter()/...` chains — and O(n²) time overall, since `list.pop(0)` is itself O(n) and it's called n times.

## What Changes

- Rewrite `BaseStream._sequential()` as an iterative loop instead of recursion, eliminating the per-op stack frame.
- Replace the front-popping (`pop(0)`) traversal with an O(1)-per-step traversal (e.g. index-based iteration or `collections.deque.popleft()`), removing the O(n²) behavior.
- No change to the method's signature, return value, or the `state_map`/per-op state-lookup behavior it already provides — purely an internal control-flow rewrite.
- No public API change; `_compose()`, `sequential()`, `parallel()`, and every terminal operation that depends on them are unaffected in observable behavior.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `pipeline-composition`: adds a new requirement that *building* a composed pipeline (`_sequential()`/`_compose()`'s own traversal of the queued closures) SHALL NOT fail with `RecursionError` regardless of chain length. Every existing requirement in that spec — non-destructive composition, per-composition state reset for `distinct()`/`limit()`/`skip()` — is unaffected and must continue to hold unchanged.

## Impact

- `src/snakestream/base_stream.py` — `_sequential()` rewritten; `_compose()` (its only caller) is untouched.
- No changes expected to `stream.py`, `parallel_stream.py`, or any public API.
- Existing `pipeline-composition` test coverage (composition non-destructiveness, per-composition state reset for `distinct()`/`limit()`/`skip()`) should continue to pass unmodified and serves as the regression check; add a new test asserting `_sequential()` builds a long chain of closures without `RecursionError`.
- **Scope note (discovered during implementation):** this fix only removes recursion from *building* the pipeline. Each individual intermediate op in `stream.py` (`filter`, `map`, `flat_map`, `sorted`, `peek`, and the `_DistinctOp`/`_LimitOp`/`_SkipOp` classes) is implemented as `async def fn(iterable): async for i in iterable: yield ...`, so *consuming* a long chain still recurses once per chained op at the `async for`/`__anext__()` level — a separate, larger issue (a push-based execution-model redesign) tracked as a follow-up change, not fixed here.

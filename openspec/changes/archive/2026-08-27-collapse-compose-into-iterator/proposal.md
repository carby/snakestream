## Why

`Stream._compose()` no longer earns its existence. Since the executor-value
redesign it is a one-line forward to `self._executor.elements(...)`, and the
only thing separating it from the public `iterator()` is a
`_check_not_consumed()` call. That difference is not a design; it is a hole.
`_evaluate()` checks, `iterator()` checks, `_compose()` does not — and
`_compose()` is reachable from user code through `Stream.concat()` and through
a `flat_map()` mapper's return value, so an already-extended stream slips past
the pipeline-immutability contract in exactly those two positions.

Now, because the surface has shrunk to four call sites and the specs have
already drifted off the name on their own: `pipeline-composition`'s Purpose
still cites `_parallel()`, which the executor redesign deleted, and both
`pipeline-composition` and `stream-iterator` describe the same mechanism in
executor vocabulary in their requirement text while naming `_compose()` only in
asides.

## What Changes

- Delete `Stream._compose()`. Its four callers — `_concat()` (twice),
  `_FlatMapSink.accept()`, `Stream.collect()`'s `StreamingCollector` branch,
  and `Stream.iterator()` — go through `iterator()` instead, which is the same
  call plus the consumed check.
- **BREAKING (behavioural, un-specified today)**: a `Stream` that has already
  been extended now raises `IllegalStateException` when passed to
  `Stream.concat()` or returned by a `flat_map()` mapper. Previously both
  silently accepted it. A stream that was merely *consumed*, never extended, is
  unaffected — the existing "repeat terminal consumption of an unextended
  reference" requirement already protects the pattern of a mapper handing back
  the same prebuilt stream on every element.
- `_concat()` takes two `AsyncGenerator`s rather than two `Stream`s;
  `Stream.concat()` calls `a.iterator()` / `b.iterator()` itself. This is
  required for correctness, not tidiness: `_concat()` is an `async def`
  generator, so leaving the calls in its body would defer the
  `IllegalStateException` to the first pull of the concatenated stream rather
  than raising it where the user called `concat()`. It also drops `_concat()`'s
  dependency on `Stream` entirely.
- Spec prose that names `_compose()` (and the already-stale `_parallel()`)
  moves to the executor vocabulary those same specs use elsewhere. No contract
  changes in that move.
- `tests/test_compose.py` is renamed/merged — it is the last artefact carrying
  the word, and its first test calls `stream._compose()` directly.

Explicitly **not** in scope: renaming `_compose()` to `_to_generator()` or
`_elements()` (the change that prompted this one — deleting it settles the
question), the `iterator()` / `collect(to_generator)` duplication, and whether
"composition" survives as the noun for a composed generator in
`StreamingCollector`'s parameter name and in CLAUDE.md.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pipeline-immutability`: new requirement extending invalidation from the
  receiver to a `Stream` supplied to the library as an argument — passed to
  `concat()`, or returned by a `flat_map()` mapper — including that
  `concat()`'s check fires at call time, not at first pull. The existing
  requirement enumerates the receiver's own methods (`iterator` among them) and
  is silent on both positions; this states what that rule already implies.
- `pipeline-composition`: requirement and scenario text naming `Stream._compose()`
  restated over the executor's element-producing operation, including the
  no-recursion requirement that names it in a SHALL. Purpose de-staled
  (`_compose()`, `_parallel()`). No guarantee changes.
- `stream-iterator`: the "via the same `_compose()` mechanism" parenthetical in
  the first requirement dropped; the second requirement in the same spec already
  states it in the neutral wording.
- `mutable-reduction-collect`: one scenario whose THEN names
  `collector(self._compose())` restated.

## Impact

- `src/snakestream/stream.py` — `_compose()` deleted; `_concat()` signature and
  body; `Stream.concat()`; `iterator()` inlines the executor call;
  `collect()`'s `StreamingCollector` branch (now double-checks, harmlessly).
- `src/snakestream/ops.py` — `_FlatMapSink.accept()` calls the public
  `iterator()`, removing a reach into another `Stream`'s privates from a module
  that should not have one.
- `tests/` — `test_compose.py` renamed/merged; new coverage for the two
  argument positions and for the un-extended-reuse case staying green;
  `stream-concat`'s existing "constructing a concatenated stream SHALL NOT pull
  any element" scenarios must stay green, since `iterator()` composes without
  pulling.
- Public API surface: unchanged. No README migration-log entry — `_compose()`
  is private, and the two newly-raising cases were never documented as
  supported.
- No dependency, tooling or packaging impact.

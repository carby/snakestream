## Context

See proposal.md - Why. Today's four `_compose()` call sites, and what each becomes:

- `Stream.iterator()` (`stream.py:166-168`) — already checks then composes; deleting `_compose()` just inlines `self._executor.elements(self._chain, self._source)` into the body.
- `Stream.collect()`'s `StreamingCollector` branch (`stream.py:307`) — `collector(self._compose())` becomes `collector(self.iterator())`. `collect()` already calls `self._check_not_consumed()` at its own top (`stream.py:302`), so the call inside `iterator()` is a harmless second check of a flag that hasn't changed between them.
- `_FlatMapSink.accept()` (`ops.py:159`) — `self._flat_mapper(element)._compose()` becomes `self._flat_mapper(element).iterator()`, reached through `aclosing(...)` exactly as today; only the object being closed changes from a `_compose()` return to an `iterator()` return; both are the same `AsyncGenerator`.
- `_concat()` (`stream.py:96-99`) and `Stream.concat()` (`stream.py:229-231`) — `_concat()` is an `async def` generator, so a `_check_not_consumed()` failure inside its body would surface at first pull, not at the `concat()` call. Moving the `a.iterator()` / `b.iterator()` calls into `Stream.concat()` itself makes the raise synchronous with the call, and stops `_concat()` from needing to know about `Stream` at all.

## Goals / Non-Goals

**Goals:**
- Delete `_compose()` without changing any behavior except the two newly-specified raises (already-extended stream passed to `concat()` or returned by a `flat_map()` mapper).
- Make `concat()`'s new check synchronous with the call, not deferred to first pull.

**Non-Goals:**
- Renaming `_compose()` / `iterator()` internals, or resolving the `iterator()` / `collect(to_generator)` duplication — both explicitly out of scope per proposal.md.
- Changing anything about `distinct()`/`limit()`/`skip()` state handling, the racing split, or any other executor behavior — this change touches only how the pipeline is *reached*, never how it *runs*.

## Decisions

**`_concat()` takes two `AsyncGenerator`s, not two `Stream`s.** `Stream.concat()` calls `a.iterator()` and `b.iterator()` before constructing `_concat(a.iterator(), b.iterator())`, so the `IllegalStateException` from an already-extended argument raises inside `concat()`'s own call frame. Leaving the calls inside `_concat()`'s body was the alternative and is rejected for exactly that reason: an `async def` generator's body doesn't run until first pulled, so the check would fire late — a materially weaker guarantee than "raises when you call `concat()`." This also drops `_concat()`'s only dependency on `Stream`, matching Impact's note that it becomes a plain generator over two `AsyncGenerator`s.

**`_FlatMapSink` reaches the check via `iterator()`, not a duplicated inline check.** `_FlatMapSink` already imports nothing from `stream.py` beyond calling a method on the `Stream` its mapper returned; routing through the public `iterator()` keeps that surface exactly as narrow as `Stream.concat()`'s, and is what the proposal's Impact section means by "removing a reach into another `Stream`'s privates from a module that should not have one."

**No compatibility shim for `_compose()`.** It is private, has exactly four call sites, all in this repo, and grep confirms no other module or test references it by name except `tests/test_compose.py`, which the proposal already scopes for rename/merge. A deprecated alias would be dead weight from the moment it's added.

**Spec `## Purpose` text naming `_compose()`/`_parallel()` is corrected by direct edit, not by delta.** OpenSpec's delta mechanism ignores a `## Purpose` block inside a delta for an existing capability — only a new capability's delta carries one. `pipeline-composition`'s Purpose (`openspec/specs/pipeline-composition/spec.md`) is therefore corrected as an implementation task that edits the main spec file directly, at the same time the requirement deltas here are archived into it, so the file never sits in a state where its Purpose and its Requirements disagree about which mechanism composes a chain.

## Risks / Trade-offs

- **Behavioral break is real, not just specified.** [Risk] Any caller today relying on `concat()` or `flat_map()` silently accepting an already-extended stream breaks. → Mitigation: both are documented as unsupported today (proposal.md - Impact: "never documented as supported"), the check matches the contract already enforced on every other entry point, and the new tests in `tests/` pin the exact raise points.
- **Double `_check_not_consumed()` in the `collect()` → `iterator()` path.** [Risk] Looks like redundant defensive code to a future reader. → Mitigation: it's one cheap attribute check, not a new invariant; a comment at the `collect()` call site (already present: `stream.py:359`'s sibling in `to_array()`) is the right amount of explanation, not a refactor to remove one of the two calls.
- **`tests/test_compose.py` rename/merge could scatter its coverage.** [Risk] Losing track of which behaviors were pinned there. → Mitigation: tasks.md enumerates the specific assertions to carry over before the file is deleted.

## Migration Plan

Single-PR internal refactor with no external migration: delete `_compose()`, update its four call sites and `_concat()`'s signature, add the two new raise paths and their tests, correct the spec prose, retire `tests/test_compose.py`. No feature flag, no phased rollout — the change is behind no public API surface change per proposal.md - Impact.

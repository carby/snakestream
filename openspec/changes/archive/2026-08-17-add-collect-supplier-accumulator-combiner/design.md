## Context

`Stream.collect(collector)` (`stream.py`) is currently a single-arg terminal op: `collector(self._compose())`, where `collector` is a plain `async def` consumer of the composed `AsyncGenerator` (`to_list`, `to_generator` in `collector.py`). Java's `Stream` also defines a 3-arg `collect(Supplier<R>, BiConsumer<R,? super T>, BiConsumer<R,R>)` overload — mutable reduction without a `Collector` object — used for cases like `stream.collect(ArrayList::new, List::add, List::addAll)`.

Every other terminal op that folds over the stream (`reduce`, `for_each`) already drives `self._compose()` directly and dispatches sync/async user callables via `_maybe_await` (`callable_dispatch.py`). This change follows that same shape rather than introducing new machinery.

## Goals / Non-Goals

**Goals:**
- Add `collect(supplier, accumulator, combiner)` as an `@overload` sibling of the existing `collect(collector)`, matching the `reduce()` precedent (`stream.py:223-227`) for how this codebase handles same-name multi-arity terminal ops.
- Support sync and async `supplier`/`accumulator` via `_maybe_await`.
- Work identically for `Stream` and `ParallelStream` with no subclass override, again matching `reduce()`.

**Non-Goals:**
- Actually invoking `combiner` or building real independent partitions to merge. Roadmap item #4 (`reduce(identity, accumulator, combiner)`) is explicitly blocked on a not-yet-made decision about `.parallel()`/`PROCESSES` semantics; this item is listed with no such blocker specifically *because* it does not attempt to resolve that decision. `combiner` is accepted for signature parity with Java and so call sites can pass one without a `TypeError`, but it is never called — documented explicitly in the requirement and docstring, not left as a silent gap.
- Any change to `ParallelStream._parallel()`'s execution model.

## Decisions

- **Overload via arg-count dispatch, not a separate method name.** `reduce()` already establishes the precedent of one Python method name carrying multiple `@overload` signatures with one runtime body branching on which args were actually supplied (using a `_UNSET` sentinel for the optional-identity case). `collect()` follows the same pattern: `collect(collector)` (1 positional) vs. `collect(supplier, accumulator, combiner)` (3 positional). Rejected alternative: a differently-named method (e.g. `collect3` or `mutable_collect`) — rejected because it has no Java equivalent and breaks the project's Java-parity naming convention.
- **`combiner` accepted but unused, and documented as such.** Alternative considered: reject 3-arg `collect()` on `ParallelStream` or raise if `combiner` would ever matter. Rejected: `reduce(identity, accumulator)` already has identical behavior on `ParallelStream` today (folds one composed, racing-but-interleaved generator into one accumulator/container) with no special-casing, so `collect()`'s 3-arg form should stay consistent with that existing, already-shipped precedent rather than inventing new parallel-aware behavior in this change.
- **New `Supplier`/`BiConsumer` type aliases in `type.py`**, not inline `Callable[...]` annotations in `stream.py`. Matches the project's established convention (`[[memory:feedback_type_aliases]]`) that composite/callable type shapes used in public signatures live in `type.py`.

## Risks / Trade-offs

- [Risk] A caller ports Java code expecting `combiner` to matter under `.parallel()` and silently gets a result equivalent to sequential accumulation into one container, not a merge of independently-accumulated partitions. → Mitigation: explicit requirement scenario + docstring stating `combiner` is accepted for signature compatibility only and never invoked; same posture the existing `reduce()`/`.parallel()` combination already has, so this isn't a new class of surprise introduced by this change.

## Open Questions

None — scope is deliberately narrow per the Non-Goals above.

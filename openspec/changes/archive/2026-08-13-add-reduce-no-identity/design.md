## Context

`Stream.reduce(identity, accumulator)` (`stream.py:207`) is the only `reduce()` overload today: `T | R`-typed identity, loops via `self._compose()`, dispatches sync/async accumulators through `_maybe_await`. Java has three `reduce()` overloads; snakestream has the 2-arg one and the 3-arg combiner one is a separate, later roadmap item blocked on parallel-reduction semantics. This design covers only the 1-arg overload (`BinaryOperator<T> accumulator`, no identity), which the roadmap marks as unblocked and delegable to the existing 2-arg implementation.

`find_any()` (`stream.py:224`) already establishes the project's convention for "may have nothing to return": plain `T | None`, not a wrapped `Optional[T]` container type. `max()`/`min()` follow the same pattern via `_min_max`.

`type.py` is the established single home for functional-interface-style type aliases (`Predicate`, `Mapper`, `FlatMapper`, `Comparator`, `Consumer`, `Accumulator`, `CloseHandler`), each covering a composite shape reused across signatures.

## Goals / Non-Goals

**Goals:**
- Add `Stream.reduce(accumulator)` — folds over the stream, seeded by its own first pulled element, returning `T | None`.
- Reuse the existing 2-arg `reduce()`'s accumulator-dispatch logic (`_maybe_await`) rather than duplicating it.
- Match Java `Stream<T>.reduce(BinaryOperator<T>)` semantics: empty stream → empty result (`None` here), single-element stream → that element unchanged (accumulator never called), multi-element stream → left-fold starting from the first element.
- Add a `type.py` alias for the no-identity accumulator shape (`T, T -> T`, no `R`) rather than writing it inline in `stream.py`'s `@overload` signatures.

**Non-Goals:**
- The 3-arg `reduce(identity, accumulator, combiner)` overload — separate roadmap item, blocked on parallel semantics.
- Changing the existing 2-arg `reduce(identity, accumulator)` signature or behavior.
- Introducing an `Optional[T]` wrapper type — out of step with the existing `T | None` convention.

## Decisions

**Overload via a sentinel default, not a separate method name.** `reduce()` gains an optional `identity` parameter (default a private `_UNSET` sentinel, following the existing `_UNSET` precedent already used in `_min_max` for the same "no value yet" problem per the Done log). When `identity` is `_UNSET`, the method pulls the first element from `self._compose()` as the seed; if the source is empty, it returns `None` immediately without ever calling the accumulator. This keeps a single Java-parity method name (`reduce`) with two call shapes, matching how `Stream.of()` already handles single-vs-multiple-arg branching in this codebase, rather than adding a differently-named method (`reduce1`, `fold`, etc. — rejected as inconsistent with the Java-parity naming preference).

**Alternative considered:** a fully separate `async def reduce(self, accumulator)` with the 2-arg version renamed — rejected because Python doesn't support true overloading by arity, and two public methods with the same conceptual name but different call signatures is worse than one method with a sentinel-driven branch.

**Typing via `@overload` plus a new `type.py` alias.** The no-identity path returns `T | None` and takes an accumulator typed `T, T -> T` (no separate `R`), which is a different composite shape than the existing `Accumulator = Callable[[T, T | R], T | R]` alias. Per the project's convention that composite/callable type shapes live in `type.py`, add a new alias there (e.g. `BinaryOperator = Callable[[T, T], T]` or an async-aware equivalent following the existing `Predicate`/`Mapper` pattern of permitting sync-or-`Awaitable`) rather than writing the shape inline in `stream.py`'s `@overload` signatures. `stream.py` then declares:
- `@overload def reduce(self, identity: T | R, accumulator: Accumulator[T, R]) -> T | R: ...`
- `@overload def reduce(self, accumulator: BinaryOperator[T]) -> T | None: ...`

**Alternative considered:** inlining the no-identity accumulator's type directly in the `@overload` signature — rejected per project convention; `type.py` is the single home for these shapes and inlining would scatter it across call sites.

## Risks / Trade-offs

- [Single-parameter `reduce(accumulator)` call could be mistaken by callers for the identity-form with a missing arg, producing a confusing `TypeError` from the accumulator being called with a `Callable` as `identity`] → Mitigated by `@overload` type signatures giving accurate static-checker feedback, and by keeping the two call shapes structurally distinct (positional arity, matching `Stream.of()`'s existing precedent).
- [Pulling the first element to seed requires special-casing the first loop iteration inside `_compose()`'s async-for, which the existing 2-arg `reduce()` doesn't need] → Small, contained addition; covered by dedicated tests for empty/single/multi-element cases.

## Open Questions

None — the empty-stream return convention (`T | None`) is settled by precedent (`find_any`/`max`/`min`), and the delegation approach avoids duplicating accumulator-dispatch logic. The exact name for the new `type.py` alias (`BinaryOperator` vs. something else) is left to implementation time but should stay close to Java's own naming (`BinaryOperator<T>`) per the project's Java-parity naming preference.

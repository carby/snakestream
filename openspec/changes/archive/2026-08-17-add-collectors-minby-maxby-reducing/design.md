## Context

`collector.py` collectors are plain factory functions returning an
`async def _closure(composition: AsyncGenerator) -> R` — no separate
Collector class hierarchy (see `CLAUDE.md`). `Stream.min`/`max` already
implement the exact extremum-tracking loop needed for `min_by`/`max_by`, in
`Stream._min_max` (`stream.py:304`), and `Stream.reduce` already implements
the exact fold loop needed for `reducing(...)`, in `Stream.reduce`
(`stream.py:257`). Both are currently only reachable as methods bound to
`self._compose()`, not as standalone functions over an arbitrary
`AsyncGenerator`.

**Java signature fidelity.** This change must track `java.util.stream.Collectors`
exactly in arg order, overload count, and semantics:
- `static <T> Collector<T,?,Optional<T>> min_by(Comparator<? super T> comparator)`
- `static <T> Collector<T,?,Optional<T>> max_by(Comparator<? super T> comparator)`
- `static <T> Collector<T,?,Optional<T>> reducing(BinaryOperator<T> op)`
- `static <T> Collector<T,?,T> reducing(T identity, BinaryOperator<T> op)`
- `static <T,U> Collector<T,?,U> reducing(U identity, Function<? super T,? extends U> mapper, BinaryOperator<U> op)`

No fourth overload, no reordered args, no renamed params beyond Python's
snake_case convention. The one intentional departure from the literal Java
signature — `T | None` instead of `Optional[T]` — is not new to this change;
it's the pre-existing project-wide convention `Stream.min`/`max`/`find_any`/
`reduce(accumulator)` already use (per `CLAUDE.md`'s Java-parity-naming
guidance: adapt casing/idiom, not behavior). Every other aspect (tie-break
rule, empty-stream result, which overload requires which args) must match
Java's Javadoc precisely — verified by mirroring `Stream.min`/`max`/`reduce`'s
already-Java-verified behavior rather than re-deriving it.

## Goals / Non-Goals

**Goals:**
- `min_by(comparator)` / `max_by(comparator)` behave identically to
  `Stream.min`/`max` (same tie-break — first of equal elements wins — same
  `TypeError` on a bool-returning comparator, same `None` on an empty
  stream) when driven via `collect()`.
- `reducing(binary_operator)` / `reducing(identity, binary_operator)` /
  `reducing(identity, mapper, binary_operator)` match Java's three
  `reducing` overloads exactly: no-identity form returns `T | None` (`None`
  for empty, matching `Optional.empty()`), identity form always returns `T`
  (never `None`, since the identity seeds the fold), and the mapper form
  applies `mapper` to each element before folding into `U`.
- Both sync and async user callables (comparator/accumulator/mapper) work,
  via the existing `_maybe_await` dispatch helper.

**Non-Goals:**
- No changes to `Stream.min`/`max`/`reduce` themselves — those stay as-is;
  this only exposes their logic as `collect()`-compatible collectors.
- No `groupingBy`/downstream-collector composition — that's the next roadmap
  item and depends on this one, not the other way around.
- No new `type.py` aliases — `Comparator`, `BinaryOperator`, `Accumulator`,
  `Mapper` already cover every shape needed, matching Java's own reuse of
  `Comparator`/`BinaryOperator`/`Function` across these methods.

## Decisions

**Duplicate the loop bodies into `collector.py` rather than have `Stream`
delegate to the new collectors, or have the collectors call back into
`Stream`.** `Stream._min_max`/`reduce` operate on `self._compose()` (a bound
method pulling from `self._chain`), while a collector's contract is a plain
`async def fn(composition: AsyncGenerator) -> R` with no `Stream` instance in
scope. Retrofitting `_min_max`/`reduce` to accept an arbitrary
`AsyncGenerator` instead of `self._compose()` and having `Stream` pass
`self._compose()` in would touch working, tested terminal-op code for no
behavioral gain — the loop bodies are ~15 lines each and `joining`/`counting`/
`summing_*` already established the precedent of small self-contained
collector bodies over cross-module delegation. Trade-off: the extremum/fold
loop now exists in two places; acceptable since neither is expected to change
independently (both are stable, already-shipped Java-parity behavior) and
`check_comparator_result_type` is still imported from `sort.py`, not
reimplemented, so the one piece of real logic (the bool-comparator guard)
has a single source of truth.

**`min_by`/`max_by` return `T | None`, not a wrapped `Optional`.** Matches the
existing `Stream.min`/`max`/`find_any`/`reduce(accumulator)` convention
already established in `stream.py` — see the Java-fidelity note above.

**`reducing`'s three overloads use `@overload` + one runtime body with a
`_UNSET` sentinel, mirroring `Stream.reduce`.** `Stream.reduce` (`stream.py:
251-272`) already solved arg-count dispatch this way (2-arg-no-identity vs.
2-arg-with-identity, disambiguated via a private `_UNSET` sentinel); the
3-arg `(identity, mapper, binary_operator)` overload adds a third arm to the
same dispatch rather than a separate function, since Java itself defines
`reducing` as one overloaded method name with three signatures, not three
distinct method names (unlike `summing_int`/`summing_long`/`summing_double`,
which really are distinct Java method names and stayed separate functions).
Argument order in the 3-arg form is `(identity, mapper, binary_operator)`,
matching Java's `reducing(U identity, Function<T,U> mapper, BinaryOperator<U> op)`
exactly — mapper before the fold operator.

**Implementation note, discovered while implementing:** three `@overload`
stub bodies (each an unreachable `...`) pushed combined branch coverage
below the repo's 98% gate, since each stub's `def ...: ...` line registers
as a never-taken branch (`stream.py`'s existing 2-overload `reduce` has the
same shape but stayed under the threshold on its own). Fixed by adding
`# pragma: no cover` to each of the three `reducing` overload stub lines —
already a supported `exclude_lines` pattern in `pyproject.toml`, so no config
change was needed, and it's the correct fix (these lines are structurally
unreachable at runtime, not undertested).

**`max_by`/`min_by` implemented as two thin functions, not one
`_extremum(comparator, asc)` helper exposed publicly.** Mirrors
`Stream.max`/`min` themselves, which are two thin methods delegating to a
private `_min_max(comparator, asc)`. The collector versions follow the same
shape: `min_by`/`max_by` are the public factory functions, matching Java's two
distinct public static methods; any shared loop body between them is a
private helper, not public surface.

## Risks / Trade-offs

[Loop-body duplication between `Stream._min_max`/`reduce` and the new
collectors could drift if one is fixed and the other isn't] → Both loops are
short (~10-15 lines), already covered by property-based tests on the
`Stream` side (`tests/test_reduce.py`'s hypothesis test), and the new
collector tests will assert byte-for-byte equivalent behavior (same
tie-break, same empty-stream result, same `TypeError` case) against both the
`Stream` methods and Java's documented semantics — a future behavioral fix to
one is very likely to be caught by the other's test suite diverging from
expected output.

[Silently deviating from Java's exact overload arity/arg order would break
the parity contract this library is built around] → Mitigated by pinning the
exact Java signatures in this document and writing tests that assert each
overload's arg count/order/return type against Java's Javadoc, not just
against `Stream`'s existing behavior.

## Migration Plan

Purely additive — no existing call site changes, no deploy/rollback concerns
beyond a normal release.

## Open Questions

None.

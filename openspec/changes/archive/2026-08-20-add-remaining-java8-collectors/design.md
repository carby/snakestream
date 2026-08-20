## Context

`collector.py` builds every collector as a bare `Collector(supplier,
accumulator, finisher=...)` triple (see proposal.md - Why). Two existing
patterns this change reuses directly:

- `grouping_by`/`partitioning_by` already compose a caller-supplied
  `downstream: Collector` by calling `downstream.supplier`/`.accumulator`/
  `.finisher` through `_maybe_await`, and reject a non-`Collector`
  `downstream` via `_check_downstream`. `mapping` and `collecting_and_then`
  are single-key versions of that same composition, with no grouping/keying
  layer.
- `_summing`/`_averaging` already dispatch a sync-or-async `mapper` once per
  container via an `is_async`/`checked` pair on a small `__slots__` box, then
  fold into `total`/`count`. `summarizing_*` needs the same mapper dispatch
  plus running min/max, so it is a third box shape over the same dispatch
  idiom rather than new machinery.

## Goals / Non-Goals

**Goals:**
- Reuse `_check_downstream`, `_maybe_await`, and the mapper-dispatch idiom
  already established, rather than inventing new composition machinery.
- Keep `SummaryStatistics` a plain immutable data holder with no behavior of
  its own, per the roadmap item's steer.

**Non-Goals:**
- Matching Java's `IntSummaryStatistics` sentinel-int behavior on empty
  input (`Integer.MAX_VALUE`/`MIN_VALUE` for min/max) — see Decisions.
- Making `to_collection`'s container protocol pluggable beyond `add()`;
  Java's `Collection.add` is the only method `Collectors.toCollection`
  relies on, so this mirrors that exactly rather than generalizing further.

## Decisions

**`SummaryStatistics` is a `NamedTuple`, not a dataclass or a ported mutable
class.** Nothing in this library mutates a summary after it's finished — the
accumulation happens on a private box during collection, and
`SummaryStatistics` is only ever constructed once, in the finisher. A
`NamedTuple` gives immutability and structural equality (useful for the
"summarizing_long behaves identically to summarizing_int" scenario) for
free, without the boilerplate of a frozen dataclass. Rejected: porting
Java's mutable `IntSummaryStatistics` — that class exists in Java because
`Collectors.summarizingInt`'s accumulator mutates one instance in place, a
constraint this library's `Collector` doesn't share (the private box already
plays that role internally).

**Empty stream yields `min=None, max=None`, not Java's sentinel ints.**
Java's `IntSummaryStatistics` reports `Integer.MAX_VALUE` for `min` and
`Integer.MIN_VALUE` for `max` on zero elements, because Java has no numeric
"empty" value and the class is designed to keep accumulating. This library's
`min_by`/`max_by` already return `None` for an empty stream (see
`collector-min-max`), so `None` here is the established local convention,
not a new one, and avoids surfacing a Java implementation detail
(`Integer.MAX_VALUE`) that means nothing in Python's unbounded ints.

**`summarizing_int`/`summarizing_long` share one private builder,
`summarizing_double` passes a `coerce=float`.** Mirrors the existing
`_summing(mapper, seed, coerce)` split exactly: one shared function
computing count/sum/min/max/average, with the double variant coercing each
mapped value (and the zero seed) to `float` before folding, and the
int/long variants passing `coerce=None` to preserve whatever numeric type
the mapper returns.

**`mapping` and `collecting_and_then` do not introduce a shared "downstream
adapter" base.** Each is a ~10-line `Collector` construction reusing
`_check_downstream` and `_maybe_await` directly, same as
`grouping_by`/`partitioning_by` today. Two more call sites of the same
pattern don't justify extracting a third abstraction layer; if a future
downstream-adapting collector shows up, that's the point to reconsider.

**`to_collection`'s accumulator calls `container.add(element)` unconditionally
(no dispatch check).** `add` is a plain method call on a caller-supplied
object, not a user-supplied sync/async callable — there is nothing here to
classify as sync-vs-async, unlike every other collector in this module whose
accumulator wraps a mapper/comparator/predicate argument.

## Risks / Trade-offs

- [`summarizing_*`'s empty-stream `min`/`max` diverges from Java's sentinel
  ints] → Documented explicitly in the spec and in README, alongside the
  existing `min_by`/`max_by` `None` convention it matches.
- [Four new public names widen `collector.py`'s surface further] →
  Consistent with every other Java-8-parity addition tracked on the
  roadmap; no mitigation needed beyond the README parity-table update the
  proposal already scopes in.

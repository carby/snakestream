## Context

`collector.py` collectors are plain factory functions returning an
`async def _closure(composition: AsyncGenerator) -> R` — no separate
Collector class hierarchy (see `CLAUDE.md`). `to_map`/`to_set` are the first
*structural* collectors in the file (materializing into `dict`/`set`) as
opposed to the existing scalar-reduction collectors (`joining`, `counting`,
`summing_*`, `averaging_*`, `min_by`, `max_by`, `reducing`) — closer in shape
to `to_list` (`collector.py:29`), which already builds a plain Python
container by iterating the composed generator, than to any fold.

**Java signature fidelity.** This change tracks
`java.util.stream.Collectors` in arg order, overload count, and semantics:
- `static <T,K,U> Collector<T,?,Map<K,U>> toMap(Function<T,K> keyMapper, Function<T,U> valueMapper)`
- `static <T,K,U> Collector<T,?,Map<K,U>> toMap(Function<T,K> keyMapper, Function<T,U> valueMapper, BinaryOperator<U> mergeFunction)`
- `static <T> Collector<T,?,Set<T>> toSet()`

Java's `toMap` has a fourth overload, `toMap(keyMapper, valueMapper,
mergeFunction, mapSupplier)`, for choosing the backing `Map` implementation
— skipped here since Python has one general-purpose `dict`, the same reason
`to_array()`'s `toArray(generator)` overload was skipped (see roadmap
**Done**).

This is the roadmap's declared first step before `groupingBy`/
`partitioningBy`: the key/value-mapper shape and duplicate-key-merge
convention decided here are what `groupingBy`'s classifier and downstream
composition will reuse.

## Goals / Non-Goals

**Goals:**
- `to_map(key_mapper, value_mapper)` builds a `dict`, raising on a duplicate
  key — matching Java's 2-arg `toMap` throwing `IllegalStateException` on
  collision.
- `to_map(key_mapper, value_mapper, merge_function)` builds a `dict`,
  resolving a duplicate key via `merge_function(existing, new)` instead of
  raising — matching Java's 3-arg `toMap`.
- `to_set()` builds a `set` from the stream's elements — matching Java's
  `toSet()`.
- Both sync and async user callables (`key_mapper`/`value_mapper`/
  `merge_function`) work, via the existing `_maybe_await` dispatch helper.

**Non-Goals:**
- No `toMap(keyMapper, valueMapper, mergeFunction, mapSupplier)` 4-arg
  overload — no Python equivalent need, same rationale as `to_array()`
  skipping `toArray(generator)`.
- No ordering guarantee on `to_set()`'s output — Python's `set` has none,
  and Java's `toSet()` documents no guarantee either (unlike
  `Collectors.toUnmodifiableSet()` vs. `LinkedHashSet`-backed variants,
  which this project isn't tracking).
- No `groupingBy`/`partitioningBy` — that's the next roadmap item and
  depends on this one, not the other way around.
- No new `type.py` aliases — `Mapper` covers `key_mapper`/`value_mapper`'s
  `T -> R` shape and `BinaryOperator` covers `merge_function`'s `T, T -> T`
  shape, both already used elsewhere in `collector.py`.

## Decisions

**`to_map` raises the same collision error Python's own `dict` idiom would
signal loudly for, rather than inventing a custom exception type.** Java
throws `IllegalStateException` with a message naming the colliding key.
Python has no direct analogue, and this project already favors Python's
built-in exception vocabulary over inventing new types elsewhere (e.g.
`check_comparator_result_type` raises plain `TypeError`, not a custom
`ComparatorError`). Raising `ValueError(f"Duplicate key: {key!r}")` on
collision — a "the value is fine as a key but its usage here is invalid"
condition, matching `ValueError`'s standard meaning — is chosen over
`KeyError` (the wrong signal: `KeyError` means a lookup found nothing,
whereas this is the opposite, a collision on insert).

**`merge_function` is `None`-checked at call time inside the closure, not
dispatched via `@overload` arg-count sniffing.** Unlike `reducing`'s three
overloads (genuinely different return shapes needing `@overload` for static
typing), `to_map`'s two Java overloads differ only in "raise vs. merge on
collision" — a runtime branch, not a shape change. A single
`to_map(key_mapper, value_mapper, merge_function=None)` signature with a
default captures both Java overloads without `@overload` machinery,
matching how `joining()`'s three Java overloads collapsed into one function
with defaults (see `openspec/changes/archive/.../add-collector-joining`)
rather than `reducing`'s `@overload` precedent — the discriminator here
(is `merge_function` given) is a plain optional arg, not an arg-count/shape
change.

**`to_set()` takes no arguments, matching Java's zero-arg `toSet()`
exactly** — no `key`/`equality` customization, since Python's `set` already
uses `__eq__`/`__hash__` and Java's `toSet()` itself exposes no
customization hook either (unlike `toMap`, which needs mappers because a
`Map` has no other way to derive a key from an element).

**Known pre-existing gap, not addressed here:** `type.py`'s `Mapper` alias
(`Callable[[T], R | None]`) omits `Awaitable[...]`, unlike `Comparator`/
`Predicate` — a defect already tracked as roadmap **Now** item #3, out of
scope for this change. `to_map`'s `key_mapper`/`value_mapper` dispatch
through `_maybe_await` at runtime regardless, so async mappers work
correctly despite the static alias under-declaring it — the same
pre-existing mismatch every other `Mapper`-typed call site in this codebase
already has today.

## Risks / Trade-offs

[A `dict`'s key must be hashable, but `key_mapper` is untyped beyond `T ->
R`, so a `key_mapper` returning an unhashable value (e.g. a `list`) raises a
raw `TypeError` from `dict.__setitem__` with no collector-specific context]
→ Accepted as-is, matching Java's own behavior: `HashMap.put` with a
non-well-behaved key is likewise the caller's problem, not something
`Collectors.toMap` guards against. No wrapping needed.

[Silently deviating from Java's exact overload arity/arg order/collision
semantics would break the parity contract this library is built around] →
Mitigated by pinning the exact Java signatures and collision behavior in
this document and writing tests asserting both the 2-arg raise-on-collision
and 3-arg merge-on-collision paths against Java's documented `toMap`
semantics.

## Migration Plan

Purely additive — no existing call site changes, no deploy/rollback
concerns beyond a normal release.

## Open Questions

None.

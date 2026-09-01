## Why

Two of the four remaining Java 8 parity gaps queued by
`enumerate-java-8-parity-gaps` are the same gap seen twice: Java lets the
caller choose the *result container* for both `toMap` and `groupingBy`, and
neither overload exists here. `to_collection()` already ships the idea one
level down, so the shape is settled; what has never been decided is what a
caller-supplied mapping type does to the `UNORDERED` declaration these two
factories make.

Gaps 2 and 3 are taken together because they share that decision and the
mechanism that implements it, not because they are both small.

## What Changes

- **`to_map(key_mapper, value_mapper, merge_function, map_supplier)`** — the
  fourth of Java's `toMap` arguments, choosing the result container. Declared
  as a three-entry `@overload` set matching Java's three overloads exactly, so
  the four-argument form always carries a `merge_function`, as Java's does.
  There is deliberately no `to_map(key_mapper, value_mapper, map_supplier)`
  form: Java has no such overload, and inventing one would be an expansion of
  the public surface rather than parity.
- **`grouping_by(classifier, map_factory, downstream)`** — the third of Java's
  three `groupingBy` overloads, with `map_factory` in **Java's argument
  position**. The existing one- and two-argument calls are unaffected: the form
  is selected by arity, the same `@overload`-plus-`_UNSET` dispatch
  `reducing()` already uses in this module for the harder case where one
  position carries three different meanings.
- **A caller-supplied container clears `Characteristics.UNORDERED`.**
  `grouping_by(f, OrderedDict, to_set())` declares nothing, where
  `grouping_by(f, to_set())` declares `UNORDERED`. The shipped derivation rests
  on `dict` equality ignoring key insertion order, and a caller-supplied
  mapping type need not: `OrderedDict.__eq__` against another `OrderedDict` is
  order-*sensitive*, a stdlib counterexample rather than a hypothetical. The
  rule is the one `to_collection()` already follows, and the escape hatch is
  `unordered()` at the pipeline, one level up.
- Each factory calls its supplier/factory **once per collection** for a fresh
  container, awaiting it like every other user-supplied callable, and finishes
  into that container so the caller's type survives the finisher.
- Not breaking. Every existing call keeps its signature, its result and its
  characteristics.

## Capabilities

### New Capabilities

None. Both overloads extend factories that already have a capability.

### Modified Capabilities

- `collector-to-map`: adds the container-choosing overload, and states that the
  overload set is exactly Java's three — no `map_supplier` without a
  `merge_function`.
- `collector-grouping-by`: adds the three-argument overload, states that the
  form is selected by arity so the shipped two-argument call is unchanged, and
  bounds the existing `UNORDERED` derivation to the default `dict` container.

## Impact

- `src/snakestream/collectors.py`: `to_map`, `grouping_by`, `_ToMapBox`,
  `_GroupBox`, `_finish_groups`. `_finish_groups` is shared with
  `partitioning_by`, which gains no factory argument and must be unaffected.
- `README.md`: the two **Not yet implemented** rows (`to_map(key_mapper,
  value_mapper, merge_function, map_supplier)` and `grouping_by(classifier,
  map_factory, downstream)`) become implemented rows. No Migration entry —
  nothing breaks.
- `roadmap.md`: **Now** -> **Queued changes** gaps 2 and 3 close, leaving gaps 4
  and 5. The numbering stays retired per that section's own convention.
- No new dependencies, no change to `collector.py`'s protocol, no change to the
  racing executor or the delivery barrier — only to what two collectors declare
  to it.

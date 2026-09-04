## Purpose

Mapping-building collector for use with `Stream.collect()`, mirroring Java's
three `Collectors.toMap(...)` overloads. Builds a `dict` unless the
four-argument form supplies a container of its own.

## Requirements

### Requirement: `to_map(key_mapper, value_mapper)` collector factory (no merge function)
`collector.py` SHALL provide a `to_map(key_mapper, value_mapper)` form —
called with no `merge_function` — returning a collector that builds a
`dict` by applying `key_mapper` and `value_mapper` (sync or async) to each
pulled element, matching Java's `Collectors.toMap(Function keyMapper,
Function valueMapper)`.

#### Scenario: builds a dict from key/value mappers
- **WHEN** `Stream.of([1, 2, 3]).collect(to_map(lambda x: x, lambda x: x * x))` is called
- **THEN** the result is `{1: 1, 2: 4, 3: 9}`

#### Scenario: empty stream yields an empty dict
- **WHEN** `Stream.of([]).collect(to_map(lambda x: x, lambda x: x))` is called
- **THEN** the result is `{}`

#### Scenario: async key_mapper and value_mapper are both awaited
- **WHEN** `to_map(key_mapper, value_mapper)` is given an async `key_mapper` and/or an async `value_mapper`
- **THEN** the result is computed correctly, with each awaited via the same dispatch used elsewhere in the library

### Requirement: `to_map` raises `IllegalStateException` on duplicate key with no merge function
When no `merge_function` is given and `key_mapper` produces the same key
for two different elements, `to_map`'s collector SHALL raise
`IllegalStateException` (from `snakestream.exception`), matching Java's
`Collectors.toMap(keyMapper, valueMapper)` throwing `IllegalStateException`
on a duplicate key. The raised exception SHALL name the colliding key.

`IllegalStateException` is a direct subclass of `Exception` and SHALL NOT be
made a subclass of `ValueError`: a caller catching `ValueError` around a
`to_map` collection no longer catches this.

#### Scenario: duplicate key without a merge function raises IllegalStateException
- **WHEN** `Stream.of(["a", "aa", "b"]).collect(to_map(lambda x: len(x), lambda x: x))` is called
- **THEN** an `IllegalStateException` is raised, since `"a"` and `"b"` both map to key `1`

#### Scenario: duplicate key is no longer a ValueError
- **WHEN** `Stream.of(["a", "aa", "b"]).collect(to_map(lambda x: len(x), lambda x: x))` is called inside a `try` that catches only `ValueError`
- **THEN** the `IllegalStateException` propagates uncaught, since it does not derive from `ValueError`

### Requirement: `to_map(key_mapper, value_mapper, merge_function)` resolves duplicate keys
`collector.py` SHALL provide the 3-arg `to_map(key_mapper, value_mapper,
merge_function)` form, where a duplicate key's colliding value is resolved
by calling `merge_function(existing_value, new_value)` (sync or async)
instead of raising, matching Java's `Collectors.toMap(keyMapper,
valueMapper, mergeFunction)`.

#### Scenario: duplicate key is resolved via merge_function
- **WHEN** `Stream.of(["a", "aa", "b"]).collect(to_map(lambda x: len(x), lambda x: x, lambda a, b: a + b))` is called
- **THEN** the result is `{1: "ab", 2: "aa"}`

#### Scenario: async merge_function is awaited
- **WHEN** `to_map(key_mapper, value_mapper, merge_function)` is given an async `merge_function` and a duplicate key occurs
- **THEN** the result is computed correctly, with `merge_function` awaited via the same dispatch used elsewhere in the library

#### Scenario: no collision means merge_function is never called
- **WHEN** `Stream.of([1, 2, 3]).collect(to_map(lambda x: x, lambda x: x, merge_function))` is called with all-distinct keys
- **THEN** the result is `{1: 1, 2: 2, 3: 3}` and `merge_function` is never invoked

### Requirement: `to_map` declares `UNORDERED` when it has no merge function

The collector returned by `to_map(key_mapper, value_mapper)` — the form called
with no `merge_function` — SHALL declare `Characteristics.UNORDERED`.

The declaration SHALL be true of the behaviour and not merely asserted. It is,
because with no merge function the collected `dict` is a function of the
element multiset alone: each key comes from `key_mapper` applied to one element
and each value from `value_mapper` applied to that same element, neither
consults any other element, `dict` equality compares key/value pairs without
regard to key order, and any element multiset that would have produced a
key-order-dependent result instead raises. So any two orderings of the same
elements collect to results that compare equal, which is the whole of what
`UNORDERED` asserts.

The declaration makes no promise about the `dict`'s own key iteration order,
which continues to follow the order the collector was fed. `UNORDERED` promises
equality of the collected result, not iteration order of it — the same
distinction `to_set()` and `grouping_by()` already rest on.

#### Scenario: the no-merge form declares UNORDERED
- **WHEN** the collector returned by `to_map(key_mapper, value_mapper)` is asked
  for its characteristics
- **THEN** they contain `Characteristics.UNORDERED`

#### Scenario: the collected dict is equal under any ordering of the same elements
- **WHEN** the same elements are collected with the same `to_map(key_mapper,
  value_mapper)` in two different orders, with no key collision
- **THEN** the two resulting `dict`s compare equal

#### Scenario: the mark does not promise key iteration order
- **WHEN** a `to_map(key_mapper, value_mapper)` collection runs under the racing
  executor with the delivery barrier skipped
- **THEN** the result compares equal to the sequential result, while its key
  iteration order may differ from encounter order

### Requirement: `to_map` with a merge function SHALL NOT declare `UNORDERED`

The collector returned by `to_map(key_mapper, value_mapper, merge_function)`
SHALL NOT declare `Characteristics.UNORDERED`, and SHALL NOT be made to declare
it by any later change.

`merge_function` is caller-supplied and is not required to commute. A merge
that keeps its first argument returns whichever colliding value arrived first,
and a merge that concatenates orders its operands, so for such a collection two
orderings of the same elements produce `dict`s that do not compare equal. The
collector is therefore order-sensitive in fact, not merely undeclared, and the
exclusion is permanent for the same reason `summing_double()`'s is: an
undeclared collector and a collector required never to declare are
indistinguishable in behaviour today but not in what a later pass may do.

A caller who knows their own `merge_function` commutes has `unordered()`, which
declares the same freedom at the pipeline rather than at the collector.

#### Scenario: the 3-arg form declares no characteristics
- **WHEN** the collector returned by `to_map(key_mapper, value_mapper,
  merge_function)` is asked for its characteristics
- **THEN** they do not contain `Characteristics.UNORDERED`

#### Scenario: a non-commuting merge function is honoured in encounter order
- **WHEN** a racing pipeline over elements with a key collision is collected
  with `to_map(key_mapper, value_mapper, merge_function)` for a
  `merge_function` that returns its first argument
- **THEN** the surviving value for the colliding key is the one from the
  earlier element in encounter order, because the collection is delivered
  through the reorder barrier

#### Scenario: the same factory yields different characteristics for its two forms
- **WHEN** `to_map(key_mapper, value_mapper)` and `to_map(key_mapper,
  value_mapper, merge_function)` are compared
- **THEN** the first declares `UNORDERED` and the second does not, the
  declaration being decided from the arguments rather than fixed for the factory

### Requirement: The duplicate-key exception names a colliding key, not a particular one

Where `to_map` is called with no `merge_function` and the elements contain a
duplicate key, the collection SHALL raise `IllegalStateException` naming a
colliding key. *Whether* it raises SHALL NOT depend on the order the elements
arrive in: a duplicate key is a property of the element multiset.

*Which* colliding key is named MAY differ between orderings when the elements
contain two or more distinct collisions, and callers SHALL NOT rely on a
particular one. Under `SEQUENTIAL` the key named is the first collision in
encounter order; under the fork-join executor the `UNORDERED` declaration
skips the delivery barrier, so a later collision may be reached first and
named instead.

#### Scenario: a duplicate key raises under either executor
- **WHEN** elements containing a duplicate key are collected with
  `to_map(key_mapper, value_mapper)` sequentially, and again under
  `.parallel()`
- **THEN** both collections raise `IllegalStateException`

#### Scenario: the named key may differ under racing
- **WHEN** elements containing two distinct key collisions are collected with
  `to_map(key_mapper, value_mapper)` under `.parallel()`
- **THEN** the raised `IllegalStateException` names one of the colliding keys,
  and which one is not guaranteed

#### Scenario: a merge function removes the question
- **WHEN** the same elements are collected with `to_map(key_mapper,
  value_mapper, merge_function)`
- **THEN** nothing is raised, and the collection is delivered in encounter order
  because that form declares no `UNORDERED`

### Requirement: `to_map(key_mapper, value_mapper, merge_function, map_supplier)` chooses the result container

`to_map` SHALL provide a 4-arg form whose fourth argument supplies the mapping
the result is built into, matching Java's `Collectors.toMap(Function keyMapper,
Function valueMapper, BinaryOperator mergeFunction, Supplier mapSupplier)`.

`map_supplier` SHALL be called with no arguments exactly once per collection,
before any element is accumulated, to produce a fresh empty mapping. It MAY be
sync or async and SHALL be awaited via the same dispatch every other
user-supplied callable in the library uses. The mapping it returns SHALL be the
object the collection returns: keys and merged values are written into that
object and it is returned as-is, so a caller-supplied type reaches the caller
intact rather than being copied into a `dict`.

Key mapping, value mapping, and duplicate-key resolution via `merge_function`
SHALL behave exactly as in the 3-arg form. The 1-, 2- and 3-argument forms
SHALL be unaffected in signature, result and characteristics.

#### Scenario: the result is the caller's mapping type
- **WHEN** `Stream.of([1, 2, 3]).collect(to_map(lambda x: x, lambda x: x * x, lambda a, b: b, OrderedDict))` is called
- **THEN** the result is an `OrderedDict` holding `{1: 1, 2: 4, 3: 9}`, not a plain `dict`

#### Scenario: a fresh mapping per collection
- **WHEN** the same 4-arg `to_map` collector instance is used across two separate `collect()` calls
- **THEN** each call returns an independent mapping, unaffected by the other call's elements

#### Scenario: empty stream yields the caller's empty mapping
- **WHEN** `Stream.of([]).collect(to_map(k, v, merge, OrderedDict))` is called
- **THEN** the result is an empty `OrderedDict`

#### Scenario: duplicate keys are merged into the caller's mapping
- **WHEN** `Stream.of(["a", "aa", "b"]).collect(to_map(len, lambda x: x, lambda a, b: a + b, OrderedDict))` is called
- **THEN** the result is an `OrderedDict` holding `{1: "ab", 2: "aa"}`

#### Scenario: an async map_supplier is awaited
- **WHEN** the 4-arg `to_map` is given an async `map_supplier`
- **THEN** the mapping it resolves to is used as the result container

### Requirement: `to_map`'s overload set is exactly Java's three forms

`to_map` SHALL accept exactly the argument counts Java's three `toMap`
overloads accept: `(key_mapper, value_mapper)`, `(key_mapper, value_mapper,
merge_function)` and `(key_mapper, value_mapper, merge_function,
map_supplier)`. The declared type surface SHALL express those three forms and
no others.

There SHALL be no `to_map(key_mapper, value_mapper, map_supplier)` form.
Java has no such overload, and providing one would expand the public surface
rather than close a parity gap. A caller who wants a chosen container and no
merging supplies a `merge_function` that states what a collision means.

A consequence: the 4-arg form always carries a `merge_function`, so it SHALL
NOT declare `Characteristics.UNORDERED`, for the reason the 3-arg form already
does not — a caller-supplied merge need not commute. The container question
therefore never arises for `to_map`.

#### Scenario: the 4-arg form declares no characteristics
- **WHEN** the collector returned by `to_map(key_mapper, value_mapper, merge_function, map_supplier)` is asked for its characteristics
- **THEN** they do not contain `Characteristics.UNORDERED`

#### Scenario: a container without a merge function is not an accepted form
- **WHEN** a caller supplies a mapping type in place of `merge_function`
- **THEN** the call is not one of the declared forms and is reported by the project's static type check

#### Scenario: the no-merge form still declares UNORDERED
- **WHEN** the collector returned by `to_map(key_mapper, value_mapper)` is asked for its characteristics
- **THEN** they contain `Characteristics.UNORDERED`, unchanged by the new overload

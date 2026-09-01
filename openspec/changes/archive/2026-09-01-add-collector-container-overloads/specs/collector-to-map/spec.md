## ADDED Requirements

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

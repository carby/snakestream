## ADDED Requirements

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
encounter order; under `RACING` the `UNORDERED` declaration skips the delivery
barrier, so a later collision may be reached first and named instead.

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

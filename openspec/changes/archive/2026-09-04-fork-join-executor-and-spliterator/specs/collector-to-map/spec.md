## MODIFIED Requirements

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

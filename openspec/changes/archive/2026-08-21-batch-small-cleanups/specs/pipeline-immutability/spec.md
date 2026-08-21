## MODIFIED Requirements

### Requirement: Intermediate ops return a new instance
`Stream`'s intermediate operations (`map`, `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) SHALL return a new `Stream`/`ParallelStream` instance carrying the extended chain, rather than mutating and returning the receiver.

#### Scenario: map() returns a distinct object
- **WHEN** `s2 = s.map(f)` is called on a `Stream` instance `s`
- **THEN** `s2 is not s`

#### Scenario: Chaining still works without holding intermediate references
- **WHEN** a fluent chain like `Stream.of([1, 2, 3]).map(f).filter(g).collect(to_list())` is awaited, with no intermediate result bound to a variable
- **THEN** it produces the same result as before this change

### Requirement: Using an already-extended reference raises
Once a `Stream`/`ParallelStream` instance has been used to build a new instance (via any intermediate operation or `sequential()`/`parallel()`), any further call on that same, now-superseded reference — whether an intermediate operation or a terminal operation (`collect`, `reduce`, `for_each`, `for_each_ordered`, `find_any`, `find_first`, `max`, `min`, `all_match`, `any_match`, `none_match`, `count`, `to_array`, `iterator`) — SHALL raise `IllegalStateException`.

#### Scenario: Extending an already-extended reference raises
- **WHEN** `s.map(f)` has already been called on `s`, and `s.filter(g)` is subsequently called on the same `s`
- **THEN** `s.filter(g)` raises `IllegalStateException`

#### Scenario: Terminally consuming an already-extended reference raises
- **WHEN** `s.map(f)` has already been called on `s`, and `s.collect(to_list())` is subsequently awaited on the same `s`
- **THEN** it raises `IllegalStateException`

#### Scenario: The new instance returned by the extending call is unaffected
- **WHEN** `s2 = s.map(f)` has been called on `s`
- **THEN** further intermediate or terminal operations on `s2` succeed normally

### Requirement: Repeat terminal consumption of an unextended reference is unaffected
A `Stream`/`ParallelStream` instance that has never been used to build a further instance (no intermediate operation or mode switch called on it) SHALL remain callable for a terminal operation more than once, per the existing `pipeline-composition` chain-recomposition contract. This requirement is unaffected by this change and is restated here to make the boundary between "extended" (invalidated) and "merely terminally consumed" (not invalidated) explicit and testable.

#### Scenario: Second terminal call on a never-extended reference does not raise
- **WHEN** `first = await s.collect(to_list())` is awaited on a `Stream` instance `s` that has never had an intermediate operation called on it, and `second = await s.collect(to_list())` is subsequently awaited on the same `s`
- **THEN** neither call raises `IllegalStateException`, and `second` reflects the already-exhausted source per the existing `pipeline-composition` contract (e.g. `[]` for a plain list source)

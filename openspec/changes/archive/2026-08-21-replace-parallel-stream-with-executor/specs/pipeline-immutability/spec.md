## MODIFIED Requirements

### Requirement: Mode switches return a new instance and invalidate the old reference
`sequential()` and `parallel()` SHALL return a new instance and SHALL mark the receiver as consumed so it can no longer be used to build or terminally consume a pipeline.

The new instance SHALL carry the receiver's source, its queued chain, its ordering flag, its close handlers and its concrete type, differing from the receiver only in which executor it holds. A mode switch SHALL NOT compose the chain into a generator, and SHALL NOT alter the receiver's own executor in place: assigning a new executor onto `self` and returning `self` is expressly forbidden, because it would leave the receiver usable and so violate this requirement.

#### Scenario: parallel() invalidates the pre-switch reference
- **WHEN** `p = s.parallel()` is called on a `Stream` instance `s`, and `s` is then used to call any intermediate or terminal operation
- **THEN** that later call on `s` raises `IllegalStateException`

#### Scenario: A mode switch returns a distinct object
- **WHEN** `p = s.parallel()` is called on a `Stream` instance `s`
- **THEN** `p is not s`

#### Scenario: The queued chain survives a mode switch
- **WHEN** an intermediate operation is queued on `s`, then `p = s.parallel()` is called, and a terminal operation is awaited on `p`
- **THEN** that queued operation is applied, rather than having been composed away or dropped

### Requirement: Using an already-extended reference raises
Once a `Stream` instance has been used to build a new instance (via any intermediate operation or `sequential()`/`parallel()`), any further call on that same, now-superseded reference — whether an intermediate operation or a terminal operation (`collect`, `reduce`, `for_each`, `for_each_ordered`, `find_any`, `find_first`, `max`, `min`, `all_match`, `any_match`, `none_match`, `count`, `to_array`, `iterator`) — SHALL raise `IllegalStateException`.

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
A `Stream` instance that has never been used to build a further instance (no intermediate operation or mode switch called on it) SHALL remain callable for a terminal operation more than once, per the existing `pipeline-composition` chain-recomposition contract. This requirement is unaffected by this change and is restated here to make the boundary between "extended" (invalidated) and "merely terminally consumed" (not invalidated) explicit and testable.

#### Scenario: Second terminal call on a never-extended reference does not raise
- **WHEN** `first = await s.collect(to_list())` is awaited on a `Stream` instance `s` that has never had an intermediate operation called on it, and `second = await s.collect(to_list())` is subsequently awaited on the same `s`
- **THEN** neither call raises `IllegalStateException`, and `second` reflects the already-exhausted source per the existing `pipeline-composition` contract (e.g. `[]` for a plain list source)

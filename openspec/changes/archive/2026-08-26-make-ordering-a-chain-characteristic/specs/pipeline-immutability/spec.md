## MODIFIED Requirements

### Requirement: Intermediate ops return a new instance
`Stream`'s intermediate operations (`map`, `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`, `unordered`) SHALL return a new `Stream` instance carrying the extended chain, rather than mutating and returning the receiver.

`unordered()` is included in that list and carries no exemption: it queues an
operation onto the chain like every other intermediate operation, so the reason
it was previously allowed to mutate and return the receiver — that it had no
chain element to append — no longer holds. `on_close()` remains exempt, as a
lifecycle operation rather than a pipeline stage.

#### Scenario: map() returns a distinct object
- **WHEN** `s2 = s.map(f)` is called on a `Stream` instance `s`
- **THEN** `s2 is not s`

#### Scenario: unordered() returns a distinct object
- **WHEN** `s2 = s.unordered()` is called on a `Stream` instance `s`
- **THEN** `s2 is not s`, and a subsequent call on `s` raises `IllegalStateException`

#### Scenario: Chaining still works without holding intermediate references
- **WHEN** a fluent chain like `Stream.of([1, 2, 3]).map(f).filter(g).collect(to_list())` is awaited, with no intermediate result bound to a variable
- **THEN** it produces the same result as before this change

### Requirement: Mode switches return a new instance and invalidate the old reference
`sequential()` and `parallel()` SHALL return a new instance and SHALL mark the receiver as consumed so it can no longer be used to build or terminally consume a pipeline.

The new instance SHALL carry the receiver's source, its queued chain, its close handlers and its concrete type, differing from the receiver only in which executor it holds. A mode switch SHALL NOT compose the chain into a generator, and SHALL NOT alter the receiver's own executor in place: assigning a new executor onto `self` and returning `self` is expressly forbidden, because it would leave the receiver usable and so violate this requirement.

The pipeline's ordering characteristic SHALL NOT be carried as separate state
alongside the chain. It survives a mode switch because the chain does; see the
`stream-ordering` capability.

#### Scenario: parallel() invalidates the pre-switch reference
- **WHEN** `p = s.parallel()` is called on a `Stream` instance `s`, and `s` is then used to call any intermediate or terminal operation
- **THEN** that later call on `s` raises `IllegalStateException`

#### Scenario: A mode switch returns a distinct object
- **WHEN** `p = s.parallel()` is called on a `Stream` instance `s`
- **THEN** `p is not s`

#### Scenario: The queued chain survives a mode switch
- **WHEN** an intermediate operation is queued on `s`, then `p = s.parallel()` is called, and a terminal operation is awaited on `p`
- **THEN** that queued operation is applied, rather than having been composed away or dropped

## Purpose

Defines the contract for treating stream instances as immutable, single-use references once they have been extended: intermediate operations and mode switches (`sequential()`/`parallel()`) return a new instance carrying the extended chain rather than mutating and returning the receiver, and the superseded receiver is invalidated so it can no longer be used to build or terminally consume a pipeline. Lifecycle operations (`on_close()`/`close()`) are exempt from this invalidation, and repeat terminal consumption of a reference that was never extended remains governed by the existing `pipeline-composition` chain-recomposition contract.

## Requirements

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

### Requirement: Using an already-extended reference raises
Once a `Stream` instance has been used to build a new instance (via any intermediate operation or `sequential()`/`parallel()`), any further call on that same, now-superseded reference — whether an intermediate operation or a terminal operation (`collect`, `reduce`, `for_each`, `for_each_ordered`, `find_any`, `find_first`, `max`, `min`, `all_match`, `any_match`, `none_match`, `count`, `to_array`, `iterator`) — SHALL raise `IllegalStateException`.

This invalidation check SHALL also apply when an already-extended `Stream` is supplied to the library as an argument, not only when a method is called directly on it: passing such a reference to `Stream.concat()`, or returning it from a `flat_map()` mapper, SHALL raise `IllegalStateException`. `concat()`'s check SHALL fire at the time `concat()` is called, not deferred to the first pull of the concatenated stream. A `flat_map()` mapper's check SHALL fire when the mapper's returned stream is composed for iteration, before any of its elements are pulled.

A `Stream` that was merely *consumed* by a terminal operation, but never *extended* by an intermediate operation or mode switch, is unaffected by either check — the existing "repeat terminal consumption of an unextended reference" requirement below already governs that case in both positions.

#### Scenario: Extending an already-extended reference raises
- **WHEN** `s.map(f)` has already been called on `s`, and `s.filter(g)` is subsequently called on the same `s`
- **THEN** `s.filter(g)` raises `IllegalStateException`

#### Scenario: Terminally consuming an already-extended reference raises
- **WHEN** `s.map(f)` has already been called on `s`, and `s.collect(to_list())` is subsequently awaited on the same `s`
- **THEN** it raises `IllegalStateException`

#### Scenario: The new instance returned by the extending call is unaffected
- **WHEN** `s2 = s.map(f)` has been called on `s`
- **THEN** further intermediate or terminal operations on `s2` succeed normally

#### Scenario: Passing an already-extended stream to concat() raises
- **WHEN** `s.map(f)` has already been called on `s` (superseding `s`), and `s` is then passed as an argument to `Stream.concat(s, other)`
- **THEN** `Stream.concat(s, other)` raises `IllegalStateException` at call time, before any element is pulled from either argument

#### Scenario: Returning an already-extended stream from a flat_map() mapper raises
- **WHEN** a `flat_map()` mapper returns a `Stream` instance that has already been used to build a further instance
- **THEN** consuming the outer chain raises `IllegalStateException` when that mapper's returned stream is composed for iteration, matching the same-reference behavior when the receiver itself is used directly

#### Scenario: A merely-consumed (never extended) stream passed to concat() does not raise
- **WHEN** a `Stream` instance that has never been extended, but has already been terminally consumed once, is passed to `Stream.concat()`
- **THEN** `concat()` does not raise on account of invalidation; the existing "repeat terminal consumption of an unextended reference" requirement governs what elements it yields

### Requirement: Repeat terminal consumption of an unextended reference is unaffected
A `Stream` instance that has never been used to build a further instance (no intermediate operation or mode switch called on it) SHALL remain callable for a terminal operation more than once, per the existing `pipeline-composition` chain-recomposition contract. This requirement is unaffected by this change and is restated here to make the boundary between "extended" (invalidated) and "merely terminally consumed" (not invalidated) explicit and testable.

#### Scenario: Second terminal call on a never-extended reference does not raise
- **WHEN** `first = await s.collect(to_list())` is awaited on a `Stream` instance `s` that has never had an intermediate operation called on it, and `second = await s.collect(to_list())` is subsequently awaited on the same `s`
- **THEN** neither call raises `IllegalStateException`, and `second` reflects the already-exhausted source per the existing `pipeline-composition` contract (e.g. `[]` for a plain list source)

### Requirement: Lifecycle operations are exempt from invalidation
`on_close()` and `close()` SHALL NOT be gated by, and SHALL NOT set, the consumed/invalidation state introduced by this capability. They remain usable on any reference, extended or not, before or after the pipeline has been consumed.

#### Scenario: close() succeeds on a reference already used to build a further instance
- **WHEN** `s.on_close(handler)` has been called on `s`, then `s.map(f)` has been called on `s` (superseding `s`), then `s.close()` is called on the original `s`
- **THEN** `s.close()` does not raise, and `handler` is called

#### Scenario: on_close() registered on a derived instance still fires via the original reference
- **WHEN** `s.on_close(handler1)` is called on `s`, then `s2 = s.parallel()`, then `s2.on_close(handler2)` is called, then a terminal operation is awaited on `s2`, then `s.close()` is called on the original `s`
- **THEN** both `handler1` and `handler2` are called, matching today's shared-`_close_handlers`-list behavior

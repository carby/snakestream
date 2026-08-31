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
Once a `Stream` instance has been used to build a new instance (via any intermediate operation, via `sequential()`/`parallel()`, or by being passed as an operand to `Stream.concat()`), any further call on that same, now-superseded reference — whether an intermediate operation or a terminal operation (`collect`, `reduce`, `for_each`, `for_each_ordered`, `find_any`, `find_first`, `max`, `min`, `all_match`, `any_match`, `none_match`, `count`, `to_array`, `iterator`) — SHALL raise `IllegalStateException`.

`Stream.concat()` is included in that list of extending operations: it builds a new stream over both operands' pipelines, so both operands are superseded by it exactly as a receiver is superseded by an intermediate operation called on it. The `stream-concat` capability carries the requirement and its scenarios; it is named here because this is the requirement that defines what "extended" means.

This invalidation check SHALL also apply when an already-extended `Stream` is supplied to the library as an argument, not only when a method is called directly on it: passing such a reference to `Stream.concat()`, or returning it from a `flat_map()` mapper, SHALL raise `IllegalStateException`. `concat()`'s check SHALL fire at the time `concat()` is called, not deferred to the first pull of the concatenated stream. A `flat_map()` mapper's check SHALL fire when the mapper's returned stream is composed for iteration, before any of its elements are pulled.

A `Stream` that was merely *consumed* by a terminal operation, but never *extended* by an intermediate operation, a mode switch or a `concat()`, is unaffected by either check — the existing "repeat terminal consumption of an unextended reference" requirement below already governs that case in both positions. That exemption concerns an operand's state on the way *in* to `concat()`; it does not survive the call, since `concat()` extends what it is given.

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

#### Scenario: A never-extended operand is extended by the concat itself
- **WHEN** a `Stream` instance that has never been extended is passed to `Stream.concat()`, and an operation is subsequently attempted on that same instance
- **THEN** that later operation raises `IllegalStateException`, the `concat()` call having extended it

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

### Requirement: Deriving a new stage does not re-enter the constructor

Deriving a new stream instance — via any intermediate operation or via
`sequential()`/`parallel()` — SHALL NOT invoke the stream class's `__init__`.
The derived instance SHALL be produced by shallow-copying the receiver, so
that a subclass's constructor runs exactly once per pipeline, at the point the
caller constructs the stream, and not once per stage.

This is the mechanism by which the "carry the receiver's concrete type"
requirement above is satisfied. That requirement never specified *how* the
concrete type is carried; this one does, because the observable consequence for
a subclass that acquires a resource in `__init__` is the whole point: such a
subclass previously acquired one resource per stage and retained only the last.

#### Scenario: A subclass constructor runs once for a multi-stage pipeline

- **WHEN** a `Stream` subclass that counts its own `__init__` invocations is
  constructed and then extended by three intermediate operations and one mode
  switch
- **THEN** its `__init__` has been invoked exactly once

#### Scenario: A subclass attribute is the same object at every stage

- **WHEN** a `Stream` subclass assigns `self.resource = object()` in its
  `__init__`, and the resulting stream is extended by an intermediate operation
  and by a mode switch
- **THEN** the final stage's `resource` **is** the object the constructor
  assigned, by identity and not merely by equality

#### Scenario: A resource acquired in the constructor is acquired once

- **WHEN** a `Stream` subclass acquires a resource in `__init__` and releases it
  in an overridden `close()`, and the stream is extended by two intermediate
  operations before `close()` is called
- **THEN** exactly one resource has been acquired and exactly one has been
  released, with no unreleased resource remaining

### Requirement: A subclass may define any constructor signature

A `Stream` subclass SHALL be free to define an `__init__` of any signature.
Derivation SHALL NOT require a subclass constructor to accept the base class's
`(source, close_handlers)` parameters, positionally or otherwise, and SHALL NOT
require it to accept an already-normalized asynchronous generator.

A subclass whose constructor takes an unrelated argument — a connection string,
a file path, an open handle — and calls `super().__init__(...)` with a source of
its own choosing SHALL support the full set of intermediate operations and mode
switches on the resulting stream.

#### Scenario: A subclass taking a single unrelated argument can be extended

- **WHEN** a `Stream` subclass defines `__init__(self, dsn)`, acquires a
  resource from `dsn`, calls `super().__init__(<a source>)`, and the resulting
  stream has an intermediate operation applied to it
- **THEN** the operation succeeds and returns a new instance of that subclass,
  rather than raising `TypeError`

#### Scenario: A subclass taking no arguments at all can be extended

- **WHEN** a `Stream` subclass defines `__init__(self)` and the resulting stream
  is extended by an intermediate operation and then by a mode switch
- **THEN** both succeed and each returned instance is an instance of that
  subclass

### Requirement: Subclass state is shared across a pipeline's stages

State a subclass places on itself in `__init__` SHALL be shared by every stage
derived from that stream, by reference rather than by copy. A pipeline's stages
SHALL NOT hold independent copies of such state.

This is the coherent reading alongside the `stream-close-handling` capability,
whose close-handler list is already shared by reference across stages: one
resource per pipeline, registered once, released once by a single `close()`.

#### Scenario: Mutating subclass state through one stage is visible from another

- **WHEN** a `Stream` subclass holds a mutable attribute assigned in `__init__`,
  a stage is derived from it, and that attribute is mutated through the derived
  stage
- **THEN** the mutation is visible through the original reference's attribute,
  the two being the same object

### Requirement: Shallow-copy hooks on a subclass are respected

Because derivation is defined as a shallow copy, a subclass that defines
`__copy__` SHALL have it honoured when a stage is derived. `Stream` itself
SHALL NOT define `__copy__`, so that the default shallow-copy behaviour applies
unless a subclass deliberately overrides it.

This is stated rather than left implicit because the hook is load-bearing under
this change where it was inert before: a `__copy__` on a subclass previously
had no effect on pipeline construction and now governs it.

#### Scenario: Stream does not define its own copy hook

- **WHEN** the `Stream` class is inspected for a `__copy__` attribute defined on
  `Stream` itself
- **THEN** no such attribute is defined

#### Scenario: A subclass's copy hook governs derivation

- **WHEN** a `Stream` subclass defines `__copy__` and records that it ran, and
  a stage is derived from an instance of that subclass
- **THEN** the subclass's `__copy__` has run

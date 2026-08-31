## ADDED Requirements

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

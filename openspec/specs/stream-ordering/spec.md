## Purpose

Defines the contract for `BaseStream`'s ordered/unordered bookkeeping: the `_ordered` flag, `unordered()`, and `is_ordered()`, mirroring Java's `BaseStream.unordered()`. This is purely a declarative marker on a stream instance — it does not itself alter iteration order in `Stream` or `ParallelStream` — but it must be tracked correctly per-instance and survive `sequential()`/`parallel()` mode switches so that order-sensitive operations (e.g. `for_each_ordered()`) built on top of it behave correctly.

## Requirements

### Requirement: BaseStream tracks an ordered/unordered flag defaulting to ordered
Every `BaseStream` instance SHALL carry a per-instance ordering flag that
defaults to ordered (`True`) at construction, queryable via
`is_ordered() -> bool`.

#### Scenario: A freshly constructed stream is ordered by default
- **WHEN** a new `Stream` (or `ParallelStream`) is constructed
- **THEN** `.is_ordered()` returns `True`

### Requirement: BaseStream.unordered() marks the stream as not order-dependent
`BaseStream.unordered()` SHALL set the instance's ordering flag to `False`
and return `self`, following the same mutate-and-return-self convention as
other chainable `BaseStream`/`Stream` methods (e.g. `filter()`, `map()`,
`on_close()`).

#### Scenario: unordered() flips is_ordered() to False
- **WHEN** `.unordered()` is called on a `Stream`
- **THEN** a subsequent `.is_ordered()` call on that same instance returns
  `False`

#### Scenario: unordered() returns self for chaining
- **WHEN** `.unordered()` is called on a `Stream`
- **THEN** the return value is the same instance the method was called on,
  so it can be chained with other intermediate operations (e.g.
  `Stream.of([...]).unordered().filter(...)`)

#### Scenario: unordered() does not affect other stream instances
- **WHEN** `.unordered()` is called on one `Stream` instance
- **THEN** a separate, independently constructed `Stream` instance's
  `.is_ordered()` still returns `True`

### Requirement: The ordering flag survives sequential()/parallel() mode switches
`BaseStream.sequential()` and `BaseStream.parallel()` SHALL propagate the
calling instance's current ordering flag onto the new `Stream`/
`ParallelStream` instance they construct, rather than resetting it to the
default.

#### Scenario: unordered() survives a parallel() switch
- **WHEN** `.unordered()` is called on a `Stream`, followed by `.parallel()`
- **THEN** the resulting `ParallelStream`'s `.is_ordered()` returns `False`

#### Scenario: unordered() survives a sequential() switch
- **WHEN** `.unordered()` is called on a `ParallelStream`, followed by
  `.sequential()`
- **THEN** the resulting `Stream`'s `.is_ordered()` returns `False`

#### Scenario: An ordered stream stays ordered across a mode switch
- **WHEN** `.parallel()` (or `.sequential()`) is called on a stream that
  never had `.unordered()` called on it
- **THEN** the resulting instance's `.is_ordered()` still returns `True`

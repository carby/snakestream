## ADDED Requirements

### Requirement: Source acceptance does not depend on execution mode

The set of source values a stream accepts and can consume SHALL be identical in
both execution modes. Any source a sequentially-executed pipeline consumes
successfully SHALL be consumed successfully by the same pipeline under
`.parallel()`, producing the same elements as a multiset. No source SHALL raise
an error in one mode that it does not raise in the other.

In particular, an async source SHALL NOT be required to be a full async
generator. An `AsyncIterable` is accepted whether or not it exposes `aclose()`,
and whether or not its `__aiter__()` returns itself: a racing branch SHALL
obtain its iterator through the same protocol a sequential pass uses, and SHALL
close the source only if the source is closeable.

Ordering is the one difference between the modes and is unaffected by this
requirement: the racing mode still does not preserve encounter order, so the
comparison of results between modes is order-insensitive.

#### Scenario: Racing over an async iterator with no aclose()
- **WHEN** a stream is constructed from an object implementing `__aiter__` (returning itself) and `__anext__` but no `aclose()`, and is consumed with `.parallel()`
- **THEN** the stream yields exactly the elements the object produces, with no `AttributeError`, and the same elements the sequential consumption of an identical source yields

#### Scenario: Racing over a source whose `__aiter__` returns a separate iterator
- **WHEN** a stream is constructed from an object whose `__aiter__` returns a distinct iterator rather than `self`, and is consumed with `.parallel()`
- **THEN** the stream yields exactly the elements that iterator produces, with no `AttributeError`

#### Scenario: A closeable source is still closed under racing
- **WHEN** a stream constructed from an async generator is consumed with `.parallel()`
- **THEN** the async generator is closed by the time consumption finishes, as it is under sequential consumption

#### Scenario: Sync and scalar sources race identically
- **WHEN** a stream constructed from a list, a bare sync iterator, or a scalar value is consumed with `.parallel()`
- **THEN** it yields the same elements, as a multiset, as the same stream consumed sequentially

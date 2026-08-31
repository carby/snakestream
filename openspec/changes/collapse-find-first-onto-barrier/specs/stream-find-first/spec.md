## MODIFIED Requirements

### Requirement: Stream.find_first() returns the first element in encounter order
`Stream.find_first()` SHALL return the first element pulled through the
composed chain, or `None` if the stream is empty, matching Java's
`Stream.findFirst()`.

#### Scenario: Non-empty stream returns its first element
- **WHEN** `.find_first()` is called on a `Stream` built from a non-empty
  source
- **THEN** the first element in the source's encounter order is returned

#### Scenario: Empty stream returns None
- **WHEN** `.find_first()` is called on a `Stream` built from an empty
  source
- **THEN** `None` is returned

#### Scenario: find_first() does not consume the rest of the stream
- **WHEN** `.find_first()` is called on a **sequential** stream with more than
  one element
- **THEN** only the first element is pulled from upstream before the method
  returns

### Requirement: find_first() preserves encounter order regardless of the ordering characteristic
`Stream.find_first()` SHALL return the first element in the stream's encounter
order, or `None` if the stream is empty, regardless of which executor the
stream carries and regardless of whether the pipeline is ordered or unordered.

It SHALL achieve this by demanding encounter order **unconditionally** at the
point elements are delivered to it — the same delivery barrier every other
order-observing terminal uses, differing only in that no other terminal demands
it on a pipeline whose ordering characteristic has been cleared. It SHALL NOT
achieve it by driving the chain under the sequential executor, and SHALL NOT
otherwise constrain how the chain runs: a `find_first()` on a parallel stream
races its operations across all branches, and only the selection of the element
returned is ordered.

This matches Java, where `findFirst()`'s find-the-leftmost behaviour is fixed
when the operation is constructed and never consults the upstream ordering
flag, and where `FindTask` performs its leftmost scan across fork-join branches
rather than falling back to a sequential traversal. Java's javadoc *permits* an
unordered stream to return any element; the reference implementation declines to
take that permission, and so does this library. A caller who wants the
relaxation SHALL use `find_any()`.

There SHALL be exactly one implementation of `find_first()`, with no branch on
the stream's type, executor or ordering characteristic.

#### Scenario: Ordered parallel stream returns the true first element
- **WHEN** `.find_first()` is called on an ordered parallel stream whose chain
  includes a step that could otherwise complete out of encounter order under
  racing execution (e.g. a `.map()` with per-element variable delay)
- **THEN** the returned element is the first element in the original source's
  encounter order, not merely the first result to arrive

#### Scenario: Unordered parallel stream also returns the true first element
- **WHEN** `.unordered()` is called on a parallel stream carrying such a chain,
  followed by `.find_first()`
- **THEN** the first element in the original source's encounter order is
  returned — the same element the ordered pipeline returns

#### Scenario: Ordered parallel stream with an empty source returns None
- **WHEN** `.find_first()` is called on a parallel stream built from an empty
  source, ordered or unordered
- **THEN** `None` is returned

#### Scenario: An op declared before .parallel() does not defeat the order guarantee
- **WHEN** `.map(f)` is declared before `.parallel()` on a stream and
  `.find_first()` is called, so that the map now runs under the racing executor
  for ordinary terminals
- **THEN** `find_first()` still returns the first element in encounter order,
  because its demand for encounter order at delivery does not depend on where
  the mode switch was written

#### Scenario: find_any() remains the unordered alternative
- **WHEN** `.find_any()` is called on a parallel stream
- **THEN** its existing racing behaviour is unchanged by this requirement — it
  is the operation a caller uses to opt out of the encounter-order guarantee

## ADDED Requirements

### Requirement: A parallel find_first() does not forfeit the caller's execution mode
`Stream.find_first()` SHALL execute under the executor its stream carries. On a
parallel stream every operation in the chain SHALL run across all branches
concurrently, and `is_parallel()` SHALL remain an accurate statement of how the
call will run.

Where the chain's operations can *drop* elements — `filter()`, and a
`flat_map()` whose mapper may yield nothing — this SHALL make a parallel
`find_first()` faster than the sequential one over the same source, because
several source elements must be processed before any answer exists. Where they
cannot, it SHALL be no slower.

#### Scenario: A dropping chain is faster in parallel
- **WHEN** `.parallel().filter(p).find_first()` is awaited on a source whose
  first several elements fail `p` and whose predicate is expensive
- **THEN** the correct first matching element is returned, and the call
  completes in substantially less wall-clock time than the same pipeline under
  `.sequential()`

#### Scenario: A non-dropping chain is no slower in parallel
- **WHEN** `.parallel().map(f).find_first()` is awaited on a source with an
  expensive mapper
- **THEN** the correct first element is returned in wall-clock time comparable
  to the same pipeline under `.sequential()`

### Requirement: find_first() may invoke a chain's callables more than once
On a parallel stream, `Stream.find_first()` SHALL be permitted to invoke the
callables of the operations in its chain on source elements other than the one
it ultimately returns, because the branches must be racing before it is known
which element is first.

The number of such elements SHALL be bounded. It SHALL NOT exceed the racing
executor's read-ahead bound, and where the source's elements complete at a
uniform rate it SHALL NOT exceed the worker count, because the call settles as
soon as the first element is released and no branch can be more than one
element ahead at that point.

A sequential `find_first()` SHALL continue to invoke them for exactly one
element.

Callers whose chain callables have side effects and who require exactly one
invocation SHALL declare `.sequential()`.

#### Scenario: A parallel find_first() may process more than one element
- **WHEN** `.parallel().map(f).find_first()` is awaited on a source of many
  elements
- **THEN** the correct first element is returned, and `f` is permitted to have
  been invoked on more than one element, up to the read-ahead bound

#### Scenario: A sequential find_first() processes exactly one
- **WHEN** `.sequential().map(f).find_first()` is awaited on the same source
- **THEN** `f` is invoked exactly once

## MODIFIED Requirements

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
  `.find_first()` is called, so that the map now runs under the fork-join
  executor for ordinary terminals
- **THEN** `find_first()` still returns the first element in encounter order,
  because its demand for encounter order at delivery does not depend on where
  the mode switch was written

#### Scenario: find_any() remains the unordered alternative
- **WHEN** `.find_any()` is called on a parallel stream
- **THEN** its existing racing behaviour is unchanged by this requirement — it
  is the operation a caller uses to opt out of the encounter-order guarantee

### Requirement: find_first() may invoke a chain's callables more than once
On a parallel stream, `Stream.find_first()` SHALL be permitted to invoke the
callables of the operations in its chain on source elements other than the one
it ultimately returns, because the batches must be dispatched and running
before it is known which element is first.

The number of such elements SHALL be bounded. Under the fork-join executor it
SHALL NOT exceed the total number of elements pulled into the first round of
batches — `WORKERS` batches of up to `_FIRST_BATCH_SIZE` elements each — because
the call settles as soon as the first element is released, and unless the
source is exhausted first, resolving it never requires starting a second round.

A sequential `find_first()` SHALL continue to invoke them for exactly one
element.

Callers whose chain callables have side effects and who require exactly one
invocation SHALL declare `.sequential()`.

#### Scenario: A parallel find_first() may process more than one element
- **WHEN** `.parallel().map(f).find_first()` is awaited on a source of many
  elements
- **THEN** the correct first element is returned, and `f` is permitted to have
  been invoked on more than one element, up to the first round's bound

#### Scenario: A sequential find_first() processes exactly one
- **WHEN** `.sequential().map(f).find_first()` is awaited on the same source
- **THEN** `f` is invoked exactly once

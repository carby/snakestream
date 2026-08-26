## ADDED Requirements

### Requirement: Ordering is derived from the stream's queued operations
A stream's ordered/unordered characteristic SHALL be derived from the
operations queued on it, not from per-instance state set independently of the
chain. Each queued operation SHALL either preserve the ordering characteristic
of everything before it (the behaviour of `map`, `filter`, `flat_map`, `peek`,
`distinct`, `limit` and `skip`), clear it, or set it; `is_ordered()` SHALL
report the result of applying those operations in the order they were queued,
starting from ordered.

This makes the characteristic **positional**: an operation declared before an
ordering-clearing operation is unaffected by it, and an operation declared
after it is. This is deliberately the opposite of `sequential()`/`parallel()`,
which are position-independent because they select an executor for the whole
pipeline rather than occupying a position in it.

#### Scenario: A stream with no ordering operations queued is ordered
- **WHEN** `.is_ordered()` is called on a newly constructed stream, or on one
  carrying only order-preserving operations such as `.map()` and `.filter()`
- **THEN** `True` is returned

#### Scenario: Clearing ordering affects only what follows it
- **WHEN** a pipeline queues an order-preserving operation, then `.unordered()`,
  then a second order-preserving operation
- **THEN** `.is_ordered()` returns `False`, and the operations queued before
  `.unordered()` are still applied exactly as they were, unchanged in behaviour
  and position

#### Scenario: Ordering is not carried between unrelated streams
- **WHEN** `.unordered()` is called on one stream
- **THEN** a separately constructed stream's `.is_ordered()` still returns
  `True`

### Requirement: unordered() queues an ordering-clearing operation
`Stream.unordered()` SHALL queue an operation that clears the ordering
characteristic for everything after it, and SHALL return a new `Stream`
instance carrying the extended chain, invalidating the receiver in the same way
every other intermediate operation does (see the `pipeline-immutability`
capability). It SHALL NOT mutate and return the receiver.

The queued operation SHALL be an identity operation: it SHALL NOT observe,
transform, reorder, drop or duplicate any element, and its only effect SHALL be
on the ordering characteristic.

#### Scenario: unordered() flips is_ordered() to False
- **WHEN** `.unordered()` is called on a stream
- **THEN** `.is_ordered()` on the returned stream returns `False`

#### Scenario: unordered() returns a distinct instance and consumes the receiver
- **WHEN** `s2 = s.unordered()` is called on a stream `s`
- **THEN** `s2 is not s`, and any subsequent intermediate or terminal call on
  `s` raises `IllegalStateException`

#### Scenario: unordered() chains with other intermediate operations
- **WHEN** a fluent chain such as
  `Stream.of([1, 2, 3, 4]).unordered().filter(g).collect(to_list())` is awaited
- **THEN** it produces the same elements it would without the `.unordered()`
  call

#### Scenario: unordered() does not change which elements are produced
- **WHEN** a pipeline is awaited with `.unordered()` queued at any position and
  again with it removed
- **THEN** both produce the same elements, subject only to the ordering
  guarantees the terminal operation itself makes

### Requirement: sorted() restores encounter order downstream
`Stream.sorted()` SHALL set the ordering characteristic for everything queued
after it, restoring it even when a preceding operation cleared it, matching
Java's `SortedOps` contribution of `IS_ORDERED`. A sort imposes an encounter
order on its output regardless of whether its input had one, so declaring a
stream unordered SHALL NOT be treated as permanently sticky across a
subsequent sort.

#### Scenario: sorted() after unordered() is ordered again
- **WHEN** `.unordered()` is queued on a stream, followed by `.sorted(c)`
- **THEN** `.is_ordered()` returns `True`

#### Scenario: unordered() after sorted() is unordered
- **WHEN** `.sorted(c)` is queued on a stream, followed by `.unordered()`
- **THEN** `.is_ordered()` returns `False`

#### Scenario: A sorted parallel pipeline yields its true first element
- **WHEN** `.parallel()`, `.unordered()` and `.sorted(c)` are queued on a
  stream built from a source whose smallest element under `c` arrives last, and
  `.find_first()` is awaited
- **THEN** the smallest element under `c` is returned, not an element that
  merely arrived early

## MODIFIED Requirements

### Requirement: The ordering flag survives sequential()/parallel() mode switches
`Stream.sequential()` and `Stream.parallel()` SHALL leave the ordering
characteristic of the pipeline unchanged. Because a mode switch carries the
receiver's queued chain onto the new instance without composing it, and because
ordering is derived from that chain, the characteristic survives a mode switch
without being copied as separate state.

The two concerns SHALL remain independent: the executor determines *how* a
pipeline runs, the ordering characteristic determines *whether the caller
requires encounter order*.

#### Scenario: unordered() survives a parallel() switch
- **WHEN** `.unordered()` is called on a sequential stream, followed by
  `.parallel()`
- **THEN** the resulting stream's `.is_ordered()` returns `False`

#### Scenario: unordered() survives a sequential() switch
- **WHEN** `.unordered()` is called on a parallel stream, followed by
  `.sequential()`
- **THEN** the resulting stream's `.is_ordered()` returns `False`

#### Scenario: An ordered stream stays ordered across a mode switch
- **WHEN** `.parallel()` (or `.sequential()`) is called on a stream on which
  `.unordered()` was never called
- **THEN** the resulting instance's `.is_ordered()` still returns `True`

#### Scenario: A mode switch is position-independent where unordered() is not
- **WHEN** `.parallel()` is declared before an operation and, in a second
  pipeline, after that same operation
- **THEN** both pipelines run that operation under the racing executor, whereas
  moving `.unordered()` across an operation does change which side of the
  ordering boundary that operation falls on

## REMOVED Requirements

### Requirement: Stream tracks an ordered/unordered flag defaulting to ordered
**Reason**: The requirement mandated per-instance state (a flag carried on the
`Stream` object and defaulting to `True` at construction), which is precisely
what made ordering apply to the whole pipeline regardless of where
`unordered()` was written. Ordering is now derived from the queued chain.

**Migration**: `is_ordered()` is unchanged as public API and still returns
`True` for a freshly constructed stream; that guarantee now lives in the
"Ordering is derived from the stream's queued operations" requirement above.
No caller of `is_ordered()` needs to change.

### Requirement: unordered() marks the stream as not order-dependent
**Reason**: The requirement mandated the mutate-and-return-`self` convention
("SHALL set the instance's ordering flag to `False` and return `self`"), which
only made sense while ordering was per-instance state with no chain element to
append. Now that `unordered()` queues an operation, it is an ordinary
intermediate operation and derives-and-consumes like the other eight.

**Migration**: The fluent form `Stream.of(x).unordered().filter(...)` is
unaffected. A caller that bound the receiver to a name and reused it after
calling `.unordered()` on it SHALL use the returned instance instead; the
superseded reference now raises `IllegalStateException`, as it already does for
every other intermediate operation. Replaced by the "unordered() queues an
ordering-clearing operation" requirement above.

## Purpose

Defines the contract for `Stream`'s ordered/unordered bookkeeping: how the
encounter-order characteristic is derived, `unordered()` and `sorted()`'s
restoration of it, mirroring Java's `BaseStream.unordered()` and
`StreamOpFlag.ORDERED`. Ordering is a **positional characteristic of the queued
chain**, not per-instance state: an operation clears it, sets it, or preserves
what came before, and the characteristic is the fold of those answers. That is
what makes it the deliberate opposite of `sequential()`/`parallel()`, which are
position-independent because they select an executor for the whole pipeline
rather than occupying a position in it.

The characteristic is **not public API**, matching Java, which exposes
`isParallel()` and keeps `ORDERED` in the package-private `StreamOpFlag`. A
caller influences it through `unordered()` and `sorted()`, and observes it
through what the order-sensitive operations built on it — `for_each_ordered()` —
do. It must therefore be tracked correctly and survive `sequential()`/
`parallel()` mode switches.

## Requirements

### Requirement: The ordering flag survives sequential()/parallel() mode switches
`Stream.sequential()` and `Stream.parallel()` SHALL leave the ordering
characteristic of the pipeline unchanged. Because a mode switch carries the
receiver's queued chain onto the new instance without composing it, and because
ordering is derived from that chain, the characteristic survives a mode switch
without being copied as separate state.

The two concerns SHALL remain independent: the executor determines *how* a
pipeline runs, the ordering characteristic determines *whether the caller
requires encounter order*.

Survival across a mode switch has no behavioural observable of its own — every
terminal that consults ordering does so at the end of a pipeline, by which point
the switch and the characteristic are indistinguishable from any other pipeline
with the same chain and executor. These scenarios therefore assert on the
internal accessor deliberately, as the sole exception in this capability: the
alternative is leaving the rule unpinned, and it is the rule whose earlier
violation produced a wrong answer.

#### Scenario: unordered() survives a parallel() switch
- **WHEN** `.unordered()` is called on a sequential stream, followed by
  `.parallel()`
- **THEN** the internal accessor reports the resulting stream unordered

#### Scenario: unordered() survives a sequential() switch
- **WHEN** `.unordered()` is called on a parallel stream, followed by
  `.sequential()`
- **THEN** the internal accessor reports the resulting stream unordered

#### Scenario: An ordered stream stays ordered across a mode switch
- **WHEN** `.parallel()` (or `.sequential()`) is called on a stream on which
  `.unordered()` was never called
- **THEN** the internal accessor still reports the resulting instance ordered

#### Scenario: A mode switch is position-independent where unordered() is not
- **WHEN** `.parallel()` is declared before an operation and, in a second
  pipeline, after that same operation
- **THEN** both pipelines run that operation under the racing executor, whereas
  moving `.unordered()` across an operation does change which side of the
  ordering boundary that operation falls on

### Requirement: Ordering is derived from the stream's queued operations
A stream's ordered/unordered characteristic SHALL be derived from the
operations queued on it, not from per-instance state set independently of the
chain. Each queued operation SHALL either preserve the ordering characteristic
of everything before it (the behaviour of `map`, `filter`, `flat_map`, `peek`,
`distinct`, `limit` and `skip`), clear it, or set it. The characteristic SHALL
be the result of applying those operations in the order they were queued,
starting from ordered.

This makes the characteristic **positional**: an operation declared before an
ordering-clearing operation is unaffected by it, and an operation declared
after it is. This is deliberately the opposite of `sequential()`/`parallel()`,
which are position-independent because they select an executor for the whole
pipeline rather than occupying a position in it.

Being derived rather than stored SHALL be observable: two pipelines carrying the
same queued operations behave identically with respect to ordering, whatever
each stream's construction history.

#### Scenario: A stream with no ordering operations queued is ordered
- **WHEN** a stream carrying only order-preserving operations such as `.map()`
  and `.filter()` is run under `.parallel()` and a terminal that honours
  encounter order is awaited
- **THEN** it observes elements in the source's encounter order

#### Scenario: Clearing ordering affects only what follows it
- **WHEN** a pipeline queues an order-preserving operation, then `.unordered()`,
  then a second order-preserving operation
- **THEN** the operations queued before `.unordered()` are still applied exactly
  as they were, unchanged in behaviour and position, and the pipeline carries no
  encounter-order requirement downstream of the `.unordered()`

#### Scenario: Ordering is not carried between unrelated streams
- **WHEN** `.unordered()` is called on one stream
- **THEN** a separately constructed stream is unaffected and still carries an
  encounter-order requirement

### Requirement: unordered() queues an ordering-clearing operation
`Stream.unordered()` SHALL queue an operation that clears the ordering
characteristic for everything after it, and SHALL return a new `Stream`
instance carrying the extended chain, invalidating the receiver in the same way
every other intermediate operation does (see the `pipeline-immutability`
capability). It SHALL NOT mutate and return the receiver.

The queued operation SHALL be an identity operation: it SHALL NOT observe,
transform, reorder, drop or duplicate any element, and its only effect SHALL be
on the ordering characteristic.

#### Scenario: unordered() clears the encounter-order requirement
- **WHEN** `.unordered()` is called on a stream and a terminal that relaxes
  under an unordered pipeline is awaited
- **THEN** that terminal takes its relaxed path, which it would not have taken
  on the same pipeline without the `.unordered()` call

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

This requirement's scenarios SHALL be behavioural. They previously asserted on
the internal accessor because observing the rule requires a sort running under
the racing executor, and that path gave a wrong answer in its own right: a sort
was order-blind there, so a sort under the racing executor was indistinguishable
from an unordered one and a behavioural assertion would have pinned the defect
rather than the rule. With order-sensitive operations honouring encounter order
under the racing executor (see the `racing-encounter-order` capability), the
distinction is observable and the exemption is withdrawn. The mode-switch
requirement's accessor assertions are unaffected: their reason is structural,
not temporary, and they remain the sole exception in this capability.

The rule SHALL be observable in the ordinary way — through what an operation
downstream of the sort selects, and through whether a downstream operation
forfeits concurrency. It SHALL NOT be pinned only by an assertion on internal
state.

#### Scenario: A sorted parallel pipeline yields its true first element
- **WHEN** `.parallel()`, `.unordered()` and `.sorted(c)` are queued on a
  stream built from a source whose smallest element under `c` arrives last, and
  `.find_first()` is awaited
- **THEN** the smallest element under `c` is returned, not an element that
  merely arrived early

#### Scenario: sorted() after unordered() is ordered again
- **WHEN** `.unordered()` is queued on a parallel stream, followed by
  `.sorted(c)` and then an operation whose result depends on encounter order,
  such as `.limit(3)`
- **THEN** that operation selects on the sorted encounter order — the three
  smallest elements under `c` — which it could not do if the sort had left the
  pipeline unordered

#### Scenario: unordered() after sorted() is unordered
- **WHEN** `.sorted(c)` is queued on a parallel stream, followed by
  `.unordered()`, over a chain whose steps complete out of encounter order
- **THEN** the pipeline takes the order-blind path downstream of the
  `.unordered()`, keeping the concurrency the caller asked for rather than
  delivering in the sorted order

#### Scenario: An operation queued after a sort keeps the restored characteristic
- **WHEN** `.unordered()` is queued on a parallel stream, followed by
  `.sorted(c)`, then an order-preserving operation such as `.map()`, and then an
  order-sensitive operation
- **THEN** the order-sensitive operation honours the sorted encounter order,
  showing the restored characteristic survived the intervening operation

### Requirement: The ordering characteristic is not part of the public API
A `Stream` SHALL NOT expose the ordering characteristic as public API. Java's
`BaseStream` exposes exactly one piece of pipeline introspection, `isParallel()`;
the ordering characteristic lives in the package-private `StreamOpFlag.ORDERED`
and is never readable by a caller. The public surface here SHALL match: a caller
influences ordering through `unordered()` and `sorted()`, and observes it only
through what order-sensitive operations do.

The characteristic SHALL remain readable internally, under a name marked private
by the leading-underscore convention, because the operations that honour
encounter order need to branch on it.

#### Scenario: The public accessor is gone
- **WHEN** a caller accesses `.is_ordered` on any `Stream`
- **THEN** `AttributeError` is raised, on the same rule that makes any other
  undefined attribute an error

#### Scenario: The characteristic is still derivable internally
- **WHEN** the internal accessor is called on a pipeline with an
  ordering-clearing operation queued and no later ordering-setting operation
- **THEN** it reports the pipeline as unordered, unchanged in every respect
  except its name

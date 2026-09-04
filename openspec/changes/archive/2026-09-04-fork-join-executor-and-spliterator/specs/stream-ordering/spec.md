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
- **THEN** both pipelines run that operation under the fork-join executor,
  whereas moving `.unordered()` across an operation does change which side of
  the ordering boundary that operation falls on

### Requirement: sorted() restores encounter order downstream
`Stream.sorted()` SHALL set the ordering characteristic for everything queued
after it, restoring it even when a preceding operation cleared it, matching
Java's `SortedOps` contribution of `IS_ORDERED`. A sort imposes an encounter
order on its output regardless of whether its input had one, so declaring a
stream unordered SHALL NOT be treated as permanently sticky across a
subsequent sort.

This requirement's scenarios SHALL be behavioural. They previously asserted on
the internal accessor because observing the rule requires a sort running under
a parallel executor, and that path gave a wrong answer in its own right: a sort
was order-blind there, so a sort under the parallel executor was
indistinguishable from an unordered one and a behavioural assertion would have
pinned the defect rather than the rule. With order-sensitive operations
honouring encounter order under the fork-join executor (see the
`racing-encounter-order` capability), the distinction is observable and the
exemption is withdrawn. The mode-switch requirement's accessor assertions are
unaffected: their reason is structural, not temporary, and they remain the
sole exception in this capability.

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

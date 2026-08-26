## MODIFIED Requirements

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

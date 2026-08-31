## MODIFIED Requirements

### Requirement: A racing pipeline delivers in encounter order when its terminal observes it

Where a terminal operation observes the encounter order of the elements it
receives, and the pipeline carries an encounter-order requirement at the end of
the chain, the racing executor SHALL deliver elements to that terminal in
encounter order. The result SHALL equal the result the same pipeline produces
under the sequential executor.

This SHALL hold whether or not the chain contains an order-sensitive operation:
a chain of only `map`, `filter`, `peek` and `flat_map` delivers in encounter
order under `.parallel()` exactly as one containing `sorted()` does.

A terminal operation SHALL declare whether it observes encounter order:

- `collect(collector)` observes it unless the collector declares
  `Characteristics.UNORDERED`.
- `collect(supplier, accumulator, combiner)`, `reduce()`, `to_array()`,
  `collect(to_generator)` and `iterator()` observe it.
- `for_each_ordered()` observes it. Its encounter-order guarantee is exactly
  this requirement applied to a consumer rather than to a collected result, and
  it is released on an unordered pipeline for exactly the reason every other
  entry in this list is; see the `stream-foreach-ordered` capability.
- `max()` and `min()` observe it. Their *value* is the same in any order, but
  which of two equal-comparing distinguishable elements they return is not, and
  `comparator-contract` requires the first in encounter order. They take the
  cheapest split there is — at `len(chain)`, so every operation still races and
  only delivery is ordered — and `unordered()` releases them from it.
- `count()`, `for_each()`, `find_any()`, `all_match()`, `any_match()` and
  `none_match()` do NOT observe it and SHALL pay nothing for this requirement —
  neither reorder buffering nor head-of-line delay.
- `find_first()` observes it **unconditionally**. It is the only terminal whose
  demand survives `unordered()`: the barrier can always restore encounter order,
  because the source index is assigned at the point elements are pulled and
  `unordered()` clears the ordering *requirement* rather than the ability to
  meet it. See the `stream-find-first` capability.

A terminal's declaration is therefore three-valued — it does not observe
encounter order, it observes it where the pipeline is ordered, or it observes it
unconditionally — mirroring the two ways an *operation* can need order restored
before it: `sorted()` needs it wherever it sits, while `limit`, `skip` and
`distinct` need it only at a position where the pipeline is ordered.

Restoring order for delivery SHALL NOT serialize the chain. Every operation in
the chain SHALL still run across all branches concurrently; only the handing of
finished elements to the terminal is ordered.

#### Scenario: An ordered racing map/filter pipeline collects in encounter order
- **WHEN** a stream over `range(50)` queues a mapping operation with variable
  per-element cost and is run under `.parallel()` and collected with
  `to_list()`
- **THEN** the result is the mapped elements in source order, equal to the
  sequential pipeline's result

#### Scenario: Delivery ordering does not serialize the chain
- **WHEN** an ordered racing pipeline whose mapping operation sleeps per element
  is collected with `to_list()`
- **THEN** it completes in substantially less wall-clock time than the
  sequential pipeline over the same source, because the mapping still runs
  across all branches concurrently

#### Scenario: for_each_ordered takes the delivery barrier like any other observer
- **WHEN** an ordered racing pipeline whose mapping operation sleeps per element
  is drained with `for_each_ordered(consumer)`
- **THEN** the consumer is invoked in encounter order, and the call completes in
  substantially less wall-clock time than the sequential pipeline over the same
  source

#### Scenario: reduce() over an ordered racing pipeline folds in encounter order
- **WHEN** `.parallel()` is used with a non-commutative accumulator, for
  instance folding elements into a string
- **THEN** the result equals the sequential fold

#### Scenario: An ordered racing max() breaks ties in encounter order
- **WHEN** `max()` or `min()` is awaited on an ordered racing pipeline over
  records whose comparator keys tie
- **THEN** the result is the tied record earliest in encounter order, equal to
  the sequential pipeline's result

#### Scenario: An order-blind terminal pays nothing
- **WHEN** `count()`, `for_each()`, `any_match()` or `find_any()` is called on
  an ordered racing pipeline
- **THEN** no element is held back waiting for an earlier one, and the pipeline
  behaves exactly as it does without this requirement

#### Scenario: An UNORDERED collector takes the order-blind path
- **WHEN** an ordered racing pipeline is collected with `to_set()`, which
  declares `Characteristics.UNORDERED`
- **THEN** no delivery barrier is engaged, and the collected set is correct

#### Scenario: An unconditional observer is not released by unordered()
- **WHEN** `.parallel().unordered().map(f).find_first()` is awaited on a chain
  whose elements complete out of encounter order
- **THEN** the delivery barrier is engaged despite the cleared ordering
  characteristic, and the first element in the source's encounter order is
  returned

#### Scenario: An unconditional observer still races its chain
- **WHEN** `.parallel().filter(p).find_first()` is awaited on a source whose
  first several elements fail an expensive `p`
- **THEN** the correct element is returned, and `p` runs across all branches
  concurrently rather than one element at a time

#### Scenario: An unordered pipeline delivers unordered
- **WHEN** `.parallel().unordered().map(f).collect(to_list())` is run
- **THEN** elements may arrive in any order, no delivery barrier is engaged, and
  the collected list is the mapped elements as a multiset

#### Scenario: An unordered for_each_ordered delivers unordered
- **WHEN** `.parallel().unordered().map(f).for_each_ordered(consumer)` is awaited
- **THEN** no delivery barrier is engaged, the consumer receives every element
  exactly once, and it may receive them in any order

#### Scenario: unordered() after an order-sensitive operation still clears delivery
- **WHEN** `.parallel().limit(5).unordered().map(f).collect(to_list())` is run
- **THEN** `limit(5)` still selects the first five in encounter order, and
  delivery of the mapped results carries no ordering guarantee

## REMOVED Requirements

### Requirement: A terminal uses the stream's executor unless it names one, and find_first() always names one
**Reason**: `for_each_ordered()` stops naming an executor, so the requirement's
list of which terminals name one changes, and its scenario "for_each_ordered
ignores the stream's executor when ordered" asserts the exact behaviour being
removed. Restated below with `find_first()` as the only terminal that names an
executor.

**Migration**: `for_each_ordered()` still invokes its consumer in encounter
order on an ordered pipeline. What changes is that the chain producing those
elements now races; see the `stream-foreach-ordered` capability.

## ADDED Requirements

### Requirement: A terminal uses the stream's executor unless it names one, and only find_first() names one

A terminal operation SHALL execute under the executor its stream carries.

A terminal operation SHALL additionally declare whether it observes the
encounter order of the elements it receives. This is a second, independent axis
alongside which executor it names: the executor decides *how* the chain runs,
the declaration decides whether the executor must deliver in encounter order
(see the `racing-encounter-order` capability). Under the sequential executor the
declaration changes nothing.

`count()`, `for_each()`, `find_any()`, `max()`, `min()`, `all_match()`,
`any_match()` and `none_match()` SHALL declare that they do not observe it.
`reduce()`, `to_array()`, `for_each_ordered()` and the three-argument
`collect(supplier, accumulator, combiner)` SHALL declare that they do.
`collect(collector)` SHALL derive its declaration from the collector: it
observes encounter order unless the collector declares
`Characteristics.UNORDERED`.

A terminal operation whose contract requires encounter order regardless of the
stream's mode SHALL name the sequential executor explicitly at its call site,
rather than relying on a shared implementation that is promised never to be
overridden.

`find_first()` SHALL do this **unconditionally**, without consulting the
ordering characteristic. Java does not relax `findFirst()` on an unordered
stream either: `FindOp.mustFindFirst` is fixed when the operation is
constructed, and the leftmost scan runs whenever it is set. The javadoc permits
returning any element there; the implementation declines to, and so does this
one. `find_any()` is where a caller who wants the race goes.

`for_each_ordered()` SHALL NOT do this. Its encounter-order guarantee is
satisfied by the delivery barrier the racing executor already provides to every
order-observing terminal, so it declares that it observes encounter order and
otherwise follows the stream's own executor in both the ordered and the
unordered case; see the `stream-foreach-ordered` capability.

#### Scenario: An ordinary terminal follows the stream's executor
- **WHEN** `count()` is called on a parallel stream
- **THEN** the chain is driven under the racing executor

#### Scenario: An order-blind terminal declares so
- **WHEN** `count()`, `for_each()`, `any_match()` or `find_any()` is called on an
  ordered parallel stream
- **THEN** no reorder barrier is engaged and no element is held back waiting for
  an earlier one

#### Scenario: An order-observing terminal declares so
- **WHEN** `reduce()`, `to_array()` or `collect(to_list())` is called on an
  ordered parallel stream
- **THEN** elements reach the terminal in encounter order

#### Scenario: collect() takes its declaration from the collector
- **WHEN** the same ordered parallel stream is collected with `to_list()` and
  with `to_set()`, which declares `Characteristics.UNORDERED`
- **THEN** the `to_list()` collection engages the reorder barrier and the
  `to_set()` collection does not

#### Scenario: for_each_ordered follows the stream's executor when ordered
- **WHEN** `for_each_ordered(consumer)` is called on an ordered parallel stream
- **THEN** the chain is driven under the racing executor, the reorder barrier is
  engaged, and the consumer is invoked in encounter order

#### Scenario: for_each_ordered follows the stream's executor when unordered
- **WHEN** `for_each_ordered(consumer)` is called on a parallel stream marked
  `unordered()`
- **THEN** the chain is driven under the racing executor with no reorder barrier
  engaged, and the consumer is invoked once per element

#### Scenario: find_first on an ordered parallel stream ignores the stream's executor
- **WHEN** `find_first()` is called on an ordered parallel stream
- **THEN** the chain is driven under the sequential executor and the true first
  element in encounter order is returned

#### Scenario: find_first on an unordered stream still forces sequential
- **WHEN** `find_first()` is called on a stream marked `unordered()`
- **THEN** it still runs under the sequential executor and returns the first
  element in the source's encounter order, rather than behaving as `find_any()`

#### Scenario: find_any remains the unordered alternative
- **WHEN** `find_any()` is called on a parallel stream
- **THEN** it runs under the stream's own executor and may return any element

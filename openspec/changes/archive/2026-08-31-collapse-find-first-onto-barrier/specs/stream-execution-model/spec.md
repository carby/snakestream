## REMOVED Requirements

### Requirement: A terminal uses the stream's executor unless it names one, and only find_first() names one
**Reason**: `find_first()` was the last terminal naming an executor for itself.
With its demand moved onto the delivery barrier, no terminal names one, so the
requirement's entire second half — and the mechanism its title states — no
longer describes anything. Restated below around the declaration axis alone,
which is now the only axis a terminal controls.

**Migration**: `find_first()` returns the same element it always did, on ordered
and unordered pipelines alike. What changes is that it no longer forces the
pipeline sequential: see the `stream-find-first` capability for the two
consequences (an order-sensitive operation on an unordered chain now races, and
a chain callable may be invoked for more than one element).

## ADDED Requirements

### Requirement: A terminal follows the stream's executor and declares what it observes

A terminal operation SHALL execute under the executor its stream carries. No
terminal SHALL name an executor for itself.

A terminal operation SHALL declare whether it observes the encounter order of
the elements it receives. This is a second, independent axis alongside the
executor the stream carries: the executor decides *how* the chain runs, the
declaration decides whether the executor must deliver in encounter order (see
the `racing-encounter-order` capability). Under the sequential executor the
declaration changes nothing.

The declaration SHALL be three-valued, because a terminal's demand for
encounter order can be unconditional or conditional on the pipeline being
ordered, and a two-valued declaration cannot express the first:

- Terminals that do not observe it: `count()`, `for_each()`, `find_any()`,
  `max()`, `min()`, `all_match()`, `any_match()` and `none_match()`. They SHALL
  pay nothing — neither reorder buffering nor head-of-line delay.
- Terminals that observe it **when the pipeline is ordered**: `reduce()`,
  `to_array()`, `for_each_ordered()`, `iterator()` and the three-argument
  `collect(supplier, accumulator, combiner)`. `collect(collector)` SHALL derive
  its declaration from the collector — it observes encounter order unless the
  collector declares `Characteristics.UNORDERED`.
- Terminals that observe it **unconditionally**, whatever the pipeline's
  ordering characteristic: `find_first()`, and no other.

`find_first()`'s unconditional demand SHALL restore encounter order for
delivery only, and SHALL NOT constrain how the chain runs. Java does not relax
`findFirst()` on an unordered stream: `FindOp.mustFindFirst` is fixed when the
operation is constructed, and the leftmost scan runs whenever it is set. The
javadoc permits returning any element there; the implementation declines to, and
so does this one — and, like `FindTask`, it declines without abandoning
parallelism. `find_any()` is where a caller who wants the race goes.

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

#### Scenario: A conditional observer is released by unordered()
- **WHEN** `reduce()` or `for_each_ordered()` is called on a parallel stream
  marked `unordered()`
- **THEN** no reorder barrier is engaged

#### Scenario: find_first is not released by unordered()
- **WHEN** `find_first()` is called on a parallel stream marked `unordered()`
- **THEN** the reorder barrier is still engaged and the first element in the
  source's encounter order is returned, rather than behaving as `find_any()`

#### Scenario: find_first follows the stream's executor
- **WHEN** `find_first()` is called on a parallel stream
- **THEN** the chain is driven under the racing executor, every operation runs
  across all branches, and the true first element in encounter order is returned

#### Scenario: find_any remains the unordered alternative
- **WHEN** `find_any()` is called on a parallel stream
- **THEN** it runs under the stream's own executor and may return any element

## MODIFIED Requirements

### Requirement: The executor protocol has exactly two operations

An executor SHALL expose exactly two operations over a chain and a source: one
producing an `AsyncGenerator` of the chain's output elements, and one driving
the chain into a terminal sink and returning that sink's result.

The element-producing operation SHALL be the one used by `iterator()`,
`collect(to_generator)`, `Stream.concat()` and the mode switches. The
terminal-driving operation SHALL be the one used by every other terminal
operation.

The terminal-driving operation SHALL have a single generic implementation —
driving the element-producing operation's output into the terminal — which the
racing executor uses unchanged. The sequential executor MAY override it with a
fused implementation that pushes source elements through the chain straight into
the terminal with nothing buffered on the way; that override SHALL be a
performance specialization only, producing results indistinguishable from the
generic implementation.

An executor's element-producing operation MAY internally run different parts of
the chain differently — for instance racing the operations upstream of an
ordering barrier while running those downstream of it in a single ordered pass
(see the `racing-encounter-order` capability). Such an internal split SHALL NOT
constitute a third executor, SHALL NOT be selectable or observable as a mode,
and SHALL leave `is_parallel()` reporting the executor the stream carries.

#### Scenario: Both executors produce the same elements
- **WHEN** the same chain over the same source is composed to a generator under
  the sequential executor and under the racing executor
- **THEN** both yield the same elements, subject only to the ordering guarantee
  each mode already gives

#### Scenario: The fused override is indistinguishable from the generic form
- **WHEN** a terminal operation is driven under the sequential executor
- **THEN** its result equals what driving the composed generator into the same
  terminal sink would have produced

#### Scenario: An internal ordering barrier is not a mode
- **WHEN** a racing pipeline containing an order-sensitive operation on an
  ordered chain is run, so that part of the chain runs in a single ordered pass
- **THEN** `is_parallel()` still reports `True`, and there are still exactly two
  executor values in the package

## REMOVED Requirements

### Requirement: A terminal uses the stream's executor unless it names one
**Reason**: One of its scenarios states a rule the implementation has never
followed. "find_first on an unordered stream does not force sequential" says
`find_first()` behaves as `find_any()` on an unordered pipeline; `find_first()`
has named the sequential executor unconditionally since
`make-ordering-a-chain-characteristic`, `tests/test_find_first.py` pins that,
and `find_first()`'s own docstring argues for it from Java's
`FindOp.mustFindFirst`. A MODIFIED delta replaces a requirement block whole and
would have carried the wrong scenario forward, so the requirement is removed and
replaced by the one below with the rule corrected.

**Migration**: None for callers — no behaviour changes. The replacement
requirement, "A terminal uses the stream's executor unless it names one, and
find_first() always names one", carries every other scenario forward unchanged.

## ADDED Requirements

### Requirement: A terminal uses the stream's executor unless it names one, and find_first() always names one

A terminal operation SHALL execute under the executor its stream carries.

A terminal operation whose contract requires encounter order regardless of the
stream's mode SHALL name the sequential executor explicitly at its call site,
rather than relying on a shared implementation that is promised never to be
overridden.

`for_each_ordered()` SHALL do this when the pipeline is ordered, and SHALL
otherwise run under the stream's own executor, per the `stream-foreach-ordered`
capability.

`find_first()` SHALL do this **unconditionally**, without consulting the
ordering characteristic. Java does not relax `findFirst()` on an unordered
stream either: `FindOp.mustFindFirst` is fixed when the operation is
constructed, and the leftmost scan runs whenever it is set. The javadoc permits
returning any element there; the implementation declines to, and so does this
one. `find_any()` is where a caller who wants the race goes.

#### Scenario: An ordinary terminal follows the stream's executor
- **WHEN** `count()` is called on a parallel stream
- **THEN** the chain is driven under the racing executor

#### Scenario: for_each_ordered ignores the stream's executor when ordered
- **WHEN** `for_each_ordered(consumer)` is called on an ordered parallel stream
- **THEN** the chain is driven under the sequential executor and the consumer is
  invoked in encounter order

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

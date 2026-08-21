## Purpose

Defines how a stream's execution mode is carried and applied: an executor value
held by the stream, a two-method executor protocol, which executor a terminal
uses, and the rule that a terminal requiring encounter order names its executor
explicitly instead of depending on the stream's.

## ADDED Requirements

### Requirement: Execution mode is a value carried by the stream

A stream SHALL hold its execution mode as a value (an executor), not as its
type. There SHALL be exactly one sequential executor and one racing executor,
and a stream SHALL carry exactly one of them at any time. No stream subclass
SHALL exist for the purpose of encoding execution mode.

`is_parallel()` SHALL report the mode from that value.

#### Scenario: A sequentially-built stream reports sequential
- **WHEN** `Stream.of([1, 2, 3]).is_parallel()` is called
- **THEN** the result is `False`

#### Scenario: A parallel stream reports parallel
- **WHEN** `Stream.of([1, 2, 3]).parallel().is_parallel()` is called
- **THEN** the result is `True`

#### Scenario: Intermediate operations carry the executor forward
- **WHEN** an intermediate operation is called on a parallel stream
- **THEN** the returned stream reports `is_parallel()` as `True`

#### Scenario: A user subclass survives a mode switch
- **WHEN** `.parallel()` and then `.sequential()` are called on an instance of a
  user-defined `class MyStream(Stream)`
- **THEN** each returned instance is a `MyStream`, not a plain `Stream`, matching
  how intermediate operations already preserve subclass identity

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

#### Scenario: Both executors produce the same elements
- **WHEN** the same chain over the same source is composed to a generator under
  the sequential executor and under the racing executor
- **THEN** both yield the same elements, subject only to the ordering guarantee
  each mode already gives

#### Scenario: The fused override is indistinguishable from the generic form
- **WHEN** a terminal operation is driven under the sequential executor
- **THEN** its result equals what driving the composed generator into the same
  terminal sink would have produced

### Requirement: A terminal uses the stream's executor unless it names one

A terminal operation SHALL execute under the executor its stream carries.

A terminal operation whose contract requires encounter order regardless of the
stream's mode SHALL name the sequential executor explicitly at its call site,
rather than relying on a shared implementation that is promised never to be
overridden. `for_each_ordered()` SHALL do this unconditionally.
`find_first()` SHALL do this when the stream is ordered, and SHALL otherwise
behave as `find_any()`.

#### Scenario: An ordinary terminal follows the stream's executor
- **WHEN** `count()` is called on a parallel stream
- **THEN** the chain is driven under the racing executor

#### Scenario: for_each_ordered ignores the stream's executor
- **WHEN** `for_each_ordered(consumer)` is called on a parallel stream
- **THEN** the chain is driven under the sequential executor and the consumer is
  invoked in encounter order

#### Scenario: find_first on an ordered parallel stream ignores the stream's executor
- **WHEN** `find_first()` is called on an ordered parallel stream
- **THEN** the chain is driven under the sequential executor and the true first
  element in encounter order is returned

#### Scenario: find_first on an unordered stream does not force sequential
- **WHEN** `find_first()` is called on a stream marked `unordered()`
- **THEN** it behaves as `find_any()`, under the stream's own executor

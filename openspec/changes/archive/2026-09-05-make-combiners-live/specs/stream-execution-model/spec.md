## MODIFIED Requirements

### Requirement: The executor protocol has exactly two operations

An executor SHALL expose exactly two operations over a chain and a source: one
producing an `AsyncGenerator` of the chain's output elements, and one driving
the chain into a terminal sink and returning that sink's result.

Both operations SHALL accept, alongside the chain and the source, the caller's
declaration of whether the consumer observes encounter order. The
element-producing operation's consumer is whoever iterates the generator and
always observes it; the terminal-driving operation's consumer is the terminal
sink, which declares for itself. An executor for which the declaration makes no
difference — the sequential one, which is ordered by construction — SHALL accept
it and ignore it.

The element-producing operation SHALL be the one used by `iterator()`,
`collect(to_generator)`, `Stream.concat()` and the mode switches. The
terminal-driving operation SHALL be the one used by every other terminal
operation.

The terminal-driving operation SHALL have a single generic implementation —
driving the element-producing operation's output into the terminal. The
sequential executor MAY override it with a fused implementation that pushes
source elements through the chain straight into the terminal with nothing
buffered on the way; that override SHALL be a performance specialization
only, producing results indistinguishable from the generic implementation.

The fork-join executor SHALL use the generic form for a terminal sink that
does not opt into the partition protocol (`sink-protocol`), or for one that
does but whose chain contains an op needing a global view (`sorted()`, or
`limit`/`skip`/`distinct` on an ordered pipeline) — each batch there still
builds and runs its own sink chain on its own OS thread, torn down once the
batch finishes, so there is no single, long-lived chain instance such a
terminal could be fused onto. For a terminal that opts in and whose chain
needs no global view, the fork-join executor SHALL instead accumulate each
batch into its own peer container on its own thread and merge the peers into
the terminal in batch order (`parallel-reduction`) — the override the
`Collector` combiner and the three-argument `reduce()`'s combiner drive, now
that both are live. This is the second executor-level override alongside the
sequential executor's fused form, not a third executor and not a change to
which two operations the protocol exposes.

An executor's element-producing operation MAY internally run different parts of
the chain differently — for instance running batches concurrently upstream of
an ordering barrier while running the barrier operation itself in a single
ordered pass and running everything after it concurrently again, or reordering
only the delivery of a chain that ran concurrently end to end (see the
`racing-encounter-order` capability). Such an internal split SHALL NOT
constitute a third executor, SHALL NOT be selectable or observable as a mode,
and SHALL leave `is_parallel()` reporting the executor the stream carries. The
terminal-driving operation's own partitioned override is likewise not a third
executor, for the same reason: it is not selectable, and `is_parallel()`
still reports the executor the stream carries.

#### Scenario: Both executors produce the same elements
- **WHEN** the same chain over the same source is composed to a generator under
  the sequential executor and under the fork-join executor
- **THEN** both yield the same elements, subject only to the ordering guarantee
  each mode already gives

#### Scenario: The fused override is indistinguishable from the generic form
- **WHEN** a terminal operation is driven under the sequential executor
- **THEN** its result equals what driving the composed generator into the same
  terminal sink would have produced

#### Scenario: The sequential executor ignores the ordering declaration
- **WHEN** a chain is run under the sequential executor with the consumer
  declaring that it observes encounter order, and again declaring that it does
  not
- **THEN** both runs produce identical results, in encounter order

#### Scenario: An internal ordering barrier is not a mode
- **WHEN** a parallel pipeline containing an order-sensitive operation on an
  ordered chain is run, so that part of the chain runs in a single ordered pass
- **THEN** `is_parallel()` still reports `True`, and there are still exactly two
  executor values in the package

#### Scenario: A delivery barrier is not a mode either
- **WHEN** an ordered parallel pipeline with no order-sensitive operation is
  collected by an order-observing terminal, so that delivery is reordered
- **THEN** `is_parallel()` still reports `True`, and there are still exactly two
  executor values in the package

#### Scenario: A non-partitioning terminal still drives through the generic form
- **WHEN** a terminal whose `can_partition()` is `False` is driven under the fork-join executor
- **THEN** it drives through the generic compose-then-drain form, exactly as before this requirement changed

#### Scenario: A partitioning override is not a third executor
- **WHEN** a `Collector` supplying a `combiner` is driven under the fork-join executor via its partitioned override
- **THEN** `is_parallel()` still reports `True`, and there are still exactly two executor values in the package

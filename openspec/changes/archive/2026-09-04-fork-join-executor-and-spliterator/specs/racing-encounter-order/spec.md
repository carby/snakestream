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
  `none_match()` do NOT observe it and SHALL pay nothing for this requirement in
  the general case — neither reorder buffering nor head-of-line delay against
  an *earlier* element. **A short-circuiting one of these** (`find_any()`,
  `any_match()`, `none_match()`) is subject to the same bounded exception the
  read-ahead requirement below now documents: under
  `fork-join-executor-and-spliterator`'s executor, such a terminal may still be
  delayed by a slow *unrelated* element sharing its own batch with the one that
  satisfies it — never by an earlier one, and never unboundedly.
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
- **THEN** no element is held back waiting for an *earlier* one, and the
  pipeline behaves exactly as it does without this requirement, subject to the
  bounded same-batch exception documented under the read-ahead requirement

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

### Requirement: The read-ahead bound is not part of the public surface

The value of the read-ahead window SHALL NOT be exported from the package, and
no public name SHALL be provided for reading or setting it. The bound is a
guarantee of finiteness, not a tunable: a caller relies on it being bounded, not
on what it is bounded to, and the value SHALL remain free to change on
measurement without that being a breaking change.

The levers offered to a caller for the cost the window implies SHALL be
`unordered()`, which removes the ordering requirement and with it the barrier
entirely, and `sequential()`, which removes the race. This mirrors the treatment
of every other bound whose effect is observable but whose mechanism is not
selectable — `find_any()`'s choice of element is observable and specified, and
is likewise not exposed as a setting.

`WORKERS` SHALL remain exported and is unaffected by this requirement; it
names a concept with a Java counterpart, while the read-ahead window does not.

#### Scenario: No public name exposes the bound
- **WHEN** a caller inspects the names exported by the `snakestream` package
- **THEN** no name is provided that reads or sets the read-ahead window, and the
  documented means of avoiding its cost are `unordered()` and `sequential()`

#### Scenario: The bound may be retuned without a breaking change
- **WHEN** the read-ahead window's value is changed on measurement
- **THEN** every requirement of this capability continues to hold unchanged, and
  no caller-visible contract is broken by the new value

### Requirement: An unordered pipeline takes the order-blind path

Where the pipeline carries no encounter-order requirement at an order-sensitive
operation's position, that operation SHALL take the order-blind path: `limit(n)`
yields the first `n` elements to arrive across all branches in whatever order
the race resolves them, `skip(n)` drops the first `n` to arrive, and
`distinct()` keeps an arbitrary representative of each equal group. These SHALL
remain valid results — `unordered()` is the caller declaring that any of them
will do.

`sorted()` is the exception and SHALL NOT take this path. A sort claims its
output is ordered, so it SHALL see the whole stream in encounter order wherever
it sits, regardless of the ordering characteristic at its own position; a sort
left in the raced head would sort each branch's subset. Its output is therefore
ordered, and stable, on an unordered pipeline as on an ordered one — see
`comparator-contract`.

Where the pipeline carries no encounter-order requirement at the *end of the
chain*, delivery to the terminal SHALL likewise be order-blind: no reorder
barrier is engaged, whatever the terminal declares about observing order. This
covers `max()`/`min()`, which observe encounter order on an ordered pipeline and
release it here.

No ordering machinery SHALL be engaged on such a pipeline: the per-element cost
and the memory profile of an unordered racing pipeline SHALL be unchanged by
this capability.

`unordered()` therefore SHALL be a performance lever and not only a semantic
one: on any racing pipeline delivering to an order-observing terminal, and on
any pipeline containing an order-sensitive operation, declaring the pipeline
unordered SHALL admit concurrency that the ordered form cannot. This SHALL be
measurable, **subject to there being more than one independently-dispatched
unit of work to admit concurrency between** — a pipeline whose entire source is
processed as a single unit has nothing for `unordered()` to let race ahead of
anything else, on any executor. `fork-join-executor-and-spliterator`'s executor
dispatches contiguous batches, so this precondition is source-size-dependent
there in a way it was not under a per-element racing executor: a source larger
than one batch's worth of elements SHALL show the effect; a source that fits in
a single batch is not required to. See that change's design.md, decisions 9
and 10, for the batch boundary and the one further, genuinely new and
bounded exception this capability now carries: an order-blind,
short-circuiting terminal may still be delayed by a slow element sharing its
own batch with the one that would have satisfied it, bounded by that batch's
size — a variant of the read-ahead requirement's already-accepted over-pull
allowance below, not a new kind of claim.

#### Scenario: An unordered limit() takes the first n to arrive
- **WHEN** `.unordered()` is queued before a mapping operation with variable
  per-element cost and `.limit(5)`, under `.parallel()`
- **THEN** the result is five elements of the source, not necessarily the first
  five in encounter order, and no error is raised

#### Scenario: An unordered sort still sorts the whole stream
- **WHEN** `.parallel().unordered().sorted(c)` is collected
- **THEN** the result is every source element in the comparator's order, not a
  concatenation of per-branch sorted subsets

#### Scenario: An unordered pipeline pays no ordering cost
- **WHEN** a racing pipeline containing an order-sensitive operation is run with
  `.unordered()` queued before that operation, and again without it
- **THEN** the unordered run holds no elements back waiting for an earlier one
  and completes without the ordered run's head-of-line delay

#### Scenario: An unordered pipeline with no order-sensitive operation pays no delivery cost
- **WHEN** `.parallel().unordered().map(f).collect(to_list())` is run and again
  without the `.unordered()`, over a source spanning more than one batch
- **THEN** the unordered run engages no reorder buffer and holds no element back

#### Scenario: unordered() applies only to operations queued after it
- **WHEN** an order-sensitive operation is queued **before** `.unordered()`
- **THEN** that operation still honours encounter order, because the pipeline is
  ordered at its position

#### Scenario: sorted() re-imposes the requirement for what follows
- **WHEN** `.unordered()` is queued, then `.sorted(asc)`, then `.limit(3)`,
  under `.parallel()`
- **THEN** the `limit(3)` yields the three smallest elements under the
  comparator, because the sort restored the encounter-order requirement at that
  position

#### Scenario: An unordered max() pays no ordering cost
- **WHEN** `.parallel().unordered().max(c)` is awaited
- **THEN** no delivery barrier is engaged, no element is held back waiting for
  an earlier one, and the returned value is correct

### Requirement: Read-ahead under an ordered racing pipeline is bounded

Honouring encounter order requires holding a finished element until every
earlier element has been released. The number of elements pulled from the source
but not yet released SHALL be bounded by a fixed window, so that one slow
element cannot cause the remainder of the source to be drawn into memory.

The window SHALL scale with the number of branches the pipeline races across, so
that raising the worker count does not reduce what each branch may have in
flight. A race across more branches SHALL be given a proportionally larger
window rather than the same window divided further.

The window's size SHALL be fixed for the duration of a pipeline's execution. A
pipeline SHALL NOT observe the bound changing part-way through its own run.

This bound SHALL apply to a delivery barrier exactly as it applies to a barrier
in front of an order-sensitive operation: an ordered racing pipeline whose
terminal observes encounter order SHALL run in memory proportional to the window
and the number of branches, whatever the length of the source.

The bound SHALL hold for an unbounded or very large source: an ordered racing
pipeline over such a source SHALL run in memory proportional to the window and
the number of branches, not to the length of the source. This is subject to the
memory an operation requires by its own definition — `sorted()` buffers its
input whatever the executor — and to what the terminal itself accumulates: a
collector building a list of the whole stream holds the whole stream by its own
definition, not because of the barrier.

A consequence SHALL be accepted and is not a defect: an operation upstream of a
short-circuiting one may run on more elements than the sequential pipeline would
run it on, up to the window. A racing pipeline is permitted this over-pull where
a sequential one is not, matching the existing racing behaviour and Java's
parallel `limit()`. The elements *selected* are unaffected.

**This same allowance extends to an order-blind, short-circuiting terminal
under `fork-join-executor-and-spliterator`'s executor**, which is not itself
racing branches against a window but batches against a batch boundary: such a
terminal may be delayed by a slow element sharing its own batch with the
element that would have satisfied it, bounded by that batch's size, for the
same reason and on the same footing as the over-pull this requirement already
accepts. Which element eventually satisfies the terminal is unaffected.

#### Scenario: A slow first element does not draw the whole source into memory
- **WHEN** an ordered racing pipeline is run over a large source in which the
  first element's upstream work is far slower than every other element's
- **THEN** the number of elements pulled from the source ahead of the first
  release stays within the window, rather than growing with the source

#### Scenario: A delivery barrier over a large source is bounded too
- **WHEN** `.parallel().map(f).for_each_ordered(...)`-shaped work is replaced by
  an ordered racing pipeline with no order-sensitive operation, delivering to an
  order-observing terminal over a very large source with one slow element at the
  head
- **THEN** the elements pulled ahead of the first release stay within the window

#### Scenario: An ordered racing limit() over an unbounded source terminates
- **WHEN** `.limit(n)` is queued on an ordered racing pipeline over an infinite
  source
- **THEN** the pipeline yields exactly `n` elements, in encounter order, and
  terminates, closing the source

#### Scenario: Over-pull upstream of an ordered limit() is bounded, and selection is not affected
- **WHEN** `.peek(fn).limit(n)` is run on an ordered racing pipeline over a
  source with far more than `n` elements
- **THEN** `fn` may be called more than `n` times but not unboundedly so, and
  the elements yielded are exactly the first `n` in encounter order

#### Scenario: A wider race is given a wider window
- **WHEN** the same ordered racing pipeline is run across more branches than the
  default worker count
- **THEN** the number of elements each branch may have pulled but unreleased is
  not smaller than it is at the default worker count

#### Scenario: An order-blind terminal may be delayed by its own batch
- **WHEN** an order-blind, short-circuiting terminal (`any_match()`,
  `find_any()`) is run under `fork-join-executor-and-spliterator`'s executor
  over an unbounded source whose satisfying element shares a batch with an
  unrelated slow element
- **THEN** the terminal is delayed by at most that batch's bound, and is not
  delayed at all when the satisfying element lands in a different batch than
  the slow one

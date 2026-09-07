## MODIFIED Requirements

### Requirement: Read-ahead under an ordered racing pipeline is bounded

Honouring encounter order requires holding a finished element until every
earlier element has been released. The number of elements pulled from the source
but not yet released SHALL be bounded by a fixed window, so that one slow
element cannot cause the remainder of the source to be drawn into memory.

The window SHALL scale with the number of branches the pipeline races across, so
that raising the worker count does not reduce what each branch may have in
flight. A race across more branches SHALL be given a proportionally larger
window rather than the same window divided further.

The window SHALL have a ceiling that is fixed for the duration of a pipeline's
execution, and a pipeline SHALL NOT observe that ceiling changing part-way
through its own run. What a pipeline may observe is the window *climbing toward*
the ceiling: the amount in flight SHALL start at a small fraction of the ceiling
and grow as the pipeline consumes, so that a consumer which stops early is never
charged for a window sized for a consumer which does not. That growth SHALL be
monotone — the window never shrinks within a run — and SHALL reach the ceiling
after a number of refills that does not depend on the length of the source, so
that a draining pipeline pays for the climb once rather than in proportion to
what it consumes. The rate of the climb, its starting size and the ceiling are
all subject to the retuning allowance below.

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
run it on, up to the window *as it stands when the short-circuiting operation
settles* — not up to the ceiling. A racing pipeline is permitted this over-pull
where a sequential one is not, matching the existing racing behaviour and Java's
parallel `limit()`. The elements *selected* are unaffected.

**This same allowance extends to an order-blind, short-circuiting terminal
under `fork-join-executor-and-spliterator`'s executor**, which is not itself
racing branches against a window but batches against a batch boundary: such a
terminal may be delayed by a slow element sharing its own batch with the
element that would have satisfied it, bounded by that batch's size as the ramp
has grown it at that point, for the same reason and on the same footing as the
over-pull this requirement already accepts. Which element eventually satisfies
the terminal is unaffected.

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

#### Scenario: An early-stopping consumer is charged the climb, not the ceiling
- **WHEN** a consumer of an ordered racing pipeline stops after a small number
  of elements — a short-circuiting terminal, or a caller breaking out of its own
  loop over `iterator()`
- **THEN** the number of elements the chain ran on is bounded by how far the
  window had climbed when the consumer stopped, which for a consumer stopping
  within the first few rounds is far below the ceiling

#### Scenario: A draining pipeline reaches the ceiling in a source-independent number of refills
- **WHEN** a pipeline that never short-circuits is run over sources of very
  different lengths
- **THEN** the number of refills spent below the ceiling is the same for each,
  so the cost of the climb is a fixed addition rather than one that grows with
  the source

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

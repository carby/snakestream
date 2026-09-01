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

## ADDED Requirements

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

`PROCESSES` SHALL remain exported and is unaffected by this requirement; it
names a concept with a Java counterpart, while the read-ahead window does not.

#### Scenario: No public name exposes the bound
- **WHEN** a caller inspects the names exported by the `snakestream` package
- **THEN** no name is provided that reads or sets the read-ahead window, and the
  documented means of avoiding its cost are `unordered()` and `sequential()`

#### Scenario: The bound may be retuned without a breaking change
- **WHEN** the read-ahead window's value is changed on measurement
- **THEN** every requirement of this capability continues to hold unchanged, and
  no caller-visible contract is broken by the new value

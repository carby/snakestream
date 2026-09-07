## MODIFIED Requirements

### Requirement: find_first() may invoke a chain's callables more than once
On a parallel stream, `Stream.find_first()` SHALL be permitted to invoke the
callables of the operations in its chain on source elements other than the one
it ultimately returns, because the batches must be dispatched and running
before it is known which element is first.

The number of such elements SHALL be bounded. Under the fork-join executor it
SHALL NOT exceed the total number of elements pulled into the first round of
batches, which SHALL be one element per worker — the smallest first round that
still reaches every worker — because the call settles as soon as the first
element is released, and unless the source is exhausted first, resolving it
never requires starting a second round.

The size of that first round is a tuning decision, not a contract: it is
covered by `racing-encounter-order`'s allowance that the read-ahead bound may be
retuned without a breaking change, and this specification SHALL NOT name an
internal symbol for it.

A sequential `find_first()` SHALL continue to invoke them for exactly one
element.

Callers whose chain callables have side effects and who require exactly one
invocation SHALL declare `.sequential()`.

#### Scenario: A parallel find_first() may process more than one element
- **WHEN** `.parallel().map(f).find_first()` is awaited on a source of many
  elements
- **THEN** the correct first element is returned, and `f` is permitted to have
  been invoked on more than one element, up to the first round's bound

#### Scenario: The first round's bound is one element per worker
- **WHEN** `.parallel().map(f).find_first()` is awaited on a source with far
  more elements than workers
- **THEN** `f` is invoked on no more elements than there are workers

#### Scenario: A sequential find_first() processes exactly one
- **WHEN** `.sequential().map(f).find_first()` is awaited on the same source
- **THEN** `f` is invoked exactly once

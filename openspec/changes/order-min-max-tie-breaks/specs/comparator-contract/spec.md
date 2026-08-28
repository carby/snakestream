## MODIFIED Requirements

### Requirement: min() and max() keep the first of tied elements
When two elements compare as equal (`comparator(a, b) == 0`), `min()` and
`max()` SHALL both retain the earlier-encountered element as the running
result, not the later one, on any pipeline that carries an encounter-order
requirement at the end of its chain — under the sequential executor and under
`parallel()` alike. On such a pipeline the element returned SHALL be the same
one the sequential pipeline returns.

Where the pipeline carries no encounter-order requirement at the end of its
chain — a pipeline declared `unordered()` — which of two tied elements is
returned is unspecified, and `min()`/`max()` SHALL take the order-blind path
and pay nothing for this requirement. This matches Java, whose parallel
`min()`/`max()` on an unordered pipeline may break ties any way. A caller who
wants a determinate answer without an ordering barrier SHALL supply a total
comparator, for which `then_comparing()` is the lever.

The value returned is unaffected either way whenever the comparator is
consistent with equality; only which of two equal-comparing but distinguishable
elements is returned depends on the pipeline's ordering.

#### Scenario: max() keeps the first of equal maximums
- **WHEN** `Stream.of([("a", 5), ("b", 5)]).max(lambda x, y: x[1] - y[1])` is awaited
- **THEN** the result is `("a", 5)`

#### Scenario: min() keeps the first of equal minimums
- **WHEN** `Stream.of([("a", 5), ("b", 5)]).min(lambda x, y: x[1] - y[1])` is awaited
- **THEN** the result is `("a", 5)`

#### Scenario: An ordered racing max() keeps the first of equal maximums
- **WHEN** a stream over distinguishable records whose comparator keys tie is
  run under `.parallel()` with a mapping operation of variable per-element cost
  and `max()` is awaited
- **THEN** the result is the tied record earliest in encounter order, equal to
  the sequential pipeline's result, and is the same on every run

#### Scenario: An ordered racing min() keeps the first of equal minimums
- **WHEN** the same pipeline is run with `min()`
- **THEN** the result is the tied record earliest in encounter order, equal to
  the sequential pipeline's result

#### Scenario: An unordered racing max() may return either tied element
- **WHEN** `.parallel().unordered()` precedes `max()` over tied records
- **THEN** the result is one of the tied records, no delivery barrier is
  engaged, and no error is raised

#### Scenario: A total comparator is determinate on an unordered pipeline
- **WHEN** `.parallel().unordered().max(comparing(key).then_comparing(tiebreak))`
  is awaited over records whose first key ties
- **THEN** the result is the record the tie-break segment selects, and is the
  same on every run

## ADDED Requirements

### Requirement: sorted() is stable
`sorted()` SHALL be stable: elements that compare as equal
(`comparator(a, b) == 0`) SHALL appear in the sorted output in the same
relative order they held on entry to the sort. This SHALL hold for every
comparator form the capability accepts — a sync comparator, an async
comparator, and a `comparing()` key comparator with any number of segments in
any direction.

Stability SHALL hold under `parallel()` as well as sequentially, and SHALL hold
on a pipeline declared `unordered()`: a sort claims its output is ordered, so
it sees the whole stream in encounter order regardless of the ordering
characteristic at its own position, and the relative order it preserves is
therefore encounter order.

This is the same rule as `min()`/`max()`'s tie-break, read over a whole stream
rather than a single running result, which is why one capability states both.

#### Scenario: A sync comparator sort preserves the order of tied elements
- **WHEN** `Stream.of([("a", 5), ("b", 3), ("c", 5)]).sorted(lambda x, y: x[1] - y[1])`
  is collected
- **THEN** the result is `[("b", 3), ("a", 5), ("c", 5)]`

#### Scenario: An async comparator sort preserves the order of tied elements
- **WHEN** the same source is sorted with an `async def` comparator over the
  same key
- **THEN** the result is the same, with `("a", 5)` before `("c", 5)`

#### Scenario: A key comparator sort preserves the order of tied elements
- **WHEN** the same source is sorted with `comparing(lambda x: x[1])`
- **THEN** the result is the same, with `("a", 5)` before `("c", 5)`

#### Scenario: A reversed key comparator is stable rather than reversing ties
- **WHEN** the same source is sorted with `comparing(lambda x: x[1]).reversed()`
- **THEN** the result is `[("a", 5), ("c", 5), ("b", 3)]` — the tied pair keeps
  its encounter order rather than being reversed with the ordering

#### Scenario: A racing sort is stable
- **WHEN** the same sort runs under `.parallel()` behind a mapping operation of
  variable per-element cost
- **THEN** the result equals the sequential result exactly, tied elements
  included, on every run

#### Scenario: A sort on an unordered pipeline is stable
- **WHEN** `.parallel().unordered()` precedes the same sort
- **THEN** the sort still sees the whole stream and the result equals the
  sequential result exactly, tied elements included

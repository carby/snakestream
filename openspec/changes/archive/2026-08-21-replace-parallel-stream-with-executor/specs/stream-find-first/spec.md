## ADDED Requirements

### Requirement: find_first() preserves encounter order on a parallel stream when ordered
`Stream.find_first()` SHALL return the first element in the stream's encounter
order when `is_ordered()` is `True` (the default), regardless of which executor
the stream carries, matching Java's `findFirst()` guarantee on a parallel
stream. It SHALL achieve this by naming the sequential executor explicitly for
that drive, rather than by a parallel-specific override of `find_first()`.

When `is_ordered()` is `False`, `find_first()` SHALL be permitted to return any
matching element — the same behaviour as `find_any()`, under the stream's own
executor — matching Java's documented relaxation of `findFirst()`'s
encounter-order guarantee for unordered streams.

There SHALL be exactly one implementation of `find_first()`, selecting on the
ordering flag rather than on the stream's type or executor.

#### Scenario: Ordered parallel stream returns the true first element
- **WHEN** `.find_first()` is called on an ordered parallel stream whose chain
  includes a step that could otherwise complete out of encounter order under
  racing execution (e.g. a `.map()` with per-element variable delay)
- **THEN** the returned element is the first element in the original source's
  encounter order, not merely the first result to arrive

#### Scenario: Ordered parallel stream with an empty source returns None
- **WHEN** `.find_first()` is called on an ordered parallel stream built from an
  empty source
- **THEN** `None` is returned

#### Scenario: Unordered parallel stream delegates to racing behavior
- **WHEN** `.unordered()` is called on a parallel stream, followed by
  `.find_first()`
- **THEN** the method returns without waiting for a strictly ordered pull,
  behaving like `find_any()`

#### Scenario: An op declared before .parallel() does not defeat the order guarantee
- **WHEN** `.map(f)` is declared before `.parallel()` on an ordered stream and
  `.find_first()` is called, so that the map now runs under the racing executor
  for ordinary terminals
- **THEN** `find_first()` still returns the first element in encounter order,
  because it drives under the sequential executor regardless

## REMOVED Requirements

### Requirement: ParallelStream.find_first() preserves encounter order when the stream is ordered
**Reason**: `ParallelStream` no longer exists — execution mode is a value, not a
type — so a requirement keyed to that class has nothing to attach to. Its
guarantee is preserved verbatim by the added requirement above, which states it
against an ordered parallel stream and additionally pins that there is only one
`find_first()` implementation.
**Migration**: None for callers. `find_first()`'s observable behaviour is
unchanged: ordered streams still get the true first element, empty sources still
return `None`.

### Requirement: ParallelStream.find_first() may race when the stream is unordered
**Reason**: Same — keyed to a class that no longer exists. Splitting the ordered
and unordered cases across two requirements also mirrored the two
implementations that existed only because mode was a type; with one
implementation, one requirement covering both branches of the ordering flag is
the accurate shape.
**Migration**: None for callers. An unordered stream's `find_first()` still
behaves as `find_any()`.

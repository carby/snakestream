## ADDED Requirements

### Requirement: find_first() preserves encounter order regardless of the ordering characteristic
`Stream.find_first()` SHALL return the first element in the stream's encounter
order, or `None` if the stream is empty, regardless of which executor the
stream carries and regardless of whether the pipeline is ordered or unordered.
It SHALL achieve this by naming the sequential executor explicitly for that
drive, rather than by a parallel-specific override.

This matches Java, where `findFirst()`'s find-the-leftmost behaviour is fixed
when the operation is constructed and never consults the upstream ordering
flag. Java's javadoc *permits* an unordered stream to return any element; the
reference implementation declines to take that permission, and so does this
library. A caller who wants the relaxation SHALL use `find_any()`.

There SHALL be exactly one implementation of `find_first()`, with no branch on
the stream's type, executor or ordering characteristic.

#### Scenario: Ordered parallel stream returns the true first element
- **WHEN** `.find_first()` is called on an ordered parallel stream whose chain
  includes a step that could otherwise complete out of encounter order under
  racing execution (e.g. a `.map()` with per-element variable delay)
- **THEN** the returned element is the first element in the original source's
  encounter order, not merely the first result to arrive

#### Scenario: Unordered parallel stream also returns the true first element
- **WHEN** `.unordered()` is called on a parallel stream carrying such a chain,
  followed by `.find_first()`
- **THEN** the first element in the original source's encounter order is
  returned — the same element the ordered pipeline returns

#### Scenario: Ordered parallel stream with an empty source returns None
- **WHEN** `.find_first()` is called on a parallel stream built from an empty
  source, ordered or unordered
- **THEN** `None` is returned

#### Scenario: An op declared before .parallel() does not defeat the order guarantee
- **WHEN** `.map(f)` is declared before `.parallel()` on a stream and
  `.find_first()` is called, so that the map now runs under the racing executor
  for ordinary terminals
- **THEN** `find_first()` still returns the first element in encounter order,
  because it drives under the sequential executor regardless

#### Scenario: find_any() remains the unordered alternative
- **WHEN** `.find_any()` is called on a parallel stream
- **THEN** its existing racing behaviour is unchanged by this requirement — it
  is the operation a caller uses to opt out of the encounter-order guarantee

## REMOVED Requirements

### Requirement: find_first() preserves encounter order on a parallel stream when ordered
**Reason**: The requirement made the encounter-order guarantee conditional on
`is_ordered()`, degrading `find_first()` to `find_any()` on an unordered
stream. Java does not do this — `findFirst()` finds the leftmost element even
on an unordered parallel stream — and the degradation produced observably wrong
answers, most sharply on `.parallel().unordered().sorted(c).find_first()`,
which returned an arbitrary element rather than the smallest.

**Migration**: `find_first()` on an unordered parallel stream now returns the
true first element instead of racing. Callers who relied on the racing
behaviour SHALL use `find_any()`, which is unchanged and is what Java directs
such callers to as well.

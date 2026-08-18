## ADDED Requirements

### Requirement: Stream.find_first() returns the first element in encounter order
`Stream.find_first()` SHALL return the first element pulled through the
composed chain, or `None` if the stream is empty, matching Java's
`Stream.findFirst()`.

#### Scenario: Non-empty stream returns its first element
- **WHEN** `.find_first()` is called on a `Stream` built from a non-empty
  source
- **THEN** the first element in the source's encounter order is returned

#### Scenario: Empty stream returns None
- **WHEN** `.find_first()` is called on a `Stream` built from an empty
  source
- **THEN** `None` is returned

#### Scenario: find_first() does not consume the rest of the stream
- **WHEN** `.find_first()` is called on a stream with more than one element
- **THEN** only the first element is pulled from upstream before the method
  returns

### Requirement: ParallelStream.find_first() preserves encounter order when the stream is ordered
`ParallelStream.find_first()` SHALL return the first element in the
stream's encounter order when `is_ordered()` is `True` (the default),
regardless of `ParallelStream`'s racing execution model, matching Java's
`findFirst()` guarantee on a parallel stream.

#### Scenario: Ordered ParallelStream returns the true first element
- **WHEN** `.find_first()` is called on an ordered `ParallelStream` whose
  chain includes a step that could otherwise complete out of encounter
  order under racing execution (e.g. a `.map()` with per-element variable
  delay)
- **THEN** the returned element is the first element in the original
  source's encounter order, not merely the first result to arrive

#### Scenario: Ordered ParallelStream with an empty source returns None
- **WHEN** `.find_first()` is called on an ordered `ParallelStream` built
  from an empty source
- **THEN** `None` is returned

### Requirement: ParallelStream.find_first() may race when the stream is unordered
`ParallelStream.find_first()` SHALL be permitted to return any matching
element (the same racing behavior as `find_any()`) when `is_ordered()` is
`False`, matching Java's documented relaxation of `findFirst()`'s
encounter-order guarantee for unordered streams.

#### Scenario: Unordered ParallelStream delegates to racing behavior
- **WHEN** `.unordered()` is called on a `ParallelStream`, followed by
  `.find_first()`
- **THEN** the method returns without waiting for a strictly ordered pull,
  behaving like `find_any()`

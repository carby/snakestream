## ADDED Requirements

### Requirement: Stream API table lists every implemented method
README's Stream API table SHALL include a row for every `Stream` method
that has a real (non-stub) implementation in `src/snakestream/stream.py`,
so the table can be relied on as an accurate parity reference against the
Java `Stream` API.

#### Scenario: sorted() has a table row
- **WHEN** a reader consults README's Stream API table to check whether
  `sorted()` is implemented
- **THEN** the table contains a row for `sorted(comparator, reverse)`
  marked as done, matching its actual implementation at `stream.py:191`

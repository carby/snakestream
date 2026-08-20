## MODIFIED Requirements

### Requirement: Iterable source spreading
Source normalization SHALL spread any other object exposing `__iter__` or `__next__` (lists, tuples, sets, generators, custom iterators, etc.) into one stream element per item produced.

An object exposing `__next__` SHALL be spread whether or not it also exposes `__iter__`: an object with only `__next__` SHALL be advanced repeatedly until it signals exhaustion, yielding one stream element per value produced, and SHALL NOT raise `TypeError` for not being iterable.

#### Scenario: List source
- **WHEN** a stream is constructed from a `list`, e.g. `Stream.of([1, 2, 3])`
- **THEN** the resulting stream has one element per list item, in order

#### Scenario: Generator source
- **WHEN** a stream is constructed from a generator object
- **THEN** the resulting stream has one element per value the generator yields, in order

#### Scenario: Iterator source exposing only `__next__`
- **WHEN** a stream is constructed from an object that implements `__next__` but not `__iter__`, and that produces `1`, `2`, `3` before signalling exhaustion
- **THEN** the resulting stream has exactly the elements `1`, `2`, `3`, in that order, and no `TypeError` is raised

#### Scenario: Exhausted iterator source exposing only `__next__`
- **WHEN** a stream is constructed from an object that implements `__next__` but not `__iter__`, and that signals exhaustion on its first advance
- **THEN** the resulting stream has zero elements and no error is raised

#### Scenario: Iterator source composed through intermediate operations
- **WHEN** a stream constructed from an object implementing only `__next__` has intermediate operations applied and is then consumed by a terminal operation
- **THEN** the pipeline produces the same result it would for an equivalent list source

## MODIFIED Requirements

### Requirement: Scalar source normalization
Source normalization (`Stream()` construction, including via `Stream.of()`) SHALL treat `dict`, `str`, `bytes`, `bytearray`, and `memoryview` values as single scalar elements, never spreading them into their constituent items/characters/bytes, even though they are iterable.

The three binary types SHALL be treated alike: whether a buffer of bytes is immutable (`bytes`), mutable (`bytearray`), or a view over another buffer (`memoryview`) SHALL NOT change how many stream elements it produces.

#### Scenario: String source
- **WHEN** a stream is constructed from a `str` value, e.g. `Stream.of("abc")`
- **THEN** the resulting stream has exactly one element, the original string `"abc"`

#### Scenario: Bytes source
- **WHEN** a stream is constructed from a `bytes` value, e.g. `Stream.of(b"ab")`
- **THEN** the resulting stream has exactly one element, the original bytes object `b"ab"`

#### Scenario: Bytearray source
- **WHEN** a stream is constructed from a `bytearray` value, e.g. `Stream.of(bytearray(b"ab"))`
- **THEN** the resulting stream has exactly one element, the original `bytearray` object, and not the integers `97` and `98`

#### Scenario: Memoryview source
- **WHEN** a stream is constructed from a `memoryview` value, e.g. `Stream.of(memoryview(b"ab"))`
- **THEN** the resulting stream has exactly one element, the original `memoryview` object, and not the integers `97` and `98`

#### Scenario: Dict source
- **WHEN** a stream is constructed from a `dict` value, e.g. `Stream.of({"a": 1})`
- **THEN** the resulting stream has exactly one element, the original dict

### Requirement: Iterable source spreading
Source normalization SHALL spread any other object exposing `__iter__` or `__next__` (lists, tuples, sets, generators, custom iterators, etc.) into one stream element per item produced. The scalar types named in "Scalar source normalization" are the complete set of exceptions to this rule.

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

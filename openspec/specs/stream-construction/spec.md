## Purpose

Defines how `Stream.of(*args)` and general source normalization (`Stream()` construction) turn a caller-supplied value or values into stream elements — how many arguments `Stream.of()` accepts and in what form, and which source values are treated as a single scalar element versus spread into multiple elements.

## Requirements

### Requirement: Stream.of() argument arity
`Stream.of(*args)` SHALL accept only positional arguments. Calling it with keyword arguments SHALL raise `TypeError`.

#### Scenario: No arguments
- **WHEN** `Stream.of()` is called with no arguments
- **THEN** the resulting stream has zero elements

#### Scenario: Single argument
- **WHEN** `Stream.of(x)` is called with exactly one positional argument
- **THEN** `x` is passed to the stream's source normalization unchanged, and the resulting stream's elements are exactly what normalizing `x` alone would produce

#### Scenario: Multiple arguments
- **WHEN** `Stream.of(x, y, z, ...)` is called with two or more positional arguments
- **THEN** the resulting stream has one element per argument, in the order given, with no further normalization applied to the argument list itself (each argument is still individually normalized as an element, e.g. a `dict` argument stays one element)

#### Scenario: Keyword arguments rejected
- **WHEN** `Stream.of(a=1)` is called with any keyword argument
- **THEN** a `TypeError` is raised by Python's argument binding

### Requirement: Scalar source normalization
Source normalization (`Stream()` construction, including via `Stream.of()`) SHALL treat `dict`, `str`, and `bytes` values as single scalar elements, never spreading them into their constituent items/characters/bytes, even though they are iterable.

#### Scenario: String source
- **WHEN** a stream is constructed from a `str` value, e.g. `Stream.of("abc")`
- **THEN** the resulting stream has exactly one element, the original string `"abc"`

#### Scenario: Bytes source
- **WHEN** a stream is constructed from a `bytes` value, e.g. `Stream.of(b"ab")`
- **THEN** the resulting stream has exactly one element, the original bytes object `b"ab"`

#### Scenario: Dict source
- **WHEN** a stream is constructed from a `dict` value, e.g. `Stream.of({"a": 1})`
- **THEN** the resulting stream has exactly one element, the original dict

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

### Requirement: Non-iterable scalar source
Source normalization SHALL treat any value with neither `__iter__` nor `__next__` (other than `dict`/`str`/`bytes`, already covered) as a single scalar element, including `None`.

#### Scenario: None source
- **WHEN** a stream is constructed from `None`, e.g. `Stream.of(None)`
- **THEN** the resulting stream has exactly one element, `None`

#### Scenario: Plain scalar source
- **WHEN** a stream is constructed from a non-iterable value, e.g. `Stream.of(1)`
- **THEN** the resulting stream has exactly one element, that value

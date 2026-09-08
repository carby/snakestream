## MODIFIED Requirements

### Requirement: Stream.of() argument arity
`Stream.of(*args)` SHALL accept only positional arguments and SHALL treat every argument atomically, at every arity. The resulting stream SHALL have exactly one element per argument, in the order given, and SHALL NOT spread any argument into its constituent items, however many arguments are supplied. The number of arguments SHALL NOT change what an argument means. Calling it with keyword arguments SHALL raise `TypeError`.

Constructing a stream *from a source* — spreading a list, draining a generator, consuming an async iterator — is `Stream(source)`, not `Stream.of(source)`. The two are distinct operations and SHALL NOT be interchangeable for any iterable argument.

#### Scenario: No arguments
- **WHEN** `Stream.of()` is called with no arguments
- **THEN** the resulting stream has zero elements

#### Scenario: Single argument
- **WHEN** `Stream.of(x)` is called with exactly one positional argument
- **THEN** the resulting stream has exactly one element, `x` itself, whether or not `x` is iterable — `Stream.of([1, 2, 3])` yields one element, the list, and not the integers `1`, `2` and `3`

#### Scenario: Single generator argument
- **WHEN** `Stream.of(g)` is called with exactly one positional argument that is a generator object
- **THEN** the resulting stream has exactly one element, the generator object itself, and the generator is never advanced

#### Scenario: Single non-iterable argument
- **WHEN** `Stream.of(x)` is called with exactly one positional argument that is not iterable, e.g. `Stream.of(1)`
- **THEN** the resulting stream has exactly one element, that value

#### Scenario: Multiple arguments
- **WHEN** `Stream.of(x, y, z, ...)` is called with two or more positional arguments
- **THEN** the resulting stream has one element per argument, in the order given, each element being the argument itself

#### Scenario: Arity does not change meaning
- **WHEN** `Stream.of([1, 2])` and `Stream.of([1, 2], [3, 4])` are both called
- **THEN** the first yields one element and the second yields two, each element being one of the argument lists, so adding an argument adds an element and changes nothing about the arguments already present

#### Scenario: Keyword arguments rejected
- **WHEN** `Stream.of(a=1)` is called with any keyword argument
- **THEN** a `TypeError` is raised by Python's argument binding

### Requirement: Scalar source normalization
Source normalization (`Stream()` construction) SHALL treat `dict`, `str`, `bytes`, `bytearray`, and `memoryview` values as single scalar elements, never spreading them into their constituent items/characters/bytes, even though they are iterable.

The three binary types SHALL be treated alike: whether a buffer of bytes is immutable (`bytes`), mutable (`bytearray`), or a view over another buffer (`memoryview`) SHALL NOT change how many stream elements it produces.

Scenarios for this requirement SHALL be stated against `Stream(...)` rather than `Stream.of(...)`. `Stream.of()` yields one element per argument by construction, so a scalar-set scenario written against it holds whatever normalization does and would guarantee nothing.

#### Scenario: String source
- **WHEN** a stream is constructed from a `str` value, e.g. `Stream("abc")`
- **THEN** the resulting stream has exactly one element, the original string `"abc"`

#### Scenario: Bytes source
- **WHEN** a stream is constructed from a `bytes` value, e.g. `Stream(b"ab")`
- **THEN** the resulting stream has exactly one element, the original bytes object `b"ab"`

#### Scenario: Bytearray source
- **WHEN** a stream is constructed from a `bytearray` value, e.g. `Stream(bytearray(b"ab"))`
- **THEN** the resulting stream has exactly one element, the original `bytearray` object, and not the integers `97` and `98`

#### Scenario: Memoryview source
- **WHEN** a stream is constructed from a `memoryview` value, e.g. `Stream(memoryview(b"ab"))`
- **THEN** the resulting stream has exactly one element, the original `memoryview` object, and not the integers `97` and `98`

#### Scenario: Dict source
- **WHEN** a stream is constructed from a `dict` value, e.g. `Stream({"a": 1})`
- **THEN** the resulting stream has exactly one element, the original dict

### Requirement: Iterable source spreading
Source normalization SHALL spread any other object exposing `__iter__` or `__next__` (lists, tuples, sets, generators, custom iterators, etc.) into one stream element per item produced. The scalar types named in "Scalar source normalization" are the complete set of exceptions to this rule.

An object exposing `__next__` SHALL be spread whether or not it also exposes `__iter__`: an object with only `__next__` SHALL be advanced repeatedly until it signals exhaustion, yielding one stream element per value produced, and SHALL NOT raise `TypeError` for not being iterable.

Spreading SHALL be reachable only through `Stream(source)`. There SHALL be no argument to `Stream.of()` that spreads.

#### Scenario: List source
- **WHEN** a stream is constructed from a `list`, e.g. `Stream([1, 2, 3])`
- **THEN** the resulting stream has one element per list item, in order

#### Scenario: Generator source
- **WHEN** a stream is constructed from a generator object, e.g. `Stream(g)`
- **THEN** the resulting stream has one element per value the generator yields, in order

#### Scenario: Infinite generator source is not drained
- **WHEN** a stream is constructed from a generator that never terminates
- **THEN** construction returns without advancing it, and elements are produced only as the pipeline is consumed

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
- **WHEN** a stream is constructed from `None`, e.g. `Stream(None)`
- **THEN** the resulting stream has exactly one element, `None`

#### Scenario: Plain scalar source
- **WHEN** a stream is constructed from a non-iterable value, e.g. `Stream(1)`
- **THEN** the resulting stream has exactly one element, that value

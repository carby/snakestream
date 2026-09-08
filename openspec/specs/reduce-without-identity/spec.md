## Purpose

Defines the contract for `Stream.reduce(accumulator)`, the 1-arg overload of `reduce` that folds a stream using its own first pulled element as the seed instead of requiring an externally supplied identity value, mirroring Java's `Optional<T> reduce(BinaryOperator<T>)`. Covers accumulator dispatch (sync and async), the `None`-on-empty and short-circuit-on-single-element edge cases, and the guarantee that the existing 2-arg `reduce(identity, accumulator)` overload is unaffected.

## Requirements

### Requirement: reduce() accepts an accumulator with no identity
`Stream.reduce(accumulator)` SHALL fold the composed stream using its own first pulled element as the seed, requiring no externally supplied identity value. `accumulator` SHALL accept two values of the stream's element type and return a value of that same type, matching Java's `BinaryOperator<T>`. Both sync and async accumulators SHALL be accepted, dispatched the same way the existing 2-arg `reduce(identity, accumulator)` dispatches its accumulator.

#### Scenario: Multi-element stream folds left starting from the first element
- **WHEN** `Stream.reduce(accumulator)` is called on a stream yielding elements `e1, e2, ..., en` in order
- **THEN** the result equals `accumulator(...accumulator(accumulator(e1, e2), e3)..., en)`, the same left-fold order as the 2-arg form with `e1` as identity

#### Scenario: Async accumulator is awaited
- **WHEN** `Stream.reduce(accumulator)` is called with an `async def` accumulator on a multi-element stream
- **THEN** each accumulator call is awaited before its result is used as the next fold input, and the final result is the awaited value, not a coroutine

### Requirement: Empty stream returns None without calling the accumulator
When the composed stream yields no elements, `Stream.reduce(accumulator)` SHALL return `None` without ever calling `accumulator`, following the same `T | None` convention already used by `find_any()`, `max()`, and `min()` rather than a wrapped `Optional[T]` type.

#### Scenario: Empty stream returns None
- **WHEN** `Stream.reduce(accumulator)` is called on a stream that yields no elements
- **THEN** the result is `None` and `accumulator` is never called

### Requirement: Single-element stream returns that element unchanged
When the composed stream yields exactly one element, `Stream.reduce(accumulator)` SHALL return that element without calling `accumulator`, matching Java's `Optional<T>`-of-the-sole-element behavior.

#### Scenario: Single-element stream short-circuits the accumulator
- **WHEN** `Stream.reduce(accumulator)` is called on a stream that yields exactly one element `e1`
- **THEN** the result is `e1` and `accumulator` is never called

### Requirement: Existing 2-arg reduce(identity, accumulator) is unchanged
Adding the 1-arg overload SHALL NOT change the behavior, signature, or return type of the existing `Stream.reduce(identity, accumulator)` overload.

#### Scenario: 2-arg reduce behavior is unaffected
- **WHEN** `Stream.reduce(identity, accumulator)` is called with an explicit identity, as before this change
- **THEN** the result is identical to the pre-change behavior: the accumulator is called once per element, starting from `identity`

### Requirement: reduce()'s overload is selected by which arguments are supplied

`Stream.reduce()` SHALL select between its three overloads by **which**
parameters the caller supplied, not by the position of the first supplied one,
so each overload behaves identically whether it is spelled positionally or with
keyword arguments. The overloads and their parameter sets are `(accumulator)`,
`(identity, accumulator)` and `(identity, accumulator, combiner)`.

Where no `identity` is supplied, the fold SHALL be seeded from the stream's own
first element, exactly as the positional 1-argument form already is. That
outcome SHALL follow from a stated rule rather than from any two internal
markers happening to be the same value.

#### Scenario: the accumulator supplied by keyword selects the no-identity form
- **WHEN** `Stream([1, 2, 3]).reduce(accumulator=lambda a, b: a + b)` is called
- **THEN** the result is `6`, identical to `Stream([1, 2, 3]).reduce(lambda a, b: a + b)`

#### Scenario: an empty stream with a keyword accumulator returns None
- **WHEN** `Stream([]).reduce(accumulator=lambda a, b: a + b)` is called
- **THEN** the result is `None` and the accumulator is never called

#### Scenario: identity and accumulator supplied by keyword select the identity form
- **WHEN** `Stream([1, 2, 3]).reduce(identity=10, accumulator=lambda a, b: a + b)` is called
- **THEN** the result is `16`, identical to the positional spelling

#### Scenario: all three supplied by keyword select the combining form
- **WHEN** `Stream([1, 2, 3]).reduce(identity=0, accumulator=lambda a, b: a + b, combiner=lambda a, b: a + b)` is called
- **THEN** the result is `6`, identical to the positional spelling, and the reduction remains partitionable

#### Scenario: a falsy identity is still a supplied identity
- **WHEN** `Stream([1, 2, 3]).reduce(identity=0, accumulator=lambda a, b: a + b)` is called
- **THEN** the result is `6` — `0` seeds the fold and is not mistaken for an omitted argument

### Requirement: a supplied-argument set matching no overload is rejected

`Stream.reduce()` SHALL raise `StreamBuildException` when the set of supplied
arguments matches none of its three overloads, rather than failing later with a
`TypeError` from calling an internal marker or silently reducing under
semantics the caller did not ask for. Supplying `combiner` without `identity`
is such a call: `combiner` appears only in the three-argument overload, whose
contract is stated by the parallel-reduction capability and presumes a seed
every partition can start from.

#### Scenario: a combiner without an identity is rejected
- **WHEN** `Stream([1, 2, 3]).reduce(accumulator=lambda a, b: a + b, combiner=lambda a, b: a + b)` is called
- **THEN** `StreamBuildException` is raised, naming the unsatisfied overload

#### Scenario: no accumulator at all is rejected
- **WHEN** `Stream([1, 2, 3]).reduce()` is called
- **THEN** `StreamBuildException` is raised rather than a `TypeError` surfacing from inside the fold

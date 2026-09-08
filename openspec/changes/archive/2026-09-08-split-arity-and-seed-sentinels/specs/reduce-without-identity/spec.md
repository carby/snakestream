## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: overload dispatch matches Java's arg count exactly

`collector.py`'s `reducing` SHALL dispatch between the three overloads by
**which** parameters the caller supplied, matching how Java's overload
resolution picks between the three `reducing` signatures. No overload SHALL
require type inspection of an argument to decide what it means.

The previous wording — dispatch "strictly by positional argument count, with no
keyword-only disambiguation required" — SHALL NOT be read as permitting a
keyword-spelled call of a documented overload to behave differently from its
positional spelling. Each of the three overloads SHALL produce identical
results under either spelling, and a keyword-spelled call SHALL NOT raise.

Where no `identity` is supplied, the fold SHALL be seeded from the first
accumulated value, exactly as the positional 1-argument form already is.

#### Scenario: one positional arg selects the no-identity form
- **WHEN** `reducing(op)` is called with a single positional argument
- **THEN** it is treated as `binary_operator` with no identity, per the no-identity overload

#### Scenario: two positional args select the identity form
- **WHEN** `reducing(identity, op)` is called with two positional arguments
- **THEN** it is treated as `(identity, binary_operator)`, per the identity overload

#### Scenario: three positional args select the mapper form
- **WHEN** `reducing(identity, mapper, op)` is called with three positional arguments
- **THEN** it is treated as `(identity, mapper, binary_operator)`, per the mapper overload

#### Scenario: the operator supplied by keyword selects the no-identity form
- **WHEN** `Stream([1, 2, 3]).collect(reducing(binary_operator=lambda a, b: a + b))` is called
- **THEN** the result is `6`, identical to the positional spelling, rather than the `TypeError` raised before this change

#### Scenario: identity and operator supplied by keyword select the identity form
- **WHEN** `Stream([1, 2, 3]).collect(reducing(identity=10, binary_operator=lambda a, b: a + b))` is called
- **THEN** the result is `16`, identical to `reducing(10, lambda a, b: a + b)`

#### Scenario: a mixed positional and keyword call selects the identity form
- **WHEN** `Stream([1, 2, 3]).collect(reducing(10, binary_operator=lambda a, b: a + b))` is called
- **THEN** the result is `16`, identical to the fully positional spelling

#### Scenario: all three supplied by keyword select the mapper form
- **WHEN** `Stream(["a", "bb", "ccc"]).collect(reducing(identity=0, mapper=len, binary_operator=lambda a, b: a + b))` is called
- **THEN** the result is `6`, identical to the positional spelling

#### Scenario: a falsy identity is still a supplied identity
- **WHEN** `Stream([1, 2, 3]).collect(reducing(identity=0, binary_operator=lambda a, b: a + b))` is called
- **THEN** the result is `6` — `0` seeds the fold and is not mistaken for an omitted argument

## ADDED Requirements

### Requirement: a supplied-argument set matching no `reducing()` overload is rejected

`reducing()` SHALL raise `StreamBuildException` when the set of supplied
arguments matches none of its three overloads, rather than deferring the
failure to a `TypeError` raised when an internal marker is called during
collection. Supplying `mapper` without `identity` is such a call: `mapper`
appears only in the three-argument overload.

#### Scenario: a mapper without an identity is rejected
- **WHEN** `reducing(mapper=len, binary_operator=lambda a, b: a + b)` is called
- **THEN** `StreamBuildException` is raised at collector construction, naming the unsatisfied overload

#### Scenario: no binary operator at all is rejected
- **WHEN** `reducing()` is called with no arguments
- **THEN** `StreamBuildException` is raised at collector construction

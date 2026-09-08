## MODIFIED Requirements

### Requirement: `grouping_by`'s form is selected by argument count

`grouping_by` SHALL select between its three forms by **which** parameters the
caller supplied, and SHALL NOT inspect an argument's type to decide what it
means:

- one argument — `classifier`, with the list-building downstream and the
  default `dict` container;
- two arguments — `classifier` and `downstream`, with the default `dict`
  container;
- three arguments — `classifier`, `map_factory` and `downstream`.

Each form SHALL behave identically whether it is spelled positionally or with
keyword arguments; a keyword-spelled call of a documented form SHALL NOT raise.

The shipped two-argument call SHALL therefore be unaffected: a call passing a
`Collector` as the second of two arguments binds it to `downstream`, not to
`map_factory`, whatever its type. The declared type surface SHALL express the
three forms so that a call is checked statically as well as dispatched at
runtime.

#### Scenario: a two-argument call still binds its second argument to downstream
- **WHEN** `Stream([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, counting()))` is called
- **THEN** the result is `{1: 3, 0: 2}` in a plain `dict`, exactly as before this change

#### Scenario: a one-argument call is unchanged
- **WHEN** `Stream([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2))` is called
- **THEN** the result is `{1: [1, 3, 5], 0: [2, 4]}` in a plain `dict`

#### Scenario: the second of three arguments is the container factory
- **WHEN** `grouping_by(classifier, map_factory, downstream)` is called
- **THEN** `map_factory` supplies the result mapping and `downstream` collects each group

#### Scenario: a downstream supplied by keyword selects the two-argument form
- **WHEN** `Stream([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, downstream=counting()))` is called
- **THEN** the result is `{1: 3, 0: 2}` in a plain `dict`, identical to the positional spelling, rather than the `TypeError` raised before this change

#### Scenario: the classifier supplied by keyword selects the one-argument form
- **WHEN** `Stream([1, 2, 3, 4, 5]).collect(grouping_by(classifier=lambda x: x % 2))` is called
- **THEN** the result is `{1: [1, 3, 5], 0: [2, 4]}` in a plain `dict`

#### Scenario: map_factory and downstream supplied by keyword select the three-argument form
- **WHEN** `grouping_by(classifier, map_factory=OrderedDict, downstream=counting())` is collected
- **THEN** the result mapping is the caller's `OrderedDict`, identical to the positional spelling

## ADDED Requirements

### Requirement: a supplied-argument set matching no `grouping_by()` form is rejected

`grouping_by()` SHALL raise `StreamBuildException` when the set of supplied
arguments matches none of its three forms. Supplying `map_factory` without
`downstream` is such a call: `map_factory` appears only in the three-argument
form. The failure SHALL name that unsatisfied form rather than reporting a
downstream type error, which is what the caller sees today when the supplied
`map_factory` is shifted into the `downstream` position.

#### Scenario: a map_factory without a downstream is rejected on its own terms
- **WHEN** `grouping_by(lambda x: x % 2, map_factory=dict)` is called
- **THEN** `StreamBuildException` is raised naming the unsatisfied three-argument form, not reporting that `downstream` is not a `Collector`

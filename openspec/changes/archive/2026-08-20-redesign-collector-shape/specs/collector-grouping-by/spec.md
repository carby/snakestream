## MODIFIED Requirements

### Requirement: `grouping_by(classifier, downstream)` composes a downstream collector
`collector.py` SHALL provide the 2-arg `grouping_by(classifier, downstream)`
form, where `downstream` is a `Collector` and each group's elements are
accumulated into that collector's own container, keyed by classifier output,
instead of being left as a plain list — matching Java's
`Collectors.groupingBy(Function classifier, Collector downstream)`. The
default `downstream` SHALL remain the list-building collector, so the 1-arg
form's `dict[K, list[T]]` result is unchanged.

Each key's container SHALL be created by the downstream collector's supplier
the first time that key occurs, accumulated into as each element of that group
arrives, and finished by the downstream collector's finisher once the source
is exhausted. Passing a callable that is not a `Collector` as `downstream`
SHALL raise `StreamBuildException`.

#### Scenario: downstream collector reduces each group
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, counting()))` is called
- **THEN** the result is `{1: 3, 0: 2}`

#### Scenario: downstream collector composes with other collector.py collectors
- **WHEN** `Stream.of(["a", "bb", "ccc", "dd"]).collect(grouping_by(len, joining(", ")))` is called
- **THEN** the result is `{1: "a", 2: "bb, dd", 3: "ccc"}`

#### Scenario: only present classifier outputs get a downstream-reduced entry
- **WHEN** `grouping_by(classifier, downstream)` is used and a stream has elements for only some classifier outputs
- **THEN** each present key's value reflects only that key's elements reduced via `downstream`, and no key is present for a classifier output that never occurred

#### Scenario: each key gets its own downstream container
- **WHEN** `grouping_by(classifier, downstream)` is used with a `downstream` whose container is mutable
- **THEN** no two keys share a container, and each key's result reflects only its own elements

#### Scenario: a non-Collector downstream is rejected
- **WHEN** `grouping_by(classifier, downstream)` is given a plain callable as `downstream`
- **THEN** `StreamBuildException` is raised

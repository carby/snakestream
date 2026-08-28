## Purpose

Grouping collector for use with `Stream.collect()`, mirroring Java's
`Collectors.groupingBy(...)` overloads.

## Requirements

### Requirement: `grouping_by(classifier)` collector factory (no downstream)
`collector.py` SHALL provide a `grouping_by(classifier)` form — called with
no `downstream` — returning a collector that buckets each pulled element by
`classifier(element)` (sync or async) and returns `dict[K, list[T]]`,
matching Java's `Collectors.groupingBy(Function classifier)` (which defaults
its downstream to `toList()`).

#### Scenario: buckets elements by classifier into lists
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2))` is called
- **THEN** the result is `{1: [1, 3, 5], 0: [2, 4]}`

#### Scenario: empty stream yields an empty dict
- **WHEN** `Stream.of([]).collect(grouping_by(lambda x: x))` is called
- **THEN** the result is `{}`

#### Scenario: only keys actually produced appear in the result
- **WHEN** `Stream.of([1, 1, 1]).collect(grouping_by(lambda x: x))` is called
- **THEN** the result is `{1: [1, 1, 1]}`, with no other keys present

#### Scenario: async classifier is awaited
- **WHEN** `grouping_by(classifier)` is given an async `classifier`
- **THEN** the result is computed correctly, with `classifier` awaited via the same dispatch used elsewhere in the library

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

### Requirement: `grouping_by()` derives `UNORDERED` from its downstream

The collector returned by `grouping_by(classifier, downstream)` SHALL declare
`Characteristics.UNORDERED` when, and only when, `downstream` declares it.

The derivation follows from what `UNORDERED` promises. The result is a mapping
from classifier key to the downstream's collected value. Two mappings compare
equal when they hold the same keys — irrespective of the order those keys were
inserted — and equal values for each. The classifier is a function of the
element, so any ordering of the same elements yields the same key set. The
result is therefore equal under reordering exactly when every group's value is,
which is the downstream's characteristic and nothing else.

The rule SHALL be the same one `mapping()` and `collecting_and_then()` already
apply, and SHALL compose through nesting.

`grouping_by()` SHALL NOT decline the derivation on the ground that the
returned mapping's key iteration order follows encounter order. It does, and
that is permitted: `UNORDERED` promises equality of the result, not its
iteration order (see the `collector-protocol` capability). Java specifies
nothing about `Collectors.groupingBy()`'s characteristics, so the derivation
diverges from no documented contract.

#### Scenario: Grouping into an unordered downstream is unordered
- **WHEN** the collector returned by `grouping_by(len, to_set())` is asked for
  its characteristics
- **THEN** `UNORDERED` is present

#### Scenario: Grouping into an ordered downstream is not unordered
- **WHEN** the collector returned by `grouping_by(len, to_list())` is asked for
  its characteristics
- **THEN** `UNORDERED` is absent

#### Scenario: The default downstream is ordered
- **WHEN** the collector returned by `grouping_by(len)` — taking the default
  downstream — is asked for its characteristics
- **THEN** `UNORDERED` is absent, because the default collects each group into
  a list

#### Scenario: Derivation composes through nesting
- **WHEN** the collector returned by `grouping_by(len, mapping(str, to_set()))`
  is asked for its characteristics
- **THEN** `UNORDERED` is present, derived through the adapter to the innermost
  downstream

#### Scenario: The derived declaration matches the behaviour
- **WHEN** two streams carrying the same elements in different orders are each
  collected with `grouping_by(f, to_set())`
- **THEN** the two resulting mappings are equal

#### Scenario: An unordered grouping skips the delivery barrier
- **WHEN** an ordered racing pipeline is collected with
  `grouping_by(f, to_set())`
- **THEN** the collected mapping is correct and no reorder barrier is engaged

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
form, where each group's bucketed elements are reduced via `downstream` (any
existing `collector.py` collector factory's returned closure) instead of
being left as a plain list, matching Java's `Collectors.groupingBy(Function
classifier, Collector downstream)`.

#### Scenario: downstream collector reduces each group
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, counting()))` is called
- **THEN** the result is `{1: 3, 0: 2}`

#### Scenario: downstream collector composes with other collector.py collectors
- **WHEN** `Stream.of(["a", "bb", "ccc", "dd"]).collect(grouping_by(len, joining(", ")))` is called
- **THEN** the result is `{1: "a", 2: "bb, dd", 3: "ccc"}`

#### Scenario: only present classifier outputs get a downstream-reduced entry
- **WHEN** `grouping_by(classifier, downstream)` is used and a stream has elements for only some classifier outputs
- **THEN** each present key's value reflects only that key's elements reduced via `downstream`, and no key is present for a classifier output that never occurred

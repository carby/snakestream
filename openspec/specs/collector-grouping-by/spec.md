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

**The derivation is bounded to the default `dict` container.** It rests on
`dict` equality holding two mappings equal irrespective of key insertion order,
and a caller-supplied mapping type need not: an `OrderedDict` compared against
another `OrderedDict` is equal only if its keys were inserted in the same
order, and key insertion order here follows the order groups were first seen.
So the collector returned by the 3-arg `grouping_by(classifier, map_factory,
downstream)` SHALL NOT declare `Characteristics.UNORDERED`, whatever
`downstream` declares.

The exclusion SHALL be unconditional on `map_factory` rather than decided by
inspecting the mapping type it produces. Whether a type's equality ignores key
order is not something the library can establish, and a caller who knows their
chosen type's is has `unordered()`, which declares the same freedom at the
pipeline rather than at the collector. This is the rule `to_collection()`
already follows: a caller-supplied container declares nothing.

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

#### Scenario: A caller-supplied container clears the mark
- **WHEN** the collector returned by `grouping_by(len, OrderedDict, to_set())`
  is asked for its characteristics
- **THEN** `UNORDERED` is absent, though `to_set()` declares it

#### Scenario: The exclusion holds even for a container equality would allow
- **WHEN** the collector returned by `grouping_by(len, dict, to_set())` is
  asked for its characteristics
- **THEN** `UNORDERED` is absent, the exclusion following from `map_factory`
  being supplied at all rather than from the type it produces

#### Scenario: A cleared mark takes the delivery barrier
- **WHEN** an ordered racing pipeline is collected with
  `grouping_by(f, OrderedDict, to_set())`
- **THEN** the reorder barrier is engaged, and the mapping's key insertion
  order follows encounter order

### Requirement: `grouping_by(classifier, map_factory, downstream)` chooses the result container

`grouping_by` SHALL provide a 3-arg form whose second argument supplies the
mapping the groups are collected into, matching Java's
`Collectors.groupingBy(Function classifier, Supplier mapFactory, Collector
downstream)`. `map_factory` SHALL sit in Java's argument position, between
`classifier` and `downstream`.

`map_factory` SHALL be called with no arguments exactly once per collection,
before any element is accumulated, to produce a fresh empty mapping. It MAY be
sync or async and SHALL be awaited via the same dispatch every other
user-supplied callable in the library uses. That mapping SHALL be the object
the collection returns: group keys are inserted into it as they are first seen,
each group's downstream result is written back into it by the finisher, and it
is returned as-is, so a caller-supplied type reaches the caller intact rather
than being copied into a `dict`.

Group creation, accumulation and downstream finishing SHALL otherwise behave
exactly as in the 2-arg form, and a `downstream` that is not a `Collector`
SHALL raise `StreamBuildException` in this form as in that one.

#### Scenario: the result is the caller's mapping type
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, OrderedDict, counting()))` is called
- **THEN** the result is an `OrderedDict` holding `{1: 3, 0: 2}`, not a plain `dict`

#### Scenario: the downstream finisher writes into the caller's mapping
- **WHEN** a 3-arg `grouping_by` is used with a `downstream` that has a finisher
- **THEN** each key's finished value is present in the returned mapping and the mapping is still the caller's type

#### Scenario: a fresh mapping per collection
- **WHEN** the same 3-arg `grouping_by` collector instance is used across two separate `collect()` calls
- **THEN** each call returns an independent mapping, unaffected by the other call's elements

#### Scenario: empty stream yields the caller's empty mapping
- **WHEN** `Stream.of([]).collect(grouping_by(f, OrderedDict, to_list()))` is called
- **THEN** the result is an empty `OrderedDict`

#### Scenario: an async map_factory is awaited
- **WHEN** the 3-arg `grouping_by` is given an async `map_factory`
- **THEN** the mapping it resolves to is used as the result container

#### Scenario: a non-Collector downstream is still rejected
- **WHEN** `grouping_by(classifier, map_factory, downstream)` is given a plain callable as `downstream`
- **THEN** `StreamBuildException` is raised

### Requirement: `grouping_by`'s form is selected by argument count

`grouping_by` SHALL select between its three forms by how many arguments are
passed, and SHALL NOT inspect an argument's type to decide what it means:

- one argument — `classifier`, with the list-building downstream and the
  default `dict` container;
- two arguments — `classifier` and `downstream`, with the default `dict`
  container;
- three arguments — `classifier`, `map_factory` and `downstream`.

The shipped two-argument call SHALL therefore be unaffected: a call passing a
`Collector` as the second of two arguments binds it to `downstream`, not to
`map_factory`, whatever its type. The declared type surface SHALL express the
three forms so that a call is checked statically as well as dispatched at
runtime.

#### Scenario: a two-argument call still binds its second argument to downstream
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, counting()))` is called
- **THEN** the result is `{1: 3, 0: 2}` in a plain `dict`, exactly as before this change

#### Scenario: a one-argument call is unchanged
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2))` is called
- **THEN** the result is `{1: [1, 3, 5], 0: [2, 4]}` in a plain `dict`

#### Scenario: the second of three arguments is the container factory
- **WHEN** `grouping_by(classifier, map_factory, downstream)` is called
- **THEN** `map_factory` supplies the result mapping and `downstream` collects each group

### Requirement: `grouping_by()` derives its combiner from its downstream

`grouping_by()`'s collector SHALL declare a `combiner` only where its
downstream collector declares one - the same rule this factory already uses
to derive `Characteristics` from its downstream, applied once more. That
combiner SHALL merge two partial group maps by key: a key present in only
one side is copied across; a key present in both is merged by calling the
downstream's own combiner on the two group containers. Where the downstream
declares no combiner, `grouping_by()`'s collector SHALL declare none either,
and the collection SHALL fall back to today's single-container behavior
rather than a wrong answer.

This derivation does not depend on whether a `map_factory` was supplied
(unlike the `UNORDERED` derivation, which is bounded to the default `dict`
container): merging two partial mappings by key works the same way over any
`MutableMapping`.

#### Scenario: Parallel result over several batches matches sequential, combinable downstream
- **WHEN** a source spanning more than one batch is collected with `grouping_by(classifier, counting())` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: A non-combinable downstream declares no combiner
- **WHEN** `grouping_by(classifier, summing_double(mapper)).combiner` is read
- **THEN** it is `None`, and the collection is not partitioned, but the result under `.parallel()` still equals the sequential result

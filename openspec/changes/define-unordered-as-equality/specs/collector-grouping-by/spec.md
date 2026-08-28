## ADDED Requirements

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

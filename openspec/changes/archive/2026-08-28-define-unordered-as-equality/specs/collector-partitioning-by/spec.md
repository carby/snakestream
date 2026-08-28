## ADDED Requirements

### Requirement: `partitioning_by()` derives `UNORDERED` from its downstream

The collector returned by `partitioning_by(predicate, downstream)` SHALL
declare `Characteristics.UNORDERED` when, and only when, `downstream` declares
it.

The derivation SHALL rest on `partitioning_by()`'s own structure rather than on
`grouping_by()`'s. Both partitions are created before any element is
accumulated, so the result is always a two-key mapping carrying the same two
keys in the same order over any input, including an empty stream. No part of
the result depends on encounter order except the value collected into each
partition, and that dependence is the downstream's characteristic.

The rule SHALL be the same one `mapping()` and `collecting_and_then()` already
apply, and SHALL compose through nesting.

Java specifies nothing about `Collectors.partitioningBy()`'s characteristics,
so the derivation diverges from no documented contract.

#### Scenario: Partitioning into an unordered downstream is unordered
- **WHEN** the collector returned by `partitioning_by(p, to_set())` is asked
  for its characteristics
- **THEN** `UNORDERED` is present

#### Scenario: Partitioning into an ordered downstream is not unordered
- **WHEN** the collector returned by `partitioning_by(p, to_list())` is asked
  for its characteristics
- **THEN** `UNORDERED` is absent

#### Scenario: The default downstream is ordered
- **WHEN** the collector returned by `partitioning_by(p)` — taking the default
  downstream — is asked for its characteristics
- **THEN** `UNORDERED` is absent, because the default collects each partition
  into a list

#### Scenario: Derivation composes through nesting
- **WHEN** the collector returned by
  `partitioning_by(p, mapping(str, to_set()))` is asked for its characteristics
- **THEN** `UNORDERED` is present, derived through the adapter to the innermost
  downstream

#### Scenario: The two-key result is unaffected by the derivation
- **WHEN** a stream is collected with `partitioning_by(p, to_set())`, including
  an empty stream
- **THEN** the result carries exactly the two keys `True` and `False`, in that
  order, as it does without the derivation

#### Scenario: An unordered partitioning skips the delivery barrier
- **WHEN** an ordered racing pipeline is collected with
  `partitioning_by(p, to_set())`
- **THEN** the collected mapping is correct and no reorder barrier is engaged

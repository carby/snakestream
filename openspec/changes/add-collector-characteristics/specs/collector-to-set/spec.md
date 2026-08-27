## ADDED Requirements

### Requirement: `to_set()` declares `UNORDERED`

The collector returned by `to_set()` SHALL declare the `UNORDERED`
characteristic, matching Java, where `Collectors.toSet()` is the one factory in
`Collectors` carrying it.

The declaration SHALL be true of the collector's behaviour and not merely
asserted: a `set` retains no record of the order in which its members were
added, so collecting any two orderings of the same elements SHALL produce equal
sets.

#### Scenario: to_set() reports UNORDERED
- **WHEN** the collector returned by `to_set()` is asked for its characteristics
- **THEN** `UNORDERED` is present

#### Scenario: The declaration matches the behaviour
- **WHEN** two streams carrying the same elements in different orders are each
  collected with `to_set()`
- **THEN** the two results are equal

#### Scenario: Collectors that observe order do not declare it
- **WHEN** the collectors returned by `to_list()` and `joining()` are asked for
  their characteristics
- **THEN** `UNORDERED` is absent from both, because each produces a result whose
  element order reflects the order it was fed

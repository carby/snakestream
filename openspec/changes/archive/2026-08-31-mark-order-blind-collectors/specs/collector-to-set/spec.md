## MODIFIED Requirements

### Requirement: `to_set()` declares `UNORDERED`

The collector returned by `to_set()` SHALL declare the `UNORDERED`
characteristic, matching Java, where `Collectors.toSet()` is the one
non-concurrent factory in `Collectors` whose documentation declares it — the
concurrent `groupingByConcurrent()` and `toConcurrentMap()` declare it too.

The declaration SHALL be true of the collector's behaviour and not merely
asserted: a `set` compares equal to another `set` with the same members
irrespective of the order in which either was built, so collecting any two
orderings of the same elements SHALL produce equal sets.

The justification SHALL rest on that equality and SHALL NOT rest on a claim
that a `set` retains no record of the order its members were added in. That
claim is false of the runtime — two equal sets built from the same elements in
different orders may iterate in different orders — and `UNORDERED` promises
equality, not iteration order (see the `collector-protocol` capability).

The order-blind path `to_set()` takes under an ordered racing pipeline SHALL be
verified as the `racing-encounter-order` capability requires. Because a `set`
compares equal under either path, a verification asserting only that the
collected set is correct SHALL NOT be treated as discharging this: it passes
whether or not a delivery barrier ran. `to_set()` is a collector whose result
cannot betray arrival order, so it SHALL be guarded by an assertion that the
factory declares `UNORDERED` together with the separate verification that
`collect()` acts on the declaration.

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

#### Scenario: The order-blind path is guarded, not merely named
- **WHEN** the verification of `to_set()`'s order-blind path under an ordered
  racing pipeline is examined
- **THEN** it asserts that `to_set()` declares `UNORDERED`, and does not rest on
  a correctness-only assertion that would pass under either path

#### Scenario: Dropping the declaration is caught
- **WHEN** the `UNORDERED` declaration is removed from `to_set()`
- **THEN** the verification of its order-blind path fails

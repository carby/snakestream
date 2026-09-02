## MODIFIED Requirements

### Requirement: Keys within a segment must be mutually comparable
Each segment SHALL order on its own keys independently, and SHALL raise
`TypeError` when two keys within one segment do not support comparison with each
other. Keys from different segments are never compared with one another, so
segments MAY produce unrelated key types.

The raise SHALL NOT depend on what earlier segments did with the same pair. A
segment holding mutually incomparable keys SHALL raise whether or not an earlier
segment already distinguishes the elements carrying them, so that a chain's
acceptance of its keys is a property of the keys and not of the data the chain
happens to be sorting.

#### Scenario: incomparable keys within one segment raise TypeError
- **WHEN** a chain is used to sort and one segment's extractor yields keys of mutually incomparable types for two elements
- **THEN** a `TypeError` is raised

#### Scenario: segments may produce unrelated key types
- **WHEN** a chain's first segment yields strings and its second yields integers
- **THEN** the sort succeeds, ordering by string then by integer

#### Scenario: an earlier segment distinguishing the elements does not excuse a later one
- **WHEN** a chain is used to sort, its first segment yields a distinct key for every element, and its second segment yields keys of mutually incomparable types
- **THEN** a `TypeError` is raised, even though no pair ever ties on the first segment

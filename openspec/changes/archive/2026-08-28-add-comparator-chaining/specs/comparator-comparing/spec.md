## MODIFIED Requirements

### Requirement: Sorting applies the key extractor once per element
When a `comparing()` comparator is used to sort, the key extractor SHALL be
invoked exactly once per element, not once per comparison. This is the property
the capability exists for: a comparison-based ordering invokes its function
O(n log n) times, which for an async extractor means O(n log n) awaits, whereas
extracting each key once means O(n).

Where the comparator orders by more than one key, this SHALL hold per key: each
of the k orderings' extractors is invoked exactly once per element, for exactly
k×n invocations. Extraction SHALL be eager — every extractor runs against every
element even where an earlier ordering already decides every comparison and a
later key is therefore never consulted. Eagerness is observable: an extractor
that raises for some element SHALL propagate that error from a sort even when
that element's later keys would not have been compared.

#### Scenario: extractor invocation count is linear in stream length
- **WHEN** a stream of n elements is sorted with `comparing()` over a key extractor that counts its invocations
- **THEN** the extractor has been invoked exactly n times once the sort completes

#### Scenario: every ordering's extractor is invoked once per element
- **WHEN** a stream of n elements is sorted by a comparator ordering on k keys, each extractor counting its invocations
- **THEN** each of the k extractors has been invoked exactly n times, including one whose key never decides a comparison

#### Scenario: a later extractor's error surfaces even when its key is not needed
- **WHEN** a stream whose elements all have distinct first keys is sorted by an ordering on that key followed by an ordering whose extractor raises for one element
- **THEN** the error propagates from the sort

## ADDED Requirements

### Requirement: Direct comparison extracts lazily, sorting extracts eagerly
Invoking a `comparing()` comparator directly as a two-argument `Comparator` —
the path `min()`, `max()`, `min_by()` and `max_by()` use — SHALL extract keys
per comparison rather than once per element, and where the comparator orders by
more than one key SHALL stop at the first key that decides the comparison,
leaving later extractors uninvoked for that pair. Both paths SHALL produce the
same ordering; they differ only in how many times an extractor runs and,
consequently, in whether an extractor that raises for a given element is reached
at all.

#### Scenario: direct comparison stops at the deciding key
- **WHEN** a comparator ordering on two keys is invoked directly with two elements whose first keys differ
- **THEN** the second key's extractor is not invoked for either element

#### Scenario: direct comparison consults the later key on a tie
- **WHEN** a comparator ordering on two keys is invoked directly with two elements whose first keys are equivalent
- **THEN** the second key's extractor is invoked and its comparison decides the returned sign

#### Scenario: both paths agree on order
- **WHEN** the same comparator is used to sort a stream and to select its minimum
- **THEN** the minimum equals the first element of the sorted result

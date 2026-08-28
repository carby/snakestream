# comparator-comparing Specification

## Purpose

Defines `comparing(key_extractor)` — the key-based way to build a `Comparator`,
matching Java's `Comparator.comparing` — so that ordering can be expressed as
"what to order by" rather than "how to compare two elements". A key-based
ordering lets every comparator-consuming operation extract one key per element
instead of calling a comparison function O(n log n) times, which for an async
key extractor is the difference between O(n) and O(n log n) awaits.

## Requirements

### Requirement: comparing() builds a Comparator from a key extractor
`comparing(key_extractor)` SHALL return a value satisfying the `Comparator`
contract that orders two elements by comparing the keys the extractor produces
for them: negative when the first element's key orders before the second's, zero
when the keys are equivalent, and positive when it orders after. The result
SHALL be accepted anywhere a `Comparator` is accepted — `sorted()`, `min()` and
`max()` on `Stream`, and the `min_by()` and `max_by()` collectors — with no
change to those signatures.

#### Scenario: sorted() orders by extracted key
- **WHEN** `Stream.of([{"v": 3}, {"v": 1}, {"v": 2}]).sorted(comparing(lambda x: x["v"]))` is collected
- **THEN** the result is `[{"v": 1}, {"v": 2}, {"v": 3}]`

#### Scenario: min() selects the element with the least key
- **WHEN** `Stream.of([{"v": 3}, {"v": 1}, {"v": 2}]).min(comparing(lambda x: x["v"]))` is awaited
- **THEN** the result is `{"v": 1}`

#### Scenario: max() selects the element with the greatest key
- **WHEN** `Stream.of([{"v": 3}, {"v": 1}, {"v": 2}]).max(comparing(lambda x: x["v"]))` is awaited
- **THEN** the result is `{"v": 3}`

#### Scenario: min_by() and max_by() collectors accept it identically
- **WHEN** `comparing(lambda x: x["v"])` is passed to the `min_by()` or `max_by()` collector
- **THEN** it orders by the extracted key exactly as it does for `min()` and `max()`

#### Scenario: result is callable as an ordinary Comparator
- **WHEN** the value returned by `comparing(key_extractor)` is invoked directly with two elements
- **THEN** it returns a negative, zero, or positive `int` following the same sign contract as any other `Comparator`

### Requirement: The key extractor may be sync or async
`comparing()` SHALL accept both a sync key extractor and one returning an
`Awaitable`, matching every other user-supplied callable in the library. An
async key extractor SHALL be awaited and its awaited value used as the key.

#### Scenario: async key extractor orders identically to the sync one
- **WHEN** an `async def` key extractor is passed to `comparing()` and used with `sorted()`
- **THEN** the resulting order is the same as for the equivalent sync key extractor

#### Scenario: async key extractor works with min() and max()
- **WHEN** `comparing()` with an `async def` key extractor is passed to `min()` or `max()`
- **THEN** the extractor is awaited and the correct extreme element is returned

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

### Requirement: Ordering by key is stable
Sorting with a `comparing()` comparator SHALL preserve the relative encounter
order of elements whose extracted keys are equivalent.

#### Scenario: elements with equal keys keep their encounter order
- **WHEN** `Stream.of([("a", 1), ("b", 1), ("c", 0)]).sorted(comparing(lambda x: x[1]))` is collected
- **THEN** the result is `[("c", 0), ("a", 1), ("b", 1)]`

### Requirement: Keys must be mutually comparable
Ordering by key SHALL raise `TypeError` when two extracted keys do not support
comparison with each other, in the same way sorting a list of such values does.
No separate sign or `bool` validation applies to a key extractor: it returns a
key, not a comparison result, so the `Comparator` bool-rejection rule defined in
`comparator-contract` has nothing to guard on this path.

#### Scenario: incomparable keys raise TypeError
- **WHEN** a stream is sorted with `comparing()` over an extractor yielding keys of mutually incomparable types
- **THEN** a `TypeError` is raised

#### Scenario: a bool-valued key is a legitimate key, not an error
- **WHEN** a stream is sorted with `comparing()` over an extractor returning `bool` values
- **THEN** no error is raised and the elements are ordered with `False` before `True`

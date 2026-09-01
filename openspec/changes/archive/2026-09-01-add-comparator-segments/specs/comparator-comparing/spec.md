## MODIFIED Requirements

### Requirement: comparing() builds a Comparator from a key extractor
`comparing(key_extractor)` SHALL return a value satisfying the `Comparator`
contract that orders two elements by comparing the keys the extractor produces
for them: negative when the first element's key orders before the second's, zero
when the keys are equivalent, and positive when it orders after. `comparing()`
SHALL additionally accept an optional second positional argument, a
`key_comparator`, in which case the extracted keys are ordered by that
comparator rather than by their natural ordering; the requirements for a
supplied ordering are stated in `comparator-key-comparator`. The result SHALL be
accepted anywhere a `Comparator` is accepted — `sorted()`, `min()` and `max()`
on `Stream`, and the `min_by()` and `max_by()` collectors — with no change to
those signatures.

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

#### Scenario: omitting the key comparator preserves natural key ordering
- **WHEN** `comparing()` is called with a key extractor alone
- **THEN** the keys are ordered naturally, exactly as before the second argument existed

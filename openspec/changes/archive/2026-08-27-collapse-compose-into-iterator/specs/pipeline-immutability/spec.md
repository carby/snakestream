## MODIFIED Requirements

### Requirement: Using an already-extended reference raises
Once a `Stream` instance has been used to build a new instance (via any intermediate operation or `sequential()`/`parallel()`), any further call on that same, now-superseded reference — whether an intermediate operation or a terminal operation (`collect`, `reduce`, `for_each`, `for_each_ordered`, `find_any`, `find_first`, `max`, `min`, `all_match`, `any_match`, `none_match`, `count`, `to_array`, `iterator`) — SHALL raise `IllegalStateException`.

This invalidation check SHALL also apply when an already-extended `Stream` is supplied to the library as an argument, not only when a method is called directly on it: passing such a reference to `Stream.concat()`, or returning it from a `flat_map()` mapper, SHALL raise `IllegalStateException`. `concat()`'s check SHALL fire at the time `concat()` is called, not deferred to the first pull of the concatenated stream. A `flat_map()` mapper's check SHALL fire when the mapper's returned stream is composed for iteration, before any of its elements are pulled.

A `Stream` that was merely *consumed* by a terminal operation, but never *extended* by an intermediate operation or mode switch, is unaffected by either check — the existing "repeat terminal consumption of an unextended reference" requirement below already governs that case in both positions.

#### Scenario: Extending an already-extended reference raises
- **WHEN** `s.map(f)` has already been called on `s`, and `s.filter(g)` is subsequently called on the same `s`
- **THEN** `s.filter(g)` raises `IllegalStateException`

#### Scenario: Terminally consuming an already-extended reference raises
- **WHEN** `s.map(f)` has already been called on `s`, and `s.collect(to_list())` is subsequently awaited on the same `s`
- **THEN** it raises `IllegalStateException`

#### Scenario: The new instance returned by the extending call is unaffected
- **WHEN** `s2 = s.map(f)` has been called on `s`
- **THEN** further intermediate or terminal operations on `s2` succeed normally

#### Scenario: Passing an already-extended stream to concat() raises
- **WHEN** `s.map(f)` has already been called on `s` (superseding `s`), and `s` is then passed as an argument to `Stream.concat(s, other)`
- **THEN** `Stream.concat(s, other)` raises `IllegalStateException` at call time, before any element is pulled from either argument

#### Scenario: Returning an already-extended stream from a flat_map() mapper raises
- **WHEN** a `flat_map()` mapper returns a `Stream` instance that has already been used to build a further instance
- **THEN** consuming the outer chain raises `IllegalStateException` when that mapper's returned stream is composed for iteration, matching the same-reference behavior when the receiver itself is used directly

#### Scenario: A merely-consumed (never extended) stream passed to concat() does not raise
- **WHEN** a `Stream` instance that has never been extended, but has already been terminally consumed once, is passed to `Stream.concat()`
- **THEN** `concat()` does not raise on account of invalidation; the existing "repeat terminal consumption of an unextended reference" requirement governs what elements it yields

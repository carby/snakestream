## Purpose

Numeric reducing collectors for use with `Stream.collect()`, mirroring
Java's `Collectors.counting()`, `summingInt`/`summingLong`/`summingDouble`,
and `averagingInt`/`averagingLong`/`averagingDouble` statics.

## Requirements

### Requirement: `counting()` collector factory
`collector.py` SHALL provide a `counting()` function that returns a
`Collector` counting the elements it accumulates and finishing to that `int`
count — usable with `Stream.collect(collector)`.

#### Scenario: Non-empty stream is counted
- **WHEN** `Stream.of([1, 2, 3]).collect(counting())` is called
- **THEN** the result is `3`

#### Scenario: Empty stream counts to zero
- **WHEN** `Stream.of([]).collect(counting())` is called
- **THEN** the result is `0`

### Requirement: `summing_int()`/`summing_long()` collector factories
`collector.py` SHALL provide `summing_int(mapper)` and `summing_long(mapper)`
functions, each returning a collector that maps every pulled element via
`mapper` (sync or async) and returns the `int` sum of the mapped values.
Both functions SHALL behave identically, mirroring Java's `Collectors
.summingInt`/`summingLong` under separate names despite Python having no
`int`/`long` distinction.

#### Scenario: summing_int sums mapped values
- **WHEN** `Stream.of(["a", "bb", "ccc"]).collect(summing_int(len))` is called
- **THEN** the result is `6`

#### Scenario: summing_long behaves identically to summing_int
- **WHEN** `Stream.of(["a", "bb", "ccc"]).collect(summing_long(len))` is called
- **THEN** the result is `6`

#### Scenario: summing_int on an empty stream returns zero
- **WHEN** `Stream.of([]).collect(summing_int(len))` is called
- **THEN** the result is `0`

#### Scenario: async mapper is awaited
- **WHEN** `Stream.of([1, 2, 3]).collect(summing_int(async_double))` is called with an async mapper doubling its input
- **THEN** the result is `12`

### Requirement: `summing_double()` collector factory
`collector.py` SHALL provide a `summing_double(mapper)` function returning a
collector that maps every pulled element via `mapper` (sync or async) and
returns the `float` sum of the mapped values, coercing each mapped value to
`float` before accumulating.

#### Scenario: summing_double sums as float
- **WHEN** `Stream.of([1, 2, 3]).collect(summing_double(lambda x: x))` is called
- **THEN** the result is `6.0` and is a `float`

#### Scenario: summing_double on an empty stream returns 0.0
- **WHEN** `Stream.of([]).collect(summing_double(lambda x: x))` is called
- **THEN** the result is `0.0`

### Requirement: `averaging_int()`/`averaging_long()`/`averaging_double()` collector factories
`collector.py` SHALL provide `averaging_int(mapper)`, `averaging_long(mapper)`,
and `averaging_double(mapper)` functions, each returning a collector that
maps every pulled element via `mapper` (sync or async) and returns the
arithmetic mean of the mapped values as a `float`. All three SHALL behave
identically, mirroring Java's `Collectors.averagingInt`/`averagingLong`/
`averagingDouble` under separate names despite Python having no `int`/
`long`/`double` distinction. An empty stream SHALL yield `0.0`, matching
Java's `Collectors.averaging*` javadocs.

#### Scenario: averaging_int computes the mean
- **WHEN** `Stream.of([1, 2, 3, 4]).collect(averaging_int(lambda x: x))` is called
- **THEN** the result is `2.5`

#### Scenario: averaging_long behaves identically to averaging_int
- **WHEN** `Stream.of([1, 2, 3, 4]).collect(averaging_long(lambda x: x))` is called
- **THEN** the result is `2.5`

#### Scenario: averaging_double behaves identically to averaging_int
- **WHEN** `Stream.of([1, 2, 3, 4]).collect(averaging_double(lambda x: x))` is called
- **THEN** the result is `2.5`

#### Scenario: averaging on an empty stream returns 0.0
- **WHEN** `Stream.of([]).collect(averaging_int(lambda x: x))` is called
- **THEN** the result is `0.0`

### Requirement: `counting()`, `summing_int()` and `summing_long()` declare `UNORDERED`

The collectors returned by `counting()`, `summing_int(mapper)` and
`summing_long(mapper)` SHALL declare the `UNORDERED` characteristic.

The declaration SHALL be true of the behaviour and not merely asserted. Counting
the same elements in any order yields the same `int`; summing the same mapped
`int` values in any order yields the same `int`, because integer addition in
Python is exact and associative. Each therefore meets the test `UNORDERED`
imposes (see the `collector-protocol` capability): any two orderings of the same
elements collect to a result that compares equal under `==`.

Java's javadoc documents characteristics for exactly three factories —
`toSet()`, `groupingByConcurrent()` and `toConcurrentMap()` — and is silent for
these. OpenJDK gives them `CH_ID`/`CH_NOID` in a private field of
`Collectors.java`, because Java's `UNORDERED` governs its *combine* strategy,
where an associative reduction is safe either way and the mark buys nothing.
This library's `UNORDERED` governs a *delivery barrier* instead, so the same
declaration buys something here that it does not buy in Java. Declaring it
SHALL therefore be treated as consistent with Java's documented contract rather
than a divergence from it.

#### Scenario: counting() reports UNORDERED
- **WHEN** the collector returned by `counting()` is asked for its characteristics
- **THEN** `UNORDERED` is present

#### Scenario: summing_int() and summing_long() report UNORDERED
- **WHEN** the collectors returned by `summing_int(mapper)` and
  `summing_long(mapper)` are asked for their characteristics
- **THEN** `UNORDERED` is present on both

#### Scenario: The declaration matches the behaviour
- **WHEN** two streams carrying the same elements in different orders are each
  collected with `counting()`, and again with `summing_int(mapper)`
- **THEN** the two counts are equal and the two sums are equal

#### Scenario: The mark removes the delivery barrier under racing
- **WHEN** an ordered racing pipeline is collected with `counting()` or
  `summing_int(mapper)`
- **THEN** no reorder barrier is engaged, no element is held back waiting for an
  earlier one, and the result equals the sequential pipeline's result

### Requirement: The floating-point numeric collectors SHALL NOT declare `UNORDERED`

The collectors returned by `summing_double(mapper)`, `averaging_int(mapper)`,
`averaging_long(mapper)` and `averaging_double(mapper)` SHALL NOT declare the
`UNORDERED` characteristic, and SHALL NOT be marked by any later change.

The exclusion is a statement of fact about the behaviour, not a convention held
open for review. Floating-point addition is not associative, so summing the same
mapped values in two different orders can produce results that differ in the
last place and compare unequal under `==`. These collectors are order-*sensitive
in fact*, which is a firmer exclusion than merely being left undeclared: a later
pass revisiting the marking question SHALL treat them as closed.

`averaging_*` is included because it divides an accumulated floating-point sum,
inheriting the same non-associativity, and this holds for `averaging_int` and
`averaging_long` too despite their `int` inputs.

#### Scenario: The floating-point collectors report no UNORDERED
- **WHEN** the collectors returned by `summing_double(mapper)`,
  `averaging_int(mapper)`, `averaging_long(mapper)` and
  `averaging_double(mapper)` are asked for their characteristics
- **THEN** `UNORDERED` is absent from every one of them

#### Scenario: A floating-point sum is fed in encounter order under racing
- **WHEN** an ordered racing pipeline is collected with `summing_double(mapper)`
- **THEN** the delivery barrier is engaged and the result equals the sequential
  pipeline's result exactly, bit for bit

### Requirement: `counting()`, `summing_int()` and `summing_long()` declare a combiner

`counting()`'s collector SHALL declare a `combiner` that adds two partial
counts. `summing_int()`'s and `summing_long()`'s collectors SHALL each
declare a `combiner` that adds two partial integer totals. Integer addition
is exact and associative, so partitioning changes nothing about the result -
the same ground these three already declare `UNORDERED` on.

#### Scenario: Parallel counting over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `counting()` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: Parallel summing_int over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `summing_int(mapper)` under `.parallel()`
- **THEN** the result equals the sequential result

### Requirement: The floating-point numeric collectors permanently decline a combiner

`summing_double()` and **all three** of `averaging_int()`/`averaging_long()`/
`averaging_double()` SHALL declare no `combiner`. Each accumulates into a
`float` running total (`summing_double`'s `_SumBox.total`; every `averaging_*`
shares one `_averaging()` whose `_AvgBox.total` is a `float`), and float
addition is not associative: partitioning would change the summation order
and so the result. `averaging_int()` and `averaging_long()` are excluded
despite their integral element types, because the accumulator they share
with `averaging_double()` divides a `float` regardless of what is mapped
into it. This is a stronger, permanent exclusion — not merely an
undeclared trait a later pass might add.

#### Scenario: summing_double declares no combiner
- **WHEN** `summing_double(mapper).combiner` is read
- **THEN** it is `None`, and a `.parallel()` collection with it is not partitioned - its result is bit-for-bit identical to the sequential one

#### Scenario: averaging_int declares no combiner despite an integral element type
- **WHEN** `averaging_int(mapper).combiner` is read
- **THEN** it is `None`

#### Scenario: averaging_long and averaging_double declare no combiner
- **WHEN** `averaging_long(mapper).combiner` and `averaging_double(mapper).combiner` are each read
- **THEN** both are `None`

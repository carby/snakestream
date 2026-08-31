## ADDED Requirements

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

## Purpose

Defines what happens when a reduction is split across the parallel executor's batches: when a terminal is partitioned rather than fed a single container, how the partial results are merged, and the contract a caller's `combiner` and `identity` must satisfy for the partitioned answer to equal the sequential one. Java's `Collector.combiner()` and the three-argument `reduce()` are the surfaces this sits behind.

## ADDED Requirements

### Requirement: `Stream.reduce()` gains a three-argument overload

`Stream.reduce()` SHALL accept a third overload, `reduce(identity,
accumulator, combiner)`, mirroring Java's `<U> U reduce(U identity,
BiFunction<U,? super T,U> accumulator, BinaryOperator<U> combiner)`. The
existing two overloads - `reduce(accumulator)` and `reduce(identity,
accumulator)` - SHALL continue to dispatch by argument count exactly as
before; this adds a third arity rather than changing either existing one.
`combiner` follows the same caller contract this capability states elsewhere
- associative, and `identity` an identity for it.

The type widening this overload might appear to need is already present on
the two-argument form (`Accumulator[T, R]` is `(T, T | R) -> T | R`), so the
combiner is the whole of what this overload adds.

#### Scenario: The one- and two-argument overloads dispatch unchanged
- **WHEN** `reduce(accumulator)` and `reduce(identity, accumulator)` are each called, exactly as before this overload existed
- **THEN** each dispatches to its own existing behavior, and `combiner` plays no part

#### Scenario: The three-argument overload dispatches and combines
- **WHEN** `reduce(identity, accumulator, combiner)` is called under `.parallel()` on a source spanning more than one batch
- **THEN** `combiner` is invoked at least once, and the result equals the sequential result for the same three arguments

#### Scenario: The three-argument overload under .sequential() matches the two-argument form
- **WHEN** `reduce(identity, accumulator, combiner)` and `reduce(identity, accumulator)` are each called under `.sequential()` with the same `identity` and `accumulator`
- **THEN** the two results are equal

### Requirement: A reduction partitions only when a combiner is supplied
A terminal reduction SHALL accumulate into a single container unless **both** conditions hold: the stream is running under a partitioning executor, and the reduction carries a combiner. Where either is absent, the reduction SHALL fold every element into one container in encounter order, exactly as it does today.

A reduction with no combiner SHALL NOT be partitioned on any executor. The absence of a combiner is the caller declining to assert associativity, and a reduction may not assume it.

Under the sequential executor a reduction SHALL produce exactly one partition, so a supplied combiner SHALL NOT be invoked. Supplying one SHALL remain valid and SHALL change nothing about the result.

#### Scenario: No combiner means no partitioning
- **WHEN** `collect(collector)` is called under `.parallel()` with a collector whose combiner is absent
- **THEN** every element is accumulated into a single container and the result equals the sequential result

#### Scenario: A combiner under the sequential executor is never invoked
- **WHEN** `.sequential()` is used with a reduction carrying a combiner
- **THEN** the combiner is not invoked, and the result equals what the same reduction produces without one

#### Scenario: A combiner under the parallel executor is invoked
- **WHEN** a stream whose source spans more than one batch is reduced under `.parallel()` with a combiner
- **THEN** the combiner is invoked at least once, and the result equals the sequential result

### Requirement: Partitions are merged in encounter order
Where a reduction is partitioned, each partition SHALL accumulate a contiguous run of the stream's elements, and the partial containers SHALL be merged in the order those runs appear in encounter order — earlier partition first.

Merging SHALL NOT require the combiner to be commutative. Contiguous partitions merged left to right need associativity only, which is the assumption Java makes and the only one a caller supplying a combiner has declared.

This SHALL hold whether or not the pipeline has been declared `unordered()`. `unordered()` releases the requirement to *deliver* in encounter order; it does not license merging partial reductions in an arbitrary order, because doing so would demand commutativity the caller never asserted.

#### Scenario: Merge order follows encounter order
- **WHEN** a stream is reduced under `.parallel()` with a combiner that is associative but not commutative — string concatenation, for example
- **THEN** the result equals the sequential result, not a permutation of it

#### Scenario: An unordered pipeline still merges in order
- **WHEN** the same reduction is run on a pipeline with `unordered()` queued
- **THEN** the partitions are still merged in encounter order and the result is unchanged

#### Scenario: An element belongs to exactly one partition
- **WHEN** a partitioned reduction completes
- **THEN** every element of the stream has been accumulated into exactly one partition — none dropped, none accumulated twice

### Requirement: The caller's combiner and identity carry a contract
A caller supplying a combiner SHALL be understood to assert that it is **associative**: `combine(combine(a, b), c)` and `combine(a, combine(b, c))` produce equal results.

For the three-argument `reduce(identity, accumulator, combiner)`, `identity` SHALL additionally be an **identity for the combiner**: `combine(identity, u)` SHALL equal `u` for every `u` the accumulation can produce. Each partition begins from `identity`, so a value that is not an identity for the combiner contributes once per partition and the parallel result diverges from the sequential one.

These are contracts on the caller, not conditions the library SHALL verify. A combiner that is not associative, or an identity that is not an identity, SHALL produce an unspecified result rather than a diagnosed error — matching Java, which states the same requirement and likewise does not check it.

#### Scenario: A non-identity identity diverges, and that is the caller's error
- **WHEN** `reduce(identity, accumulator, combiner)` is called under `.parallel()` with an `identity` that is not an identity for `combiner`
- **THEN** the result is unspecified and MAY differ from the sequential result; this SHALL be documented rather than detected

#### Scenario: A correct identity gives the sequential answer
- **WHEN** `reduce(identity, accumulator, combiner)` is called under `.parallel()` with an `identity` that is an identity for `combiner` and an associative `combiner`
- **THEN** the result equals the sequential result for the same arguments

### Requirement: A combiner is declared only where the merge is associative over the accumulation type
A collector SHALL declare a combiner only where merging two partial containers is associative **over the type actually accumulated**, not merely over the type the caller sees.

A collector accumulating in a floating-point type SHALL NOT declare a combiner, floating-point addition not being associative: partitioning would change the summation order and so the result. This SHALL apply to the whole family that accumulates in `float`, including those whose element type is integral.

A collector whose merge behaviour depends on a caller-supplied function that is not required to be associative SHALL NOT declare a combiner.

Declaring a combiner SHALL be independent of declaring `Characteristics.UNORDERED`. The two answer different questions — whether delivery order may be disregarded, versus whether partial results may be merged — and a collector MAY declare either without the other.

#### Scenario: The float-accumulating family declines a combiner
- **WHEN** a collector accumulates into a floating-point running total
- **THEN** it declares no combiner, and a reduction using it is not partitioned, so its result under `.parallel()` is bit-for-bit what it is sequentially

#### Scenario: A caller-supplied merge is not lifted into a combiner
- **WHEN** a collector takes a merge function from the caller that is not required to be associative
- **THEN** it declares no combiner, and the form of the same collector that takes no such function MAY declare one

#### Scenario: Combinable and unordered are independent
- **WHEN** a collector is examined for both properties
- **THEN** declaring a combiner neither implies nor is implied by declaring `Characteristics.UNORDERED`

### Requirement: A composing collector derives its combiner from its downstream
A collector that wraps a downstream collector SHALL declare a combiner only where its downstream declares one, and its combiner SHALL merge by combining each downstream container with its counterpart. Where the downstream declares none, the composing collector SHALL declare none.

This is the rule already used for `Characteristics`, applied to the same composition, so a caller does not have to reason about the two properties differently.

#### Scenario: A composite over a combinable downstream partitions
- **WHEN** a grouping collector is built over a downstream that declares a combiner
- **THEN** the grouping collector declares one, and a reduction using it under `.parallel()` gives the sequential result

#### Scenario: A composite over a non-combinable downstream does not
- **WHEN** a grouping collector is built over a downstream that declares no combiner
- **THEN** the grouping collector declares none, the reduction is not partitioned, and the result is still the sequential one

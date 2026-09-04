## Purpose

Defines `Stream.spliterator()` and the `Spliterator` it returns — Java's parallel-decomposition iterator, the object that splits a source into contiguous pieces separate workers traverse. It is both a public parity surface and the mechanism the parallel executor is built on, so the contract stated here is the one the executor relies on rather than a description written alongside it.

## Requirements

### Requirement: spliterator() exposes the composed pipeline as a decomposable traversal
`Stream.spliterator()` SHALL compose the stream's currently-queued chain of intermediate operations and return a `Spliterator[T]` over the resulting elements, without pulling any elements from the source. It SHALL follow the same non-destructive composition contract as `iterator()`: the chain is neither drained nor mutated.

`spliterator()` SHALL be a terminal-ish operation in the same sense `iterator()` is — it hands the caller something that produces elements, and the caller drives it.

#### Scenario: spliterator() returns without consuming
- **WHEN** `.spliterator()` is called on a stream with a queued chain
- **THEN** a `Spliterator` is returned and no element has been pulled from the underlying source

#### Scenario: Traversing a spliterator yields the pipeline's elements
- **WHEN** a caller traverses the returned `Spliterator` to exhaustion
- **THEN** it yields the same elements, in the same order, that `collect(to_list())` would have produced for an equivalent chain

### Requirement: try_advance consumes one element at a time
`Spliterator.try_advance(action)` SHALL pull at most one element, invoke `action` with it, and return `True`; when no element remains it SHALL invoke nothing and return `False`. It SHALL be awaitable, since the underlying source is asynchronous, and `action` MAY be sync or async as every other user-supplied callable in this library may.

#### Scenario: try_advance reports whether it advanced
- **WHEN** `try_advance(action)` is awaited on a spliterator with elements remaining
- **THEN** `action` is invoked exactly once with the next element and the call returns `True`

#### Scenario: try_advance on an exhausted spliterator
- **WHEN** `try_advance(action)` is awaited on a spliterator whose elements are exhausted
- **THEN** `action` is not invoked and the call returns `False`

### Requirement: try_split yields a contiguous prefix
`Spliterator.try_split()` SHALL either return a new `Spliterator` covering a **contiguous prefix** of this spliterator's remaining elements — leaving this one positioned over the remainder — or return `None` when it declines to split.

Contiguity is the load-bearing property and SHALL NOT be weakened to "some subset". It is what allows two independently accumulated partial results to be combined on associativity alone, without assuming commutativity; a decomposition that handed out interleaved subsequences would require the stronger assumption and would not be a spliterator.

`try_split()` SHALL return `None` when the remaining elements are too few to be worth dividing, so that a caller looping on it terminates.

#### Scenario: A split covers a contiguous prefix
- **WHEN** `try_split()` returns a spliterator
- **THEN** the returned spliterator's elements are a contiguous run of the source's encounter order, and this spliterator's remaining elements continue immediately after it, with no element in both and none skipped

#### Scenario: Splits and the remainder reconstitute the stream
- **WHEN** a caller repeatedly calls `try_split()` until it returns `None`, traverses every returned spliterator and then this one, concatenating the results in split order
- **THEN** the concatenation equals the elements the stream would have produced in encounter order

#### Scenario: Splitting terminates
- **WHEN** `try_split()` is called repeatedly on a spliterator over a finite source
- **THEN** it SHALL eventually return `None` rather than splitting indefinitely

#### Scenario: An unsized source is split by draining batches
- **WHEN** `try_split()` is called on a spliterator over a source whose size is unknown (a generator, an async iterator)
- **THEN** it SHALL drain a bounded batch of elements to form the returned spliterator, rather than declining to split because the size is unknown

### Requirement: estimate_size reports what is known, and says when nothing is
`Spliterator.estimate_size()` SHALL return an estimate of the number of elements remaining, or a distinguished unknown value when the source cannot report one. It SHALL NOT consume elements to answer.

A source that cannot be sized SHALL report unknown rather than guessing, and a caller SHALL NOT treat unknown as zero.

#### Scenario: A sized source reports its remaining count
- **WHEN** `estimate_size()` is called on a spliterator over a source of known length from which nothing has been consumed
- **THEN** it returns that length, without pulling any element

#### Scenario: An unsized source reports unknown
- **WHEN** `estimate_size()` is called on a spliterator over a generator
- **THEN** it returns the distinguished unknown value, not zero and not a guess

### Requirement: characteristics reports the traversal's properties
`Spliterator.characteristics()` SHALL report the set of properties that hold of this traversal — at minimum whether it is `ORDERED` and whether it is `SIZED`. A characteristic SHALL be reported only when it actually holds: reporting `ORDERED` for a traversal whose order is not meaningful would mislead a caller into relying on it.

A spliterator taken from a stream on which `unordered()` has been declared SHALL NOT report `ORDERED`.

#### Scenario: An ordered stream's spliterator reports ORDERED
- **WHEN** `characteristics()` is called on a spliterator taken from a stream with no `unordered()` declared
- **THEN** the reported set contains `ORDERED`

#### Scenario: An unordered stream's spliterator does not report ORDERED
- **WHEN** `characteristics()` is called on a spliterator taken from a stream with `unordered()` queued
- **THEN** the reported set does not contain `ORDERED`

#### Scenario: A split inherits its parent's characteristics
- **WHEN** `try_split()` returns a spliterator from a parent reporting a given set of characteristics
- **THEN** the returned spliterator reports characteristics consistent with the parent's, so that a recursive decomposition does not silently gain or lose a property

### Requirement: for_each_remaining traverses the rest
`Spliterator.for_each_remaining(action)` SHALL invoke `action` with every element remaining in this spliterator, in encounter order where the traversal reports `ORDERED`, and SHALL leave the spliterator exhausted. It SHALL be awaitable and SHALL accept a sync or async `action`.

#### Scenario: for_each_remaining consumes everything left
- **WHEN** `for_each_remaining(action)` is awaited after some elements have already been consumed by `try_advance`
- **THEN** `action` is invoked once per remaining element, in encounter order, and a subsequent `try_advance` returns `False`

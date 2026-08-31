## REMOVED Requirements

### Requirement: An ordered drive is available regardless of stream mode
**Reason**: The requirement named two users of the ordered drive and this change
removes one of them, which changes both its statement and the scenarios that
pin it — `for_each_ordered()` no longer requests a single-flight push and its
scenario's premise is gone. It is restated below with `find_first()` as the sole
user.

Its scenario "An unordered parallel `find_first()` still races ... behaves as
`find_any()` does" is dropped rather than restated, because it is **already
wrong**: it contradicts the `stream-find-first` capability, which requires the
true leftmost element on an unordered stream, and it contradicts the shipped
implementation, which names the sequential executor unconditionally. It is the
same stale rule `order-stateful-ops-under-racing` corrected in
`stream-execution-model` and missed in this file.

**Migration**: No behavioural migration for `find_first()`, whose ordered drive
is unchanged here. `for_each_ordered()` callers see the change described in the
`stream-foreach-ordered` capability: encounter order for the consumer is
preserved, and the chain producing those elements now races.

## ADDED Requirements

### Requirement: An ordered drive is available regardless of stream mode, and find_first() is its only user

A terminal SHALL be able to request a strictly ordered, single-flight push
through the chain, bypassing any racing execution the stream's executor would
otherwise use. It SHALL do so by naming the sequential executor explicitly.

`find_first()` SHALL use it unconditionally, and SHALL be its only user.

`for_each_ordered()` SHALL NOT use it. An ordered `for_each_ordered()` obtains
encounter order from the racing executor's delivery barrier instead, which
orders the handing over of finished elements without serializing the chain that
produced them; see the `stream-foreach-ordered` capability.

The ordered drive SHALL deliver elements to the terminal in source encounter
order whichever executor the stream carries.

#### Scenario: An ordered parallel find_first() returns the true first element
- **WHEN** `find_first()` is called on an ordered parallel stream whose chain reorders arrival timing
- **THEN** it returns the first element in source encounter order, not the first to arrive

#### Scenario: An unordered parallel find_first() also returns the true first element
- **WHEN** `find_first()` is called on a parallel stream that has been marked `unordered()`
- **THEN** it still uses the ordered drive and returns the first element in source encounter order, per the `stream-find-first` capability

#### Scenario: for_each_ordered() stays in source order without the ordered drive
- **WHEN** `for_each_ordered(consumer)` is called on a parallel stream whose chain reorders arrival timing (for example a `map()` with a positional delay)
- **THEN** `consumer` is invoked with the elements in source encounter order, and the chain is not driven single-flight

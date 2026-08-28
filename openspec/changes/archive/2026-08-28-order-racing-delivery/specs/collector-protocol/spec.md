## MODIFIED Requirements

### Requirement: `Characteristics` is the public vocabulary for a collector's traits

The library SHALL expose a public `Characteristics` enumeration, mirroring
Java's `Collector.Characteristics`, whose members describe traits of a
collector that a caller or the execution machinery may act on.

It SHALL define exactly one member, `UNORDERED`, meaning the collector does not
observe the encounter order of the elements it accumulates: for any two
orderings of the same elements, the collected result SHALL be equal.

`IDENTITY_FINISH` and `CONCURRENT` SHALL NOT be defined. The first is already
observable as the absence of a finisher, and defining it would allow two
statements of one fact to disagree. The second describes accumulating into one
shared container from independently reduced partitions, which the library has
no execution mode to produce — the `combiner` is accepted for signature parity
and never invoked. The enumeration SHALL be shaped so that either can be added
later without changing the meaning of `UNORDERED`.

`UNORDERED` SHALL be read by `collect()` to decide whether the pipeline must
deliver elements to the collector in encounter order. On an ordered racing
pipeline, a collector declaring `UNORDERED` SHALL be fed as the race resolves
elements, with no reorder barrier and no head-of-line delay; a collector not
declaring it SHALL be fed in encounter order (see the `racing-encounter-order`
capability).

Declaring `UNORDERED` SHALL NOT change the *value* a correct collector
produces. A collector declaring it asserts that its result is equal for any
ordering of the same elements; where that assertion holds, the declaration is
observable only as reduced latency and memory, never as a different result.
Where a caller declares it on a collector for which it does not hold, the
resulting order is unspecified and the caller has broken the contract.

Under the sequential executor the declaration SHALL have no effect at all.

#### Scenario: UNORDERED is a member of the public enumeration
- **WHEN** `Characteristics.UNORDERED` is referenced from the library's public
  surface
- **THEN** it resolves to a member of the `Characteristics` enumeration

#### Scenario: The other two Java characteristics are absent
- **WHEN** `IDENTITY_FINISH` or `CONCURRENT` is looked up on `Characteristics`
- **THEN** neither is defined

#### Scenario: Declaring UNORDERED does not change what is collected
- **WHEN** a sequential stream is collected with a collector declaring
  `UNORDERED`, and again with an otherwise identical collector declaring nothing
- **THEN** both collections produce equal results

#### Scenario: UNORDERED removes the delivery barrier under racing
- **WHEN** an ordered racing pipeline is collected with a collector declaring
  `UNORDERED`, and again with an otherwise identical collector declaring nothing
- **THEN** the declaring collection engages no reorder barrier and holds no
  element back, while the other delivers in encounter order

#### Scenario: to_set() takes the order-blind path
- **WHEN** an ordered racing pipeline is collected with `to_set()`
- **THEN** the collected set is correct and no reorder barrier was engaged

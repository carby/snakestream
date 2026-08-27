## ADDED Requirements

### Requirement: `collecting_and_then()` carries its downstream's characteristics

The collector returned by `collecting_and_then(downstream, finisher)` SHALL
declare exactly the characteristics `downstream` declares, matching Java, where
`collectingAndThen()` derives from the downstream collector.

Accumulation is `downstream`'s unchanged, and `finisher` is applied once to the
finished result rather than per element, so it cannot introduce a dependence on
the order the elements arrived in. A collector that did not observe encounter
order does not begin to observe it by having its result transformed.

Java's `collectingAndThen()` additionally clears `IDENTITY_FINISH` from what it
derives, since adding a finisher is precisely what makes the finish
non-identity. That clearing is not specified here because `IDENTITY_FINISH` is
not defined; if it is ever added, the clearing SHALL be added with it.

#### Scenario: Adapting an unordered downstream stays unordered
- **WHEN** the collector returned by `collecting_and_then(to_set(), frozenset)`
  is asked for its characteristics
- **THEN** `UNORDERED` is present

#### Scenario: Adapting an ordered downstream stays ordered
- **WHEN** the collector returned by `collecting_and_then(to_list(), tuple)` is
  asked for its characteristics
- **THEN** `UNORDERED` is absent

#### Scenario: Composing the two adapters derives through both
- **WHEN** the collector returned by
  `collecting_and_then(mapping(len, to_set()), frozenset)` is asked for its
  characteristics
- **THEN** `UNORDERED` is present

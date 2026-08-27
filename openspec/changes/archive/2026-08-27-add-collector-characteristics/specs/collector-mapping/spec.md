## ADDED Requirements

### Requirement: `mapping()` carries its downstream's characteristics

The collector returned by `mapping(mapper, downstream)` SHALL declare exactly
the characteristics `downstream` declares, matching Java, where `mapping()`
derives its characteristics from the downstream collector rather than fixing
its own.

This follows from what `mapping()` is: it transforms each element on its way in
and then produces `downstream`'s result unchanged, so every trait of that
result is a trait of `downstream`. In particular, mapping into a downstream
that does not observe encounter order yields a collector that does not observe
it either, because the mapper is applied per element and cannot make the result
depend on position.

#### Scenario: Mapping into an unordered downstream is unordered
- **WHEN** the collector returned by `mapping(len, to_set())` is asked for its
  characteristics
- **THEN** `UNORDERED` is present

#### Scenario: Mapping into an ordered downstream is not unordered
- **WHEN** the collector returned by `mapping(len, to_list())` is asked for its
  characteristics
- **THEN** `UNORDERED` is absent

#### Scenario: Nested mapping derives through both levels
- **WHEN** the collector returned by `mapping(len, mapping(str, to_set()))` is
  asked for its characteristics
- **THEN** `UNORDERED` is present, derived from the innermost downstream

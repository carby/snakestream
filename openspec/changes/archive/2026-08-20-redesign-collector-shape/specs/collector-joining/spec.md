## MODIFIED Requirements

### Requirement: `joining()` collector factory
`collector.py` SHALL provide a `joining(delimiter: str = "", prefix: str = "", suffix: str = "")` function that returns a `Collector` accumulating the stream's `str` elements and finishing them into a single `str` — usable with `Stream.collect(collector)`. It SHALL support Java's three `Collectors.joining` overloads via default arguments: no-arg (empty delimiter/prefix/suffix), delimiter-only, and delimiter+prefix+suffix.

#### Scenario: No-arg joining concatenates with no delimiter
- **WHEN** `Stream.of(["a", "b", "c"]).collect(joining())` is called
- **THEN** the result is `"abc"`

#### Scenario: Delimiter-only joining
- **WHEN** `Stream.of(["a", "b", "c"]).collect(joining(", "))` is called
- **THEN** the result is `"a, b, c"`

#### Scenario: Delimiter, prefix, and suffix
- **WHEN** `Stream.of(["a", "b", "c"]).collect(joining(", ", "[", "]"))` is called
- **THEN** the result is `"[a, b, c]"`

#### Scenario: Single-element stream has no delimiter applied
- **WHEN** `Stream.of(["a"]).collect(joining(", "))` is called
- **THEN** the result is `"a"`

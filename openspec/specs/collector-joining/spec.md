## Purpose

String-concatenation collector for use with `Stream.collect()`, mirroring
Java's `Collectors.joining()` / `joining(delimiter)` /
`joining(delimiter, prefix, suffix)` overloads.

## Requirements

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

### Requirement: Empty-stream behavior matches Java
An empty stream SHALL produce `prefix + suffix`, with the delimiter never used.

#### Scenario: Empty stream, no prefix/suffix
- **WHEN** `Stream.of([]).collect(joining(", "))` is called
- **THEN** the result is `""`

#### Scenario: Empty stream with prefix and suffix
- **WHEN** `Stream.of([]).collect(joining(", ", "[", "]"))` is called
- **THEN** the result is `"[]"`

### Requirement: Non-`str` elements raise `TypeError`
`joining()`'s collector SHALL raise `TypeError` if any pulled element is not a `str`, matching Java's `Collectors.joining()` being defined only on `Stream<CharSequence>`. No implicit stringification (e.g. via `str()`) SHALL occur.

#### Scenario: Non-string element raises
- **WHEN** `Stream.of(["a", 1, "c"]).collect(joining())` is called
- **THEN** a `TypeError` is raised

### Requirement: `joining()` declares a combiner

`joining()`'s collector SHALL declare a `combiner` that concatenates two
partial part-lists (the same list-of-parts accumulation `to_list()` uses),
merged before `delimiter`/`prefix`/`suffix` are ever applied — the finisher
runs once, on the fully-merged list.

#### Scenario: Parallel result over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `joining(delimiter=",")` under `.parallel()`
- **THEN** the result equals the sequential result

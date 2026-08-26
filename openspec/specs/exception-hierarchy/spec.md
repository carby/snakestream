## Purpose

Defines the public exception types this library raises and the common base
every one of them derives from, so a caller can catch anything snakestream
raised without enumerating the leaves.

## Requirements

### Requirement: `StreamException` is the base of every exception the library raises

The library SHALL expose a public `StreamException` from
`snakestream.exception`, deriving directly from `Exception`, and every
exception type the library defines and raises SHALL derive from it. As of
this change those are `StreamBuildException` and `IllegalStateException`.

`StreamException` SHALL NOT be raised directly by the library — it exists to
be caught, not to be thrown — and SHALL NOT derive from any built-in
exception other than `Exception`. In particular it SHALL NOT derive from
`ValueError`, for the same reason `IllegalStateException` does not: a
stream-reuse error is not a `ValueError` under any reading.

Inserting this base SHALL NOT change either leaf's name, message, or the
conditions under which it is raised, so existing `except StreamBuildException`
and `except IllegalStateException` call sites SHALL continue to catch exactly
what they caught before.

#### Scenario: A build error is caught by the base
- **WHEN** `Stream.of([1, 2, 3]).collect(lambda c: c)` is awaited inside a `try` catching only `StreamException`
- **THEN** the `StreamBuildException` it raises is caught

#### Scenario: A reuse error is caught by the base
- **WHEN** a consumed stream reference is used again inside a `try` catching only `StreamException`
- **THEN** the `IllegalStateException` it raises is caught

#### Scenario: The existing leaf catches still work
- **WHEN** `except StreamBuildException` wraps a `collect()` call passed a non-`Collector`
- **THEN** the exception is caught, exactly as before this change

#### Scenario: The base is not a ValueError
- **WHEN** a `StreamException` is raised inside a `try` that catches only `ValueError`
- **THEN** it propagates uncaught

#### Scenario: Both leaves report the base as an ancestor
- **WHEN** `issubclass` is asked whether `StreamBuildException` and `IllegalStateException` derive from `StreamException`
- **THEN** both answer `True`, and `StreamException` derives from `Exception`

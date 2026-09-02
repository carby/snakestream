## MODIFIED Requirements

### Requirement: `StreamException` is the base of every exception the library raises

The library SHALL expose a public `StreamException` from
`snakestream.exception`, deriving directly from `Exception`, and every
exception type the library defines and raises SHALL derive from it. As of
this change those are `StreamBuildException`, `IllegalStateException` and
`ComparatorContractException`.

`StreamException` SHALL NOT be raised directly by the library — it exists to
be caught, not to be thrown — and SHALL NOT derive from any built-in
exception other than `Exception`. In particular it SHALL NOT derive from
`ValueError`, for the same reason `IllegalStateException` does not: a
stream-reuse error is not a `ValueError` under any reading.

That constraint binds the base alone. A **leaf** SHALL be permitted to derive
from a built-in exception in addition to its `StreamException` ancestry, and
SHALL do so only where the fault it reports genuinely is one of that built-in
kind, so that a caller catching the built-in keeps catching it. The base stays
narrow so `except StreamException` never widens into unrelated built-ins; a
leaf may be specific because it describes one fault.

Inserting this base SHALL NOT change any leaf's name, message, or the
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

#### Scenario: The comparator leaf reports both its ancestors
- **WHEN** `issubclass` is asked whether `ComparatorContractException` derives from `StreamException` and from `TypeError`
- **THEN** both answer `True`, and it derives from `StreamBuildException` as well

## ADDED Requirements

### Requirement: `ComparatorContractException` reports a comparator that breaks its contract

The library SHALL expose a public `ComparatorContractException` from
`snakestream.exception`, deriving from both `StreamBuildException` and
`TypeError`. It SHALL be raised where a user-supplied `Comparator` returns a
value that is not an `int`, as required by `comparator-contract`.

Deriving from `TypeError` SHALL keep every existing `except TypeError` around
a comparator-consuming operation catching exactly what it caught before;
deriving from `StreamBuildException` SHALL place it alongside the other fault
of the same kind — a comparator supplied in a shape the library cannot use —
so that one `except StreamBuildException` covers both. It SHALL NOT derive
from `ValueError`.

The exception's message SHALL be unchanged from the bare `TypeError` it
replaces, and the conditions under which it is raised SHALL be unchanged.

#### Scenario: A bool comparator is caught as a TypeError
- **WHEN** `Stream.of([3, 1, 2]).sorted(lambda a, b: a > b)` is collected inside a `try` catching only `TypeError`
- **THEN** the exception is caught, exactly as before this change

#### Scenario: A bool comparator is caught as a build error
- **WHEN** the same collection runs inside a `try` catching only `StreamBuildException`
- **THEN** the exception is caught

#### Scenario: A bool comparator is caught by the library base
- **WHEN** the same collection runs inside a `try` catching only `StreamException`
- **THEN** the exception is caught

#### Scenario: A bool comparator is not a ValueError
- **WHEN** the same collection runs inside a `try` catching only `ValueError`
- **THEN** it propagates uncaught

#### Scenario: The async comparator rejection is unaffected
- **WHEN** a bare async comparator is passed as a `comparing()` segment and rejected
- **THEN** a `StreamBuildException` is raised as before, and it is not a `ComparatorContractException`

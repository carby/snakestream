## MODIFIED Requirements

### Requirement: close() invokes every registered close handler

`Stream.close()` SHALL call every registered close handler, in the order they were registered, with no arguments. If one or more close handlers raise an exception, `close()` SHALL still invoke every remaining handler before raising; it SHALL NOT stop invoking handlers because an earlier handler raised. After all handlers have run, if any raised, `close()` SHALL raise the first exception that was raised, in encounter order.

When more than one handler raised, `close()` SHALL NOT discard the later exceptions. On interpreters that support attaching explanatory notes to an exception (Python 3.11 and later), `close()` SHALL attach one note per later exception to the exception it raises, in encounter order, each identifying that exception, so that the propagated traceback shows every failure. Which exception is raised SHALL remain the first one regardless: the notes are additional detail, not a change to what propagates. On interpreters without note support (Python 3.10), `close()` SHALL raise the first exception exactly as specified above, unmodified.

#### Scenario: close() with no handlers registered

- **WHEN** `close()` is called on a stream with no close handlers registered
- **THEN** no error is raised and nothing is invoked

#### Scenario: close() invokes all handlers in registration order

- **WHEN** `close()` is called on a stream with multiple close handlers registered
- **THEN** every handler is called exactly once, in the order they were registered

#### Scenario: A raising handler does not prevent later handlers from running

- **WHEN** `close()` is called on a stream with handlers `[bad, good]` registered in that order, and `bad` raises an exception when called
- **THEN** `good` is still called, and `close()` raises `bad`'s exception after both handlers have run

#### Scenario: Multiple raising handlers still all run, and the first exception is raised

- **WHEN** `close()` is called on a stream with handlers `[bad_a, bad_b]` registered in that order, both of which raise when called
- **THEN** both `bad_a` and `bad_b` are called, and `close()` raises `bad_a`'s exception (the first one encountered)

#### Scenario: The later exceptions' detail survives on the raised exception

- **WHEN** `close()` is called, on an interpreter with note support, on a stream with handlers `[bad_a, bad_b, bad_c]` registered in that order, all three of which raise distinguishable exceptions
- **THEN** `close()` raises `bad_a`'s exception, and that exception carries notes identifying `bad_b`'s and `bad_c`'s exceptions, in that order

#### Scenario: A single raising handler gains no notes

- **WHEN** `close()` is called on a stream where exactly one handler raises
- **THEN** the raised exception is that handler's exception with no notes added by `close()`

#### Scenario: Interpreters without note support are unaffected

- **WHEN** `close()` is called, on an interpreter without note support, on a stream with two raising handlers
- **THEN** both handlers are called and the first exception is raised unmodified, with no error arising from the attempt to preserve the second

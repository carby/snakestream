## REMOVED Requirements

### Requirement: close() invokes every registered close handler

**Reason**: Superseded by the two ADDED requirements below, which split it. The requirement carried two contracts at once — which handlers run and in what order, and how their failures are reported — and only the second is affected by the floor raise. Splitting is also what lets the interpreter-dependent scenario go: it described `close()` on Python 3.10, the only interpreter lacking `BaseException.add_note()`, and 3.10 is no longer supported. A MODIFIED delta may not drop a scenario, so the requirement is removed and its two halves re-stated under names of their own.

**Migration**: None for any caller on a supported interpreter. Handler invocation, ordering, and which exception propagates are all restated verbatim; note attachment on 3.11+ is exactly what shipped before. Only the 3.10 fallback path is gone, and `requires-python >= 3.11` now refuses that interpreter at install time.

## ADDED Requirements

### Requirement: close() runs every registered close handler and raises the first failure

`Stream.close()` SHALL call every registered close handler, in the order they were registered, with no arguments. If one or more close handlers raise an exception, `close()` SHALL still invoke every remaining handler before raising; it SHALL NOT stop invoking handlers because an earlier handler raised. After all handlers have run, if any raised, `close()` SHALL raise the first exception that was raised, in encounter order.

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

### Requirement: close() preserves later handler failures as notes

When more than one handler raised, `close()` SHALL NOT discard the later exceptions. `close()` SHALL attach one note per later exception to the exception it raises, in encounter order, each identifying that exception, so that the propagated traceback shows every failure. Which exception is raised SHALL remain the first one regardless: the notes are additional detail, not a change to what propagates.

This SHALL be unconditional. `BaseException.add_note()` has existed since Python 3.11 and the supported floor is 3.11, so `close()` SHALL NOT branch on interpreter version and there is no supported interpreter on which it falls back to raising the first exception unmodified.

`close()` SHALL NOT raise a composite exception (an `ExceptionGroup`) when more than one handler raised. Java's `AbstractPipeline.close()` composes its handlers through `Streams.composeWithExceptions()`, which runs every handler, calls `addSuppressed()` on the first exception for each later one, and rethrows that first exception; it never throws a composite. First-exception-wins-with-the-rest-attached is therefore the contract being matched, and `add_note()` is its Python spelling — the same exception propagates, the rest ride along as detail. Raising an `ExceptionGroup` would change which exception type escapes `close()`, and so would be a divergence in observable API behaviour rather than an internal one. This is a settled decision on that ground alone. It was additionally deferred once because the matrix still carried Python 3.10, which has no `ExceptionGroup`; that objection is now spent, and its expiry changes nothing about the decision.

#### Scenario: The later exceptions' detail survives on the raised exception

- **WHEN** `close()` is called on a stream with handlers `[bad_a, bad_b, bad_c]` registered in that order, all three of which raise distinguishable exceptions
- **THEN** `close()` raises `bad_a`'s exception, and that exception carries notes identifying `bad_b`'s and `bad_c`'s exceptions, in that order

#### Scenario: A single raising handler gains no notes

- **WHEN** `close()` is called on a stream where exactly one handler raises
- **THEN** the raised exception is that handler's exception with no notes added by `close()`

#### Scenario: Note attachment is not conditioned on the interpreter

- **WHEN** `close()` is called with two raising handlers on any interpreter the distribution supports
- **THEN** the first exception is raised carrying a note for the second, with no version-dependent path that would raise it unmodified

## MODIFIED Requirements

### Requirement: on_close() registers a close handler

`Stream.on_close(close_handler)` SHALL append `close_handler` (a plain no-arg callable) to the stream's list of close handlers and SHALL return the same stream instance, following the mutate-and-return-self convention used by other chainable `Stream` methods.

#### Scenario: Registering a single close handler

- **WHEN** `on_close(handler)` is called on a stream
- **THEN** `handler` is added to the stream's close handlers, and the call returns the same stream instance

#### Scenario: Registering multiple close handlers preserves order

- **WHEN** `on_close(handler_a)` then `on_close(handler_b)` are both called on the same stream
- **THEN** both handlers are registered, in the order they were added

### Requirement: close() invokes every registered close handler

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

### Requirement: Close handlers propagate across sequential()/parallel() mode switches

`Stream.sequential()` and `Stream.parallel()` SHALL carry the calling stream's current close handlers over to the new stream instance they return.

#### Scenario: Close handlers survive a parallel() call

- **WHEN** a stream with a registered close handler calls `.parallel()`
- **THEN** the resulting stream's `close()` still invokes that handler

#### Scenario: Close handlers survive a sequential() call

- **WHEN** a parallel stream with a registered close handler calls `.sequential()`
- **THEN** the resulting stream's `close()` still invokes that handler

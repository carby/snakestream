## Purpose

Defines the `on_close()`/`close()` close-handler contract shared by `BaseStream`, `Stream`, and `ParallelStream` — Java's AutoClose equivalent. Covers registering close handlers, invoking them on `close()`, initializing a stream's close handlers at construction time (including via an explicit `close_handlers` argument), and carrying registered handlers across `sequential()`/`parallel()` mode switches.

## Requirements

### Requirement: on_close() registers a close handler

`BaseStream.on_close(close_handler)` SHALL append `close_handler` (a plain no-arg callable) to the stream's list of close handlers and SHALL return the same stream instance, following the mutate-and-return-self convention used by other chainable `BaseStream`/`Stream` methods.

#### Scenario: Registering a single close handler

- **WHEN** `on_close(handler)` is called on a stream
- **THEN** `handler` is added to the stream's close handlers, and the call returns the same stream instance

#### Scenario: Registering multiple close handlers preserves order

- **WHEN** `on_close(handler_a)` then `on_close(handler_b)` are both called on the same stream
- **THEN** both handlers are registered, in the order they were added

### Requirement: close() invokes every registered close handler

`BaseStream.close()` SHALL call every registered close handler, in the order they were registered, with no arguments.

#### Scenario: close() with no handlers registered

- **WHEN** `close()` is called on a stream with no close handlers registered
- **THEN** no error is raised and nothing is invoked

#### Scenario: close() invokes all handlers in registration order

- **WHEN** `close()` is called on a stream with multiple close handlers registered
- **THEN** every handler is called exactly once, in the order they were registered

### Requirement: A stream constructed with initial close handlers uses them

`Stream(source, close_handlers)` and `ParallelStream(source, close_handlers)` SHALL initialize the new stream's close handlers to the given list. `Stream(source)` / `ParallelStream(source)` (no `close_handlers` argument, or `None`) SHALL initialize the new stream with an empty list of close handlers.

#### Scenario: Constructing with an explicit close_handlers list

- **WHEN** `Stream(source, [handler])` is constructed
- **THEN** `close()` on the resulting stream invokes `handler`

#### Scenario: Constructing with no close_handlers argument

- **WHEN** `Stream(source)` is constructed without a `close_handlers` argument
- **THEN** `close()` on the resulting stream invokes nothing, and `on_close()` can still be used afterward to register handlers

### Requirement: Close handlers propagate across sequential()/parallel() mode switches

`sequential()` and `parallel()` (`BaseStream`) SHALL carry the calling stream's current close handlers over to the new stream instance they construct.

#### Scenario: Close handlers survive a parallel() call

- **WHEN** a stream with a registered close handler calls `.parallel()`
- **THEN** the resulting `ParallelStream`'s `close()` still invokes that handler

#### Scenario: Close handlers survive a sequential() call

- **WHEN** a `ParallelStream` with a registered close handler calls `.sequential()`
- **THEN** the resulting `Stream`'s `close()` still invokes that handler

## MODIFIED Requirements

### Requirement: A stream constructed with initial close handlers uses them

`Stream(source, close_handlers)` SHALL initialize the new stream's close handlers to the given list. `Stream(source)` (no `close_handlers` argument, or `None`) SHALL initialize the new stream with an empty list of close handlers. This holds whichever executor the resulting stream carries.

#### Scenario: Constructing with an explicit close_handlers list

- **WHEN** `Stream(source, [handler])` is constructed
- **THEN** `close()` on the resulting stream invokes `handler`

#### Scenario: Constructing with no close_handlers argument

- **WHEN** `Stream(source)` is constructed without a `close_handlers` argument
- **THEN** `close()` on the resulting stream invokes nothing, and `on_close()` can still be used afterward to register handlers

### Requirement: Close handlers propagate across sequential()/parallel() mode switches

`sequential()` and `parallel()` (`BaseStream`) SHALL carry the calling stream's current close handlers over to the new stream instance they return.

#### Scenario: Close handlers survive a parallel() call

- **WHEN** a stream with a registered close handler calls `.parallel()`
- **THEN** the resulting stream's `close()` still invokes that handler

#### Scenario: Close handlers survive a sequential() call

- **WHEN** a parallel stream with a registered close handler calls `.sequential()`
- **THEN** the resulting stream's `close()` still invokes that handler

## MODIFIED Requirements

### Requirement: on_close() registers a close handler

`Stream.on_close(close_handler)` SHALL append `close_handler` (a no-arg callable, whose result MAY be an awaitable) to the stream's list of close handlers and SHALL return the same stream instance, following the mutate-and-return-self convention used by other chainable `Stream` methods.

Registration SHALL NOT inspect, classify or reject a handler on the grounds of whether it is awaitable. Both kinds register identically and in one list; which of `close()`/`aclose()` can run a given handler is decided when it is invoked, not when it is registered. A handler MAY therefore be registered on a stream that is later closed synchronously, and the failure that follows is the one the `close()` requirement specifies rather than an error at `on_close()`.

Permitting an awaitable result aligns the close handler with every other user-supplied callable in this library — a predicate, mapper, comparator, consumer and accumulator each already permit a sync or an async implementation — and is a widening: every handler accepted before this requirement is still accepted, unchanged.

#### Scenario: Registering a single close handler

- **WHEN** `on_close(handler)` is called on a stream
- **THEN** `handler` is added to the stream's close handlers, and the call returns the same stream instance

#### Scenario: Registering multiple close handlers preserves order

- **WHEN** `on_close(handler_a)` then `on_close(handler_b)` are both called on the same stream
- **THEN** both handlers are registered, in the order they were added

#### Scenario: An async handler registers exactly as a sync one does

- **WHEN** `on_close(async_handler)` is called, where `async_handler` is defined with `async def`
- **THEN** it is registered like any other handler, the call returns the same stream instance, and nothing is raised at registration time

#### Scenario: Sync and async handlers share one ordered list

- **WHEN** `on_close(sync_a)`, `on_close(async_b)` and `on_close(sync_c)` are called in that order
- **THEN** all three are registered in that order, with no separation by kind

### Requirement: close() runs every registered close handler and raises the first failure

`Stream.close()` SHALL call every registered close handler, in the order they were registered, with no arguments. If one or more close handlers raise an exception, `close()` SHALL still invoke every remaining handler before raising; it SHALL NOT stop invoking handlers because an earlier handler raised. After all handlers have run, if any raised, `close()` SHALL raise the first exception that was raised, in encounter order.

`close()` SHALL remain synchronous and SHALL NOT await. A handler whose result is awaitable therefore cannot be run to completion by `close()`, and `close()` SHALL refuse it: it SHALL raise `StreamBuildException`, naming the handler and directing the caller to `aclose()` or `async with`. It SHALL NOT leave an un-awaited coroutine behind silently, and it SHALL NOT attempt to drive the awaitable itself — by starting an event loop, by reaching for a running one, or by any means that would make the outcome depend on whether a loop happens to be running.

The refusal SHALL be an ordinary per-handler failure and SHALL NOT be a special path: it joins the encounter-ordered list of failures exactly as a handler's own exception does, so every remaining handler still runs, the first failure in encounter order is still the one that propagates, and the later ones still ride along as notes.

Where the awaitable is returned by a callable that is not itself declared asynchronous, the refusal SHALL still be raised, but only after the handler has been called — the awaitability is undiscoverable before invocation. `close()` SHALL NOT claim in that case that the resource is untouched.

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

#### Scenario: close() refuses an async handler

- **WHEN** `close()` is called on a stream with a handler defined with `async def` registered
- **THEN** `StreamBuildException` is raised, and no un-awaited coroutine is left behind

#### Scenario: A refused handler does not stop the sync handlers around it

- **WHEN** `close()` is called on a stream with handlers `[sync_a, async_b, sync_c]` registered in that order
- **THEN** `sync_a` and `sync_c` are both invoked, and `close()` raises the `StreamBuildException` for `async_b`

#### Scenario: The refusal takes its place in encounter order

- **WHEN** `close()` is called on a stream with handlers `[bad, async_b]` registered in that order, where `bad` raises
- **THEN** `bad`'s exception is the one raised, carrying a note identifying the `StreamBuildException` for `async_b`

#### Scenario: A sync callable returning an awaitable is refused after being called

- **WHEN** `close()` is called on a stream with a handler defined with a plain `def` that returns a coroutine
- **THEN** the handler has been called, `StreamBuildException` is raised, and no un-awaited coroutine is left behind

#### Scenario: The refusal does not depend on a running event loop

- **WHEN** `close()` is called on a stream with an async handler registered, both from inside a running event loop and from outside one
- **THEN** the same `StreamBuildException` is raised in both cases, and no event loop is created or reached for

## ADDED Requirements

### Requirement: aclose() is the asynchronous twin of close()

`Stream.aclose()` SHALL be an asynchronous method that runs every registered close handler with no arguments, in the order they were registered. Where a handler's result is awaitable, `aclose()` SHALL await it; where it is not, `aclose()` SHALL treat the handler as complete on return. A stream carrying only sync handlers SHALL therefore behave under `aclose()` exactly as it does under `close()`.

`aclose()` SHALL run handlers one at a time, awaiting each before invoking the next. It SHALL NOT run them concurrently: concurrency would forfeit both the registration-order guarantee and the definition of "the first exception in encounter order".

`aclose()` SHALL carry the failure contract of `close()` unchanged — every remaining handler runs after one fails, the first failure in encounter order propagates, and each later failure is attached to it as a note. A handler that fails by raising and a handler that fails while being awaited SHALL be treated identically.

`aclose()` SHALL close handlers only. It SHALL NOT close, exhaust, cancel or otherwise touch the stream's source, and SHALL NOT consume the stream. `close()` and `aclose()` SHALL differ in exactly one observable respect: whether an awaitable handler result can be completed.

Calling `aclose()` on a consumed reference SHALL be permitted, as `on_close()` and `close()` already are.

#### Scenario: aclose() with no handlers registered

- **WHEN** `aclose()` is awaited on a stream with no close handlers registered
- **THEN** nothing is invoked and no error is raised

#### Scenario: aclose() awaits an async handler

- **WHEN** `aclose()` is awaited on a stream with a handler defined with `async def`
- **THEN** the handler has run to completion, and no un-awaited coroutine remains

#### Scenario: aclose() runs sync handlers too

- **WHEN** `aclose()` is awaited on a stream whose registered handlers are all plain sync callables
- **THEN** every handler has been invoked exactly once, in registration order, exactly as `close()` would have invoked them

#### Scenario: Mixed handlers run in registration order

- **WHEN** `aclose()` is awaited on a stream with handlers `[sync_a, async_b, sync_c]` registered in that order
- **THEN** all three have run, and each completed before the next was invoked

#### Scenario: Handlers are not run concurrently

- **WHEN** `aclose()` is awaited on a stream with two async handlers, the first of which suspends before completing
- **THEN** the second handler is not invoked until the first has completed

#### Scenario: A failing handler does not prevent later handlers from running

- **WHEN** `aclose()` is awaited on a stream with handlers `[bad, good]` registered in that order, where `bad` raises
- **THEN** `good` is still invoked, and `aclose()` raises `bad`'s exception after both have run

#### Scenario: An async handler that raises while awaited is an ordinary failure

- **WHEN** `aclose()` is awaited on a stream with handlers `[async_bad, async_good]`, where `async_bad` raises after suspending
- **THEN** `async_good` still runs, and `async_bad`'s exception is the one raised

#### Scenario: Later failures survive as notes

- **WHEN** `aclose()` is awaited on a stream with three failing handlers registered in order, mixing sync and async
- **THEN** the first failure is raised, carrying one note per later failure, in encounter order

#### Scenario: aclose() leaves the source alone

- **WHEN** `aclose()` is awaited on a stream whose source is an async generator that has not been consumed
- **THEN** the source has not been closed or advanced, and the stream can still be consumed afterwards

### Requirement: A stream consumed as another stream's source does not fire its close handlers

Close handlers SHALL run only when the caller closes the stream — through `close()`, `aclose()`, or a context manager built on either. Consuming a stream SHALL NOT fire them, and this SHALL hold when the consumer is another `Stream` that was constructed over it.

`Stream(inner_stream)` SHALL leave `inner_stream`'s close handlers unfired, whether the outer stream is consumed to exhaustion, abandoned part-way, or short-circuited by a terminal. The source teardown a stream performs at the end of consumption is about the iteration, not about the close-handler contract, and the two SHALL NOT be conflated because the names of the operations happen to coincide.

This requirement pins behaviour that already holds. It is stated because `aclose()` gives `Stream` an attribute that source teardown probes for, so the behaviour would otherwise be one implementation detail away from changing silently.

#### Scenario: An inner stream's handlers survive the outer stream's exhaustion

- **WHEN** a stream with a registered close handler is used as the source of another stream, and that outer stream is consumed to exhaustion
- **THEN** the inner stream's close handler has not been invoked

#### Scenario: An inner stream's handlers survive a short-circuited outer stream

- **WHEN** a stream with a registered close handler is used as the source of another stream that is consumed under a short-circuiting terminal
- **THEN** the inner stream's close handler has not been invoked

#### Scenario: Closing the inner stream still runs them

- **WHEN** the inner stream from the scenarios above is subsequently closed by the caller
- **THEN** its close handler is invoked exactly once

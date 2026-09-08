## ADDED Requirements

### Requirement: A stream is constructed with no close handlers

`Stream(source)` SHALL initialize the new stream with an empty list of close
handlers. There SHALL be no constructor argument for supplying handlers at
construction time: `on_close()` is the only way to register one, and it works on
a consumed reference, so nothing a caller could express through a constructor
argument is lost.

This holds whichever executor the resulting stream carries, and for every static
factory that constructs a stream (`of()`, `empty()`, `iterate()`,
`StreamBuilder.build()`).

A stream assembled from other streams — `Stream.concat(a, b)` — is the one case
that starts with a non-empty list, and it takes those handlers from its operands
rather than from its caller; see the `stream-concat` capability.

#### Scenario: Constructing a stream registers no handlers

- **WHEN** `Stream(source)` is constructed
- **THEN** `close()` on the resulting stream invokes nothing, and `on_close()` can still be used afterward to register handlers

#### Scenario: A handler argument is rejected

- **WHEN** `Stream(source, [handler])` is called
- **THEN** a `TypeError` is raised by Python's argument binding, rather than the handler being silently accepted or ignored

## REMOVED Requirements

### Requirement: A stream constructed with initial close handlers uses them

**Reason**: This requirement documented a *signature*, not a use case. The
`close_handlers` parameter existed so that stage derivation could rebuild the
next stage carrying handlers forward — `type(self)(self._source,
self._close_handlers)` — an internal calling convention that happened to sit in
a public constructor. When `derive-without-reinit` replaced that call with
`copy()`, the parameter lost its only real caller; what remained was
`Stream.concat()`, which had borrowed it to carry two operands' handlers into a
stream that is not a copy of either. Serving that one internal need through a
public parameter left `_close_handlers` as the only piece of stream state with a
constructor argument, beside two siblings — executor and ordering — that
`concat()` sets by other means entirely. `concat()` now expresses all three as
one named operation, leaving the parameter with no callers at all. No
caller-facing situation for it was ever described here, and Java has no
counterpart constructor.

**Migration**: Use `on_close()`, which is already the documented way to register
a handler and is unchanged: `Stream(source, [handler])` becomes
`Stream(source).on_close(handler)`. `on_close()` mutates and returns the
receiver, so it chains and does not consume the stream. The break is loud —
`TypeError` at the call site — and affects only a caller who passed the second
argument; a `Stream` subclass may still define any `__init__` signature it likes,
which `derive-without-reinit` established and this does not narrow.

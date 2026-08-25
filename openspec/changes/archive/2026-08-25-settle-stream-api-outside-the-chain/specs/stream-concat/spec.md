## ADDED Requirements

### Requirement: The concatenated stream carries both operands' close handlers

The stream returned by `Stream.concat(a, b)` SHALL be constructed with the
close handlers registered on `a`, in their registration order, followed by
those registered on `b`, in their registration order. Calling `close()` on the
concatenated stream SHALL therefore invoke every handler registered on either
input, matching Java's `Stream.concat`, whose result closes both inputs.

Handlers SHALL be taken as they stand when `concat()` is called. Registering a
handler on `a` or `b` after `concat()` has returned SHALL NOT retroactively add
it to the concatenated stream, consistent with the concatenated stream being an
ordinary `Stream` constructed with an explicit `close_handlers` list per the
`stream-close-handling` capability.

The existing rules of that capability apply unchanged to the concatenated
stream: every handler runs, in order; a raising handler does not prevent later
handlers from running; and the first exception raised is the one propagated.

#### Scenario: Handlers from both inputs run

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where `a` has close
  handler `handler_a` registered and `b` has `handler_b`
- **THEN** both `handler_a` and `handler_b` are invoked exactly once

#### Scenario: Handler order follows a then b

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where `a` has handlers
  `[a1, a2]` and `b` has handlers `[b1, b2]`
- **THEN** the handlers are invoked in the order `a1, a2, b1, b2`

#### Scenario: One input has no handlers

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where only `b` has a
  close handler registered
- **THEN** `b`'s handler is invoked and no error is raised

#### Scenario: Neither input has handlers

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where neither input
  has a close handler registered
- **THEN** nothing is invoked and no error is raised

#### Scenario: Registering after concat does not affect the result

- **WHEN** `Stream.concat(a, b)` is called and a close handler is then
  registered on `a`, after which the concatenated stream's `close()` is called
- **THEN** the handler registered after `concat()` is not invoked

#### Scenario: A raising handler on one input does not skip the other's

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where `a`'s handler
  raises and `b`'s does not
- **THEN** `b`'s handler is still invoked, and `a`'s exception is raised after
  both have run

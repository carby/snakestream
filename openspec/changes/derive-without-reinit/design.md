## Context

See proposal.md — Why. The mechanical facts this design rests on were measured
rather than reasoned about:

- `MyStream(src).map(f).filter(g).parallel().sorted()` runs the subclass
  `__init__` five times; the final stage's attribute is not the object the first
  constructor assigned.
- `copy.copy` of a `Stream` subclass instance does **not** re-enter `__init__`,
  and yields an object sharing `_source`, `_chain`, `_close_handlers` and every
  subclass attribute by reference, with `_consumed` carried as `False`.
- A subclass whose `__init__` takes anything other than `(source, close_handlers)`
  raises `TypeError` on its first intermediate operation.

Two existing constraints bound the solution. `pipeline-immutability` requires the
derived instance to carry the receiver's concrete type, which
`test_a_user_subclass_survives_a_mode_switch` pins. And `_derive()` is the single
seam: every intermediate op, `sequential()`, `parallel()` and `unordered()` go
through it, so there is exactly one line to change.

## Goals / Non-Goals

**Goals:**

- Constructor runs once per pipeline, not once per stage.
- Subclass identity across derivation preserved, as today.
- The subclass constructor contract widened to "anything", and said so out loud.

**Non-Goals:**

- `Stream.concat()`. It constructs a base `Stream` deliberately and drops
  subclass identity for reasons of its own; `concat-carries-characteristics`
  states that as a decision.
- Any change to `stream-close-handling`. The handler list is already shared by
  reference; this change makes the resource it guards shared too, which is what
  makes the existing rule coherent rather than what changes it.
- `__copy__` on `Stream` itself. This design decides *not* to define one; that
  is a decision, not an omission, and the spec records it.

## Decisions

### Derive by shallow copy, not by construction

`copy.copy(self)` replaces `type(self)(self._source, self._close_handlers)`.

*Alternative — `cls.__new__(cls)` plus a `__dict__` update.* Identical effect and
avoids the `__copy__` hook. Rejected because the hook is a feature, not a hazard:
a subclass with genuinely per-stage state has one place to express it, and
`copy.copy` is the protocol a Python reader already knows. It also breaks on
`__slots__` unless handled by hand, where `copy.copy` handles it via
`__reduce_ex__`.

*Alternative — follow Java literally: derived stages become an internal type
holding no resource, pointing back at a source stage that does.* This is what
`ReferencePipeline.StatelessOp` is, and it is why Java never had this bug. It is
rejected because Java gets it for free from a decision this library already made
differently: Java's `Stream` is an interface nobody subclasses, so its derived
stages *can* be an internal type. Here, `type(self)` exists precisely to preserve
subclass identity, and the existing test pins it. Adopting Java's shape would
mean `isinstance(par, MyStream)` becoming `False` — a larger break than the one
being fixed.

Having committed to identity preservation, shallow-copying is the only way to
have identity without construction. That is the whole argument.

### The four assignments stay explicit

`copy.copy` gives a correct starting object; `_derive()` still sets `_chain` and
`_executor` on it afterwards, and still sets `self._consumed = True` on the way
out. Order matters and is unchanged: copy first (while `_consumed` is still
`False`), then invalidate the receiver.

The no-op path's chain-by-identity optimisation is unaffected — `copy.copy`
shares `_chain` by reference, which is exactly what the mode-switch path already
relies on, and the extending path replaces it with a fresh list as before.

### One incidental saving

`__init__` currently runs `_accept(source) or _normalize(source)` on every
derivation, over a source that is already an `AsyncGenerator`. It hits
`_accept`'s `isinstance` check and passes through, so nothing was wrong — but it
is a wasted call per stage that disappears. Not a motivation, and not worth
benchmarking; noted so nobody looks for the missing normalization later.

### `Stream` does not define `__copy__`

Defining one would mean hand-maintaining the attribute list that the default
already handles, and would make the class the wrong place to look when a
subclass's copy semantics matter. The default is correct here because every
attribute a `Stream` holds is one a derived stage should share.

The consequence is that a subclass's `__copy__` becomes load-bearing where it was
previously inert. That is stated in the spec rather than left to be discovered:
a subclass that defines `__copy__` for unrelated reasons will now find it running
on every `.map()`.

## Risks / Trade-offs

- **A subclass relying on per-stage construction breaks.** → This is the change,
  not a side effect. There is no such subclass in the repository, and the
  behaviour it would rely on is the defect being fixed. Called out as BREAKING in
  the proposal.
- **`copy.copy` honours `__reduce_ex__` on exotic subclasses.** → A subclass that
  customises pickling now customises derivation. Acceptable, and strictly better
  than today, where such a subclass was already broken by the constructor call.
- **The existing subclass test asserts equality on a string literal and would
  keep passing.** → It is tightened to `is` in the same change; without that the
  spec's identity requirement has no guard, and the change could regress
  silently. This is the same failure mode `mark-order-blind-collectors` recorded:
  a correctness-only assertion that passes under either mechanism.

## Migration Plan

No deprecation path. The behaviour change is observable only to `Stream`
subclasses, of which the repository has none outside tests, and the direction is
strictly toward what the documented use case already intended. CLAUDE.md's
AutoClose section gains the constructor-runs-once guarantee.

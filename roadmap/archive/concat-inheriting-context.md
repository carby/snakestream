+++
id = "concat-inheriting-context"
title = "`close_handlers` stops being a constructor parameter with one caller"
filed = 2026-09-08
closed = 2026-09-08
outcome = "shipped"
shipped_as = "inherit-context-on-concat"
+++

**`close_handlers` stops being a constructor parameter with one caller**
(closed 2026-09-08; filed 2026-09-08). Shipped as `inherit-context-on-concat`.

`Stream.__init__(self, source, close_handlers=None)` had exactly one
production caller, `Stream.concat()` — `of()`, `empty()`, `iterate()` and
`StreamBuilder.build()` all passed a source alone, and `_derive()` never
touched it, since `copy()` carries `_close_handlers` forward by reference.
Surfaced immediately after `make-stream-of-atomic`, the entry directly
below, made `Stream(source)` the *documented* construction entry point: the
parameter was invisible while the constructor was, and stopped being
invisible the moment README named the constructor as the surface a caller
reads.

**The parameter was the symptom; the defect was that `concat()` set three
sibling attributes by three different mechanisms** with no principle
choosing between them — handlers through the constructor, executor by
direct assignment, ordering through a `.unordered()` derive. `concat()` now
expresses all three through one named private operation, `_concatenate(a,
b)`, and the constructor drops to `Stream(source)`.

**`_concatenate` is binary, not variadic**, correcting the item's own
`*operands` sketch: `concat()` is the only caller and is itself binary,
matching Java's `Stream.concat(a, b)`, and a variadic signature would have
been generality nobody asked for in a change whose whole point was removing
a parameter nobody used.

**Two things about the merge were easy to get wrong and are now under
test.** The merged handler list must be a *new* list —
`a._close_handlers + b._close_handlers` — rather than an alias of either
operand's; assigning an operand's list directly satisfies every scenario
that predated this change while quietly linking a later `on_close()` on the
concatenation to that operand too, so a reverse-aliasing test and matching
`stream-concat` scenario were added specifically because no prior test
exercised that direction. And the executor assignment has to precede the
`.unordered()` ordering derive, not follow it: `_derive()` copies `_executor`
by value, so assigning it to `self` after the derive has already produced a
new stream sets it on the now-consumed receiver and loses it silently —
`_close_handlers` would survive the same mistake, being shared by reference,
which is what makes the bug worse rather than better, since the half of the
state that carries would mask the half that does not. A test asserting mode
and ordering together on one concatenation guards this.

**A `_Stage`-style value object (source, chain, executor, handlers merged
into one construct-via-`replace()` type) was considered and rejected on
cruft, not performance.** The performance objection was checked and does
not hold: pipeline state is read only inside `stream.py`, and the chain
reaches `execution.py` by value once per terminal rather than once per
element, so a `_Stage`'s extra allocation would land once per `_derive()`
call — per stage, not per element — and every regression this repo has
measured and acted on was per-element (+125% on `count()` from composing
then draining; ~3% on the segment-sign twins), not in this class. What sinks
it instead is that it buys nothing over `copy()`, which already carries
shared context forward — including subclass attributes it knows nothing
about — without ever having to answer which attributes count as pipeline
state: `_consumed` is per-reference, `_size_hint` belongs to the raw source,
and subclass attributes belong to nobody in particular. It becomes the right
call the moment a second parentless construction site exists; today there
is exactly one, and `concat()` is the only binary operation in the API
(`__add__` delegates to it).

The break is loud: `Stream(source, [handler])` now raises `TypeError`, and
the one-for-one replacement, `Stream(source).on_close(handler)`, was already
the documented way to register a handler. A `Stream` subclass may still
define any `__init__` signature it likes, which `derive-without-reinit`
established and this does not narrow.

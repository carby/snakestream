+++
id = "reduce-without-identity"
title = "Added the one-argument `Stream.reduce(accumulator)`"
filed = 2026-08-13
closed = 2026-08-13
outcome = "shipped"
+++

Added `Stream.reduce(accumulator)` — the 1-arg, no-identity overload,
returning `T | None` (`None` for an empty stream) rather than a wrapped
`Optional[T]` type, matching the existing `find_any()`/`max()`/`min()`
convention already used elsewhere in `stream.py`. Implemented as a single
`reduce()` method carrying two `@overload` signatures (identity form and
no-identity form) with one runtime body: a private `_UNSET` sentinel
distinguishes "no identity given," in which case the first pulled element
seeds the fold and an empty stream short-circuits to `None` before the
accumulator is ever called; a single-element stream likewise returns that
element without calling the accumulator. Delegates to the same
`_maybe_await`-based accumulator dispatch the 2-arg form already used, so
sync and async accumulators both work with no duplicated dispatch logic.
Added a new `BinaryOperator` alias to `type.py` for the no-identity
accumulator's `T, T -> T` shape, following the project's convention that
composite/callable type shapes used in public signatures live in
`type.py` rather than being written inline. Added 6 new tests in
`tests/test_reduce.py` (empty stream, single-element stream, multi-element
fold order, async-accumulator awaiting, a hypothesis property test against
`functools.reduce`, and a regression check that the existing 2-arg form is
unchanged). No changes to the existing `reduce(identity, accumulator)`
behavior. See `openspec/changes/add-reduce-no-identity`.

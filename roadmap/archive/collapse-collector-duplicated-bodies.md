+++
id = "collapse-collector-duplicated-bodies"
title = "Collapsed the duplicated bodies in `collector.py` and the sinks' dispatch-state boilerplate"
filed = 2026-08-20
closed = 2026-08-20
outcome = "shipped"
+++

**Collapsed the duplicated bodies in `collector.py` and the repeated
dispatch-state boilerplate in the sinks**, the four-part item that came out
of the 2026-08-19 simplification read. All four parts landed, all
behaviour-neutral, no public API change and no README edit. 457 tests pass
unchanged at 98% coverage; `tests/` was not touched at all.

**(a) The six summing/averaging bodies became two private factories.**
`_summing(mapper, seed, coerce)` and `_averaging(mapper)`; the six public
names survive as one-line wrappers, each keeping its own return annotation,
which is where the Java-primitive distinction is actually expressed. The
`collector.py` comment defending them was reworded: it defends six *names*,
and had been read as defending six *bodies*. `coerce` is `None` rather than
an identity callable on the int/long path, so no call is added per element
and a mapper returning `Decimal`/`Fraction` still sums in its own type.

**The design's hoisting decision was reversed mid-implementation, and this
is the interesting part.** design.md required the `coerce is None` test to be
hoisted out of the `async for`, which means writing the loop twice. Measured
(interleaved, 41 reps, 200k elements) that was right on its own terms: the
hoisted form matches the pre-change code and the single-loop form costs a
reproducible ~2% on `summing_int`/`summing_long`. But `ruff` then fails with
`C901 _summing is too complex (11 > 10)` — the duplicated loop trips the
project's own mccabe gate, which the design had not accounted for.
Suppressing that gate on a function whose complexity comes *entirely from
duplication*, inside a change whose purpose is removing duplication, was the
wrong trade. Shipped as one loop with a per-element `coerce is None` test:
a branch, not a call, and ~2% against the +32-75% that got
`add-callsite-dispatch` rejected.

**(b) Eight sinks lost their hand-copied dispatch triple** to an
`AsyncDispatch` mixin in `callable_dispatch.py` — the module already named
for the concept, and already holding the canonical-shape comment the mixin
now makes checkable. `_FilterSink`/`_MapSink`/`_PeekSink` and
`_ForEachSink`/`_ReduceSink`/`_MinMaxSink`/`_MutableReductionSink`/
`_MatchSink` mix it in and call `_init_dispatch(fn)` from `__init__`. It is
a plain method, not an `__init__`, so it stays out of the MRO: those eight
sit on two different bases with different constructor signatures. The stored
callable unified on `self._fn`, replacing five different names
(`_predicate`, `_mapper`, `_consumer`, `_accumulator`, `_comparator`);
constructor parameters keep their descriptive names and annotations.
`_SortedSink` keeps its own `_comparator` — it never had the triple.
`_MatchSink` keeps its own `_cancelled`, which is short-circuit state, not
dispatch state. **Verified mechanically** that all eight `accept()` bodies
are identical to their pre-change form modulo that one rename, by AST-
extracting each and diffing against `git show HEAD:` with the rename applied
— so nothing was added to the per-element path, which is the whole reason
this part was allowed where `CallSite` was not.

**(c) `grouping_by`/`partitioning_by` now share `_group_into()`.** The
design said `partitioning_by` would pass a `key_fn` wrapping its predicate
in `bool(...)`. **That is unimplementable and the suite catches it:**
dispatch classifies `key_fn` and awaits its *result*, so a sync `bool()`
wrapper sees an unawaited coroutine for an async predicate — always truthy —
and sorts every element into the `True` bucket
(`tests/test_partitioning_by.py:37`). Shipped instead with a separate
optional `coerce_key` applied to the awaited key. Not hoisted, unlike (a):
this loop body already does a `setdefault` and an `append`, and hoisting
would duplicate the only code the part extracts. The `downstream`
comprehension deliberately stays at both call sites — it is the line the
`Collector` redesign rewrites.

**(d) `StatefulOp` now subclasses `StatelessOp`**, overriding `link()` alone.
Gated on a grep first: the only `isinstance` touching these names
(`tests/test_op_protocol.py:84`) tests concrete subclasses, not the two
bases, so the part was safe to do. Both docstrings kept, plus a note that
the subclassing is mechanical convenience and that the docstrings, not the
hierarchy, carry the shared-state distinction.

**Came in well under estimate: -69 code lines** (excluding comments and
docstrings), or -79 coverage-measured statements, against the ~150
estimated. The estimate counted the raw span of the deleted bodies including
their blank and comment lines, and this change adds explanatory comments the
old copies did not carry. See
`openspec/changes/collapse-collector-sink-duplication`.

+++
id = "is-ordered-leaves-public-api"
title = "`is_ordered()` left the public API"
filed = 2026-08-26
closed = 2026-08-26
outcome = "shipped"
+++

**`is_ordered()` left the public API** (2026-08-26). Renamed to
`_is_ordered()`. Java has no such accessor to be at parity with: `BaseStream`
exposes exactly one piece of pipeline introspection, `isParallel()`, while the
ordering characteristic lives in the package-private `StreamOpFlag.ORDERED`
and is never readable by a caller. The question that surfaced it was "where is
`Stream.ordered()`?" — and the answer is that Java has no `ordered()` either,
because ordering is a spliterator characteristic contributed by the source,
only ever cleared by `unordered()` or re-imposed by `sorted()`. Both are now
struck-through rows in README's parity table. See
`openspec/changes/archive/2026-08-26-make-is-ordered-internal`.

**Renamed, not deleted, and not inlined** — the second half was the live
question, since the fold turned out to have exactly one caller
(`for_each_ordered()`; `find_first()` stopped consulting it in
`make-ordering-a-chain-characteristic`, and `CLAUDE.md` had been stale about
that ever since, now fixed). Inlining five lines into a single caller is the
ordinary call and was still rejected: three mode-switch scenarios have no
behavioural observable and pin their rule through the accessor, so inlining
collapses into dropping them — and it is the rule whose earlier violation
produced a wrong answer. The docstring also records *why* the fold is not
cached onto the instance, which is reasoning nobody finds inside a method
about consuming elements.

**The rewrite of the tests is what this change actually cost.** Replacing
accessor assertions with behavioural ones silently weakened them, and a
mutation check caught it: with `_SortedOp` altered to preserve rather than set
the characteristic, all four rewritten `sorted()`-restores tests still passed.
They were reverted to `_is_ordered()` assertions, and the reason — that (a) in
**Now** makes a sort under `RACING` indistinguishable from an unordered one —
is recorded in the spec, in `tests/test_unordered.py`, and as test debt on (a)
itself, along with a pre-existing weak test the same sweep found in
`tests/test_for_each_ordered.py`. **The lesson generalises: "assert on
behaviour, not on internals" is right until the behaviour is broken, and a
test rewrite is not verified by the suite going green afterwards.**

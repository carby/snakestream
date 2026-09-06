+++
id = "collectors-per-box-dispatch"
title = "`collectors.py`'s per-box dispatch state"
bucket = "next"
rank = 2
filed = 2026-09-02
claimed = 2026-09-02
updated = 2026-09-03
gate = "per-element path; write the benchmark before the refactor"

[refs]
changes = ["add-callsite-dispatch", "collapse-terminal-collector-duplication", "extract-racing-task-lifecycle"]
specs = ["callable-dispatch", "collector-protocol"]
files = ["src/snakestream/collectors.py"]
+++

The second of the two duplications from the 2026-09-02 read (see
[`comparator-segment-sign`](comparator-segment-sign.md) for the first, which is
ranked above it).

Nine `_*Box` dataclasses carry 14 `(<name>_is_async, <name>_checked)` pairs — 28
field declarations — plus a `_supply()` that re-seeds them from
`is_async_callable`. It is `AsyncDispatch`'s three pieces of state, written out
longhand once per collector, because a `Collector` is reusable across
concurrent collections and so cannot hold classification on itself the way a
sink does.

*The gate, and it is the hard one.* Every consolidation that suggests itself —
a shared base box, a `Dispatch` slot object, routing the four hand-inlined
accumulators through the existing `_classify_step` — adds either an attribute
hop (`container.key.is_async` for `container.key_is_async`) or a tuple
allocation on the per-element path. That is precisely the charge that killed
`add-callsite-dispatch`, `collapse-terminal-collector-duplication` and the
`merge()` generator in `extract-racing-task-lifecycle`. **This is the largest
literal duplication in the repository and the one most likely to be rejected
again.** Anyone starting it should write the benchmark before the refactor, and
should expect the answer to be "extract the *declaration* (the box's fields and
their seeding) while leaving the per-element dance inlined" rather than a clean
collapse.

*Sharpened 2026-09-03* by the read recorded in [`decisions.md`](../decisions.md).
That predicted answer now has a reason behind it rather than only a benchmark:
the declaration is precisely the part carrying the structural guarantee, because
per-composition classification is a property of *where the state is allocated* —
here, a box the supplier builds once per collection — and not of the lines that
read it. So a shared base box is admissible only while it stays allocated per
collection. One that did not would trade the cheapest safety property in the
package for line count, and would do it silently: the behavioural tests would
still pass, since every one of them collects once.

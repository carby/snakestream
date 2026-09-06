+++
id = "unset-dual-role"
title = "`UNSET` is two sentinels wearing one name"
bucket = "later"
rank = 4
filed = 2026-09-06
blocked_on = "whether an accumulation seed and an omitted argument are the same concept here, or coincide in one place and are conflated in the rest"

[refs]
specs = ["reduce-without-identity", "collector-reducing"]
files = ["src/snakestream/sink.py", "src/snakestream/stream.py", "src/snakestream/collectors.py"]
+++

Surfaced 2026-09-06 while exploring
[`sink-sentinel-placement`](sink-sentinel-placement.md), and split out from it
because it is a question about the sentinel's *identity*, not its address.

`UNSET` serves two roles. **A fold with no seed** — "no value yet", paired with
`unseeded()`, in `UnseededSink._create_container()`, `ReduceSink.accept()`,
`MinMaxSink.accept()`, `_ExtremumBox.found`, `_ReduceBox.acc`. And **an omitted
argument** — arity dispatch between overloads, Python's ordinary
`_MISSING = object()` idiom, in `Stream.reduce()`, `collectors.reducing()` and
`grouping_by()`. Nineteen `is UNSET` comparisons against seven default-argument
slots.

*The roles meet on purpose in exactly one place.* `Stream.reduce()`'s `identity`
defaults to `UNSET` for arity and then flows unchanged into
`ReduceSink._create_container()`, where it means seed — "no identity supplied"
**is** "unseeded fold", and one object makes that free. But the sibling
parameter on the same line is translated at the boundary instead
(`reduce_combiner = None if combiner is UNSET else combiner`), and
`grouping_by(map_factory=UNSET, downstream=UNSET)` is pure arity with no
accumulation anywhere near it.

So the coincidence is load-bearing once and coincidental three times. Splitting
into a `MISSING` arity sentinel and an `UNSET` seed sentinel would cost one
translating line in `reduce()` and buy an honest name in `grouping_by()`; not
splitting keeps a single sentinel whose meaning a reader has to infer from its
neighbourhood.

*Blocked on the decision, not on effort* — the work is small either way. It also
gates its sibling: where `UNSET` belongs depends on whether it is one concept or
two, which is why `sink-sentinel-placement` sits behind this one.

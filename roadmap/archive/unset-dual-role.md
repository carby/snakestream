+++
id = "unset-dual-role"
title = "`UNSET` splits into an arity sentinel and a seed sentinel"
filed = 2026-09-06
closed = 2026-09-08
outcome = "shipped"
shipped_as = "split-arity-and-seed-sentinels"
+++

**`UNSET` splits into an arity sentinel and a seed sentinel, fixing four
keyword-dispatch defects it was hiding** (closed 2026-09-08; filed
2026-09-06). Shipped as `split-arity-and-seed-sentinels`.

`UNSET` served two roles under one name: "no value yet", the seed of an
unseeded fold paired with `unseeded()` and `UnseededSink`; and "argument
omitted", the ordinary `_MISSING = object()` idiom used for arity dispatch
across eight default-argument slots in `Stream.reduce()`,
`collectors.reducing()` and `collectors.grouping_by()`. A private
`_MISSING = object()` now lives separately in `stream.py` and in
`collectors.py`; `UNSET` stays in `sink.py`, meaning the seed role alone.

**The positional call paths cost the split nothing.** Both arity branches
already wrote the seed sentinel explicitly before this change
(`identity, accumulator = UNSET, identity`, and the equivalent in
`reducing()`), so renaming the slot defaults to `_MISSING` left every
positional call's behaviour untouched.

**The keyword form was the one place the two roles genuinely met, and
where the bugs were.** Each dispatcher tested only its *leading* unfilled
slot — a valid proxy for arity under positional calls, wrong under keyword
ones. `reduce(accumulator=f)` worked today only because the two sentinels
were one object; `reducing(binary_operator=op)`,
`reducing(identity=0, binary_operator=op)`, `reducing(0, binary_operator=op)`
and `grouping_by(f, downstream=to_set())` all raised `TypeError` from
calling the shared sentinel as if it were a function. Dispatch now tests
*which* slots are unsupplied, shifting on the trailing slot so a
keyword-spelled call of any documented overload behaves identically to its
positional spelling; the two sentinels meet in exactly one line per
function (`if identity is _MISSING: identity = UNSET`), converting what was
a silent coincidence into a stated rule. An argument set matching no
documented overload — a `combiner`/`mapper` without an `identity`,
`map_factory` without `downstream`, or no accumulator at all — now raises
`StreamBuildException` at construction instead of failing later with a
confusing `TypeError` or a misdirected "downstream must be a Collector".

**`_MISSING` is defined twice on purpose, not deduplicated.** Every
`is _MISSING` test compares against a default the *same* module wrote for
the *same* function, so its identity never needs to cross a module
boundary — unlike `UNSET`, which `stream.py` writes into `ReduceSink` for
`terminals.py` to read and which must stay a single object with a single
home. Two distinct `_MISSING` objects are therefore the accurate model, not
an oversight; a shared name would have needed a home no existing module is
a natural fit for, repeating the exact trap `sink.py`'s stale comment had
already fallen into once.

+++
id = "sink-sentinel-placement"
title = "`UNSET` and `unseeded()` sit in `sink.py` on rejected reasoning"
bucket = "now"
rank = 1
filed = 2026-09-03
updated = 2026-09-08
gate = "a decision on whether `UnseededSink` earns the fold vocabulary its home despite `collectors.py`'s non-sink boxes — the import graph will not settle it, since the split leaves `UNSET`'s three importers unchanged"

[refs]
changes = ["extract-encounter-order-model", "name-by-visibility-not-underscore", "split-arity-and-seed-sentinels"]
specs = ["sink-protocol"]
files = ["src/snakestream/sink.py"]
+++

Surfaced by the `extract-encounter-order-model` move as a diagnosis. **Narrowed
twice since, and both narrowings removed a third of it.**

*2026-09-03, by `name-by-visibility-not-underscore`:* the naming half is moot.
All three names were underscored and cross-module, and that change's rule made
them bare (`_UNSET` -> `UNSET`, `_unseeded()` -> `unseeded()`), the same as it
did to `_split_point()`.

*2026-09-06, by exploring it:* `Box` left. Counting the callers shows the three
were never one question — `UNSET` has three importing modules, `unseeded()` and
`Box` have one each — and `Box`'s home follows from that count rather than from
judgement, so it is now
`move-box-into-collectors`, which shipped on 2026-09-08 (see
[`decisions.md`](../decisions.md)). What remains is the placement of two names,
not three.

**The quoted justification is stale and cannot be argued against as written.**
`UNSET`'s comment says it lives in `sink.py` "because both [`terminals.py` and
`collector.py`] need it and neither may import the other". `collector.py` has
zero references to `UNSET`, `unseeded()` or `Box`; its only `sink` import is
`TerminalSink`. The real second caller is `collectors.py`, which the comment
never names. The placement may still be wrong, but the sentence defending it has
to be rebuilt from the actual import graph first.

**The test to apply**, from the origin rather than the paraphrase — the tell is
not that import topology was consulted, but that a justification only rules
places *out* and never rules one *in*:

> That reasoning correctly rules out `stream.py` and then stops one step early
> — it never asks whether the fold and the enum should be *anywhere* in the
> push protocol's module.

**Options, once the blocker clears.** A new leaf module for the concern (the
`ordering.py` shape, but two symbols against its four — thin, and "thin helpers
earn nothing" has been applied here before); the same plus `UnseededSink`, which
gives it three but costs `sink.py` one of the shapes its docstring advertises;
or leaving both in place and fixing `sink.py`'s docstring instead, on the
grounds that `UnseededSink` gives the push protocol a genuine claim on the
vocabulary and a docstring is cheaper to correct than a module is to move. That
last option is the one the original diagnosis never considered, and it is only
available while `UNSET` remains a single sentinel — which is what
[`unset-dual-role`](unset-dual-role.md) decides.

No spec in `openspec/specs/` names either symbol, so whatever lands is a
zero-delta refactor needing `skip_specs: true`.

**Unblocked 2026-09-08 by its gate.** [`unset-dual-role`](unset-dual-role.md)
was decided as a **split**, so this item now places a `MISSING` arity sentinel
and an `UNSET`/`unseeded()` fold pair rather than one sentinel of two minds.
That removes the third option above — leaving both in place and fixing
`sink.py`'s docstring was available only while `UNSET` stayed a single
sentinel, and it no longer is. Sequence this after the split; placing names
whose count is about to change would be work done twice.

## Corrected 2026-09-08 by rebuilding the graph the gate asked for

Three findings, and each narrows the item further.

**The stale comment is off by one letter, not one argument.** `collector.py` is
a typo for `collectors.py`, which *is* the second caller — so the pair the
comment names is otherwise right, and the item overstated the damage. What is
genuinely false is the clause after it: `terminals.py` and `collectors.py` have
disjoint import closures (`terminals` reaches `callable_dispatch, comparator,
exception, ordering, sink, type`; `collectors` reaches those plus `collector,
execution, spliterator`), so **both** edges are acyclic and either module could
import the other today. The true statement is weaker — neither is downstream of
the other, so neither is a plausible host. Rebuild the comment on that, not on
"may not".

**The import graph does not move under the split, so it cannot decide this.**
`Stream.reduce()` still writes the seed sentinel for `ReduceSink` to read
(`identity, accumulator = UNSET, identity`, then `ReduceSink(identity, ...)`),
so `UNSET`'s importers stay exactly `stream.py`, `collectors.py`,
`terminals.py` before and after. What changes is that all three now mean one
thing. A gate phrased as "rebuilt from the actual import graph" was asking a
question the graph has no answer to.

**Option three is strengthened by the split, not removed.** The "Unblocked"
note above has this backwards. A dual-purpose sentinel had *no* honest home —
half its uses were arity dispatch with no relationship to sinks at all, which
is precisely what made `sink.py` look like a dumping ground. Strip those away
and the residue is a coherent trio, `UNSET` / `unseeded()` / `UnseededSink`,
whose third member *is* the concept:

```
UnseededSink._create_container() -> UNSET
UnseededSink._finish(c)          -> unseeded(c)
```

That rules `sink.py` **in** rather than merely failing to rule it out, which is
the positive argument this item says has never been made. The split creates it.

**The counterweight, which is the whole remaining question.**
`collectors.py`'s `_ExtremumBox.found` and `_ReduceBox.acc` are dataclass
boxes, deliberately *not* sinks — the stated reason `unseeded()` is a free
function rather than a base-class method (design Decision 3 of
`collapse-unseeded-accumulation-rule`). So the concept has two
implementations and `sink.py`'s docstring advertises only one. Whether that
reads as "the module docstring is one sentence short" or "the concept outgrew
the module" is now the entire item.

**And half of it has vanished.** `unset-dual-role` shipped 2026-09-08 as
`split-arity-and-seed-sentinels` (see `decisions.md`): `_MISSING`'s identity
never crosses a module boundary, so it is a private `_MISSING = object()` in
each of `stream.py` and `collectors.py`, defined twice on purpose, and needed
no placement decision at all. This item now places one trio —
`UNSET` / `unseeded()` / `UnseededSink` — not two names of two kinds.

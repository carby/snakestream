+++
id = "sink-sentinel-placement"
title = "`UNSET` and `unseeded()` sit in `sink.py` on rejected reasoning"
bucket = "later"
rank = 5
filed = 2026-09-03
updated = 2026-09-06
blocked_on = "whether `UNSET` stays one sentinel or becomes two — a two-symbol concern module and a one-sentinel-plus-one-rule module are different judgements"

[refs]
changes = ["extract-encounter-order-model", "name-by-visibility-not-underscore"]
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
[`move-box-into-collectors`](move-box-into-collectors.md). What remains is the
placement of two names, not three.

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

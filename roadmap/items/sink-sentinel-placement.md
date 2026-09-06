+++
id = "sink-sentinel-placement"
title = "`UNSET`, `unseeded()` and `Box` sit in `sink.py` on rejected reasoning"
bucket = "now"
rank = 2
filed = 2026-09-03
updated = 2026-09-03

[refs]
changes = ["extract-encounter-order-model", "name-by-visibility-not-underscore"]
specs = ["sink-protocol", "internal-name-visibility"]
files = ["src/snakestream/sink.py"]
+++

Surfaced by the `extract-encounter-order-model` move. Recorded as a diagnosis,
not as available work — it is not scaffolded.

The three names sit in `sink.py` on the same import-topology reasoning that
move **rejected** for the encounter-order model. `UNSET`'s own comment says why
it landed there: "Lives here rather than in `terminals.py` or `collector.py`
because both need it and neither may import the other" — placement decided by
which module both callers could already reach, not by what `sink.py`'s
docstring says the module is for (the push protocol). It is the identical shape
`Ordering` and `is_ordered()` were moved out of.

**Narrowed 2026-09-03 by `name-by-visibility-not-underscore`:** the naming half
of this is now moot — all three were underscored and cross-module, and that
change's rule made them bare (`_UNSET` -> `UNSET`, `_unseeded()` ->
`unseeded()`), the same as it did to `_split_point()`. What is left is only the
module-placement question the title names: whether these three earn a fourth
module, fold into an existing one, or stay put on the grounds that a sentinel
and a rule-with-a-name are a smaller, more defensible exception than four
symbols were. Still a call for whoever picks this up — not settled here.

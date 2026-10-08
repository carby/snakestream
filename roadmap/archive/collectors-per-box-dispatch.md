+++
id = "collectors-per-box-dispatch"
title = "`collectors.py`'s per-box dispatch state: declined on mechanism, not on the benchmark"
filed = 2026-09-02
closed = 2026-09-07
outcome = "declined"
+++

**`collectors.py`'s per-box dispatch state: declined on mechanism, not on the
benchmark** (closed 2026-09-07; filed 2026-09-02, claimed the same day, the
second of the two duplications from that read — the first,
`comparator-segment-sign`, is scaffolded and shipping). Nine `_*Box`
dataclasses carry 14 `(is_async, checked)` pairs, 28 field declarations, and
the item called it "the largest literal duplication in the repository and the
one most likely to be rejected again". It is, and it is — but not for the
reason it expected. The item's gate was "write the benchmark before the
refactor". **Two of the three extractions never reach a benchmark: they do
not type-check or do not name.**

*It is not one duplication written nine times.* It is two dialects, and the
boundary between them is a lint gate:

| | callables | dance | classification | field names |
|---|---|---|---|---|
| `_SumBox`, `_AvgBox`, `_SummaryBox`, `_ExtremumBox` | 1 each | inlined, 6 lines | seeded at supply, eagerly | `is_async` / `checked` |
| `_ReduceBox` (2), `_ToMapBox` (3), `_GroupBox` (2), `_MappingBox` (2), `_CollectAndThenBox` (1) | 1-3 | `classify_step()` | lazy, on element 1 | `<name>_is_async` / `<name>_checked` |

`classify_step`'s own docstring says why: it exists for sites classifying
several callables per element, "where inlining each would push the enclosing
function's branch count past the mccabe complexity gate"
(`max-complexity = 10`). One callable fits inline; two or three do not. So the
duplication has a structural explanation, and any collapse has to survive it.

**The three extractions, and what each dies on.**

*A decorator injecting the fields* — dead on the type gate, no benchmark
needed. `ty` cannot see dynamically-set attributes, and CI runs it on the
GIL-enabled leg:

```
error[unresolved-attribute]: Object of type `BoxViaDecorator` has no
attribute `key_is_async`
```

*A shared base box* — survives, and is still wrong. Plain inheritance fails
outright, since every box has a required field:
`TypeError: non-default argument 'total' follows default argument 'checked'`.
`kw_only=True` fixes that, at the cost of converting all ten positional
constructions to keyword. But a base supplies **one** pair under **fixed**
names, and the boxes need one, two or three independently named pairs — so
`_ReduceBox` would read `container.is_async` for its mapper and
`container.op_is_async` for its operator, or every box degrades to
`a_`/`b_`/`c_`. That trades `container.key_is_async` for
`container.a_is_async` and calls the loss of a meaningful name a saving.

*A `Dispatch` slot object* (`container.key.is_async`) — the attribute hop on
the per-element path, which is the charge that already killed
`add-callsite-dispatch`, `collapse-terminal-collector-duplication` and
`extract-racing-task-lifecycle`'s `merge()` generator. Not re-measured; the
prior three are the measurement.

**A fourth option the item never listed, priced here so nobody re-derives
it.** Collapse each pair into one tri-state int — 28 fields to 14, no base
class, no decorator, no attribute hop, names stay semantic
(`mapper_dispatch`). Measured through the public `collect()`, 20,000
elements, interleaved round-robin, best of 3, median of 25 rounds:

| variant | sync mapper | async mapper |
|---|---:|---:|
| named module-level constants | +5.2% | +2.4% |
| literal ints in the branch | +2.7% | +2.1% |

It clears the `+10%` gate and is still the wrong trade: positive in all four
measurements, buying only line count, and turning two self-documenting
booleans into an int needing either magic numbers or a global lookup that
costs more than the attribute load it saves.

**So 28 declarations is the floor for this design**, given that
per-composition classification is a property of *where the state is
allocated* — a box the supplier builds once per collection — and not of the
lines that read it. The item had already sharpened to that point on
2026-09-03; what is added here is that the extraction it predicted
("extract the declaration, leave the dance inlined") is not available either,
because the declaration is what varies in arity and in name.

**Note — two things that are available, and are not collapses.** Neither was
taken here; both are small, off the per-element path, and would be a new item
if anyone wants them. First, the dialect boundary is undocumented where it is
read: nothing in `collectors.py` says why four boxes inline and five delegate,
and a reader has to find it in `callable_dispatch.py`'s docstring. This item
existed largely because the duplication looks unexplained, so explaining it in
place is the closest thing to a real fix. Second, `_CollectAndThenBox` is a
genuine inconsistency — one callable, but the multi-callable dialect, lazy
where its arity-peers seed. Either it joins the seeded-inline family or the
boundary above is a description rather than a rule.

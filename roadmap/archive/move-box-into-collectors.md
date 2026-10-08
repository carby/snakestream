+++
id = "move-box-into-collectors"
title = "`Box` belongs with the collector containers"
filed = 2026-09-03
closed = 2026-09-08
outcome = "shipped"
shipped_as = "move-box-into-collectors"
+++

**`Box` belongs with the collector containers** (closed 2026-09-08; filed
2026-09-03). Shipped as `move-box-into-collectors`.

`Box` was defined in `sink.py` and used by exactly one module: `collectors.py`,
in `counting()` alone, across four lines. It moved to `collectors.py` as
`_Box`, placed immediately above `counting()` — the layout every one of the
nine sibling containers already follows, each sitting directly above the
factory that supplies it. Nothing in `sink.py` used it; `terminals.py` and
`ops.py` mentioned it only in prose explaining why they deliberately do *not*.

**Ruled in by the family, not out by the import graph.** That distinction is
the whole point of the item, and it comes from `extract-encounter-order-model`'s
own diagnosis of the defect it left behind: a justification that "correctly
rules out `stream.py` and then stops one step early — it never asks whether
[it] should be *anywhere* in the push protocol's module". Several homes were
permitted by the import graph; only `collectors.py` puts `Box` next to the
nine things it is a sibling of. `collector.py` was rejected explicitly — it
holds the *protocol*, and a container one factory accumulates into would have
repeated the same mistake one module over.

The rename to `_Box` is a **consequence, not a second decision**: the naming
rule underscores a module-level name exactly when no other module uses it, and
`tests/test_name_visibility.py` already enforced it. The reverse reading
("rename it private, therefore move it") would be circular.

**Split three ways rather than landing as one diff.** The parent item,
[`sink-sentinel-placement`](items/sink-sentinel-placement.md), bundled `Box`
with `UNSET` and `unseeded()` as one question. Counting the callers shows they
never were — `UNSET` has three importing modules, `unseeded()` and `Box` have
one each — and `Box` is the only one of the three whose home is decided by
counting rather than by judgement. The other two remain open and deliberately
untouched, including `sink.py`'s `UNSET` comment, which is wrong about which
module is its second caller but says nothing about `Box`, so this change left
it alone rather than half-rewriting a sentence the remaining item has to
rebuild from the actual import graph.

Three stale in-source comments followed the move — `terminals.py`'s
`CountSink`, `ops.py`'s `_GuardedCounter` (whose claim that collector boxes
are never shared across threads reads *more* true now that `_Box` lives among
them), and one in `tests/test_fork_join.py` the item had not counted. Review
also caught a coupling the move introduced rather than removed: `test_sink.py`
had begun importing `_Box` from `collectors.py` purely as a generic
shared-state container for `StatefulOp` fixtures unrelated to collectors. It
now defines its own three-line `_ValueBox` instead.

**Declined in review: renaming it `_CountBox`** to match the eight
purpose-named siblings. It is the one container in the file with a generic
name, but the generic name is accurate — `test_sink.py` used it as a bare
mutable cell with no counting involved — and design Decision 2 is explicit
that the underscore is derived from a rule rather than chosen. `_CountBox`
would be a genuine second judgement call in a change whose entire value was
carrying none.

No behaviour change: the same class, the same call sites, the same four lines
in `counting()`. 1114 tests, 99% coverage, `ruff` and `ty` clean. `Box` was
never exported from `__init__.py`, so no README Migration entry was owed.

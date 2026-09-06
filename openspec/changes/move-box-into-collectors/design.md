## Context

See proposal.md - Why. One constraint shapes the whole change: this is the
third of a three-way split of the roadmap item `sink-sentinel-placement`, and
its value depends on staying that third. `extract-encounter-order-model`
declined to bundle these names for a stated reason — "bundling them would make
one diff carry two independent judgement calls" — and it undercounted at two.
The other two calls are live and unresolved; this one is not a call at all.

The test that decides it comes from that same change's proposal, which named
the failure mode precisely:

> That reasoning correctly rules out `stream.py` and then stops one step early
> — it never asks whether the fold and the enum should be *anywhere* in the
> push protocol's module.

A placement justified only by what it rules *out* is the defect. A placement
that rules a home *in* is the fix.

## Goals / Non-Goals

**Goals:**

- Put `Box` where a reader looking for it would look.
- Leave the two hard questions strictly untouched, so this diff carries no
  judgement at all.

**Non-Goals:**

- Deciding where `UNSET` and `unseeded()` belong.
- Deciding whether `UNSET` should remain one sentinel or become two.
- Any change to `Box`'s definition, fields, or semantics.
- Any change to `counting()`'s behaviour or its `UNORDERED` declaration.

## Decisions

### 1. `collectors.py`, ruled in by the family rather than out by the graph

`collectors.py` holds nine dataclass containers of exactly this shape, each
private, each supplied by one factory. `Box` is the generic member of that set —
`counting()` uses it for the same reason `_SumBox` exists for `summing_*`: a
free-function accumulator has to mutate a container it was handed rather than
rebind a local.

That is a positive reason, not an elimination. The import graph permits several
homes (`sink.py`, `collector.py`, a new module, `collectors.py`); only one of
them puts `Box` next to the nine things it is a sibling of.

**Alternative considered: `collector.py`, with the protocol.** Rejected. That
module holds `Collector`, `CollectorSink`, `StreamingCollector` and
`to_generator` — the protocol, per the established `collectors -> collector`
import direction. A container that one factory happens to accumulate into is
not part of the protocol, and putting it there would repeat this item's own
mistake one module over: reachable by both, described by neither.

**Alternative considered: leave it and fix `sink.py`'s docstring instead.**
This is a real option for `UNSET`/`unseeded()`, where `UnseededSink` gives the
sink protocol a genuine claim on the vocabulary. It is not an option for `Box`,
which `sink.py` does not use at all. A docstring admitting `sink.py` also holds
a container for another module's use would be true and would document a defect.

### 2. The rename is derived, not chosen

`_Box` follows from the naming rule once `collectors.py` is the only module
using it. It is worth stating that this is a *consequence* rather than a second
decision, because the reverse reading — "rename it private, therefore move it" —
would be circular. The move is justified by the family; the underscore then
falls out of a rule that is already build-checked.

There is no collision: `collectors.py` has no existing `_Box`.

### 3. Stale prose is corrected here, not swept later

Two comments name `Box`'s current address to explain a deliberate non-use, and
both go stale the moment it moves:

- `terminals.py`'s `CountSink`: "A plain int, not a `Box`..."
- `ops.py`'s limit/skip state: "Kept out of `Box` (`sink.py`), which collectors
  also build per composition and never share across threads."

Both are load-bearing explanations rather than decoration — they record why a
shared mutable container was rejected in one place and a lock added in another —
so they are worth keeping accurate rather than deleting. The `ops.py` one is
also now *more* true after the move, since `Box` living among the collector
containers is exactly what that comment asserts about it.

`sink.py`'s `UNSET` comment is corrected only where it is wrong about `Box`.
Its larger problem — it names `collector.py` as a caller that uses none of the
three — belongs to the remaining item, because rewriting it properly requires
deciding what that sentence should say instead.

## Risks / Trade-offs

- **A three-way split could read as churn**, three changes where the roadmap
  had one item. -> The alternative is one diff mixing a decided move with two
  open questions, which is what `extract-encounter-order-model` declined to do
  and for the reason it gave. Each of the three lands or is rejected on its own
  evidence.
- **`collectors.py` is already 950 lines** and this adds to the longest module
  in the package. -> It adds roughly eight, and it adds them to a family that
  is already there; the alternative keeps a tenth sibling in a module that
  never touches it. If `collectors.py`'s length is a problem it is a problem
  about the ~20 factories, not about this class.
- **`tests/test_name_visibility.py` may fail if the rename is missed** on any
  call site. -> That is the check working. A red result there means the change
  is incomplete, not that the test needs adjusting.

## Migration Plan

Independent of the other two items and of the two fork/join changes; can land in
any order relative to all of them. No caller-visible surface changes — `Box` is
not exported from `__init__.py` before or after — so no README Migration entry
is owed.

Rollback is moving one class back and reverting three comments.

## Open Questions

None. The two questions this change deliberately does not answer are tracked as
their own roadmap items rather than deferred inside this one.

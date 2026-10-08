+++
id = "per-element-dispatch-fourth-look"
title = "The per-element dispatch dance, re-examined and declined a fourth time"
filed = 2026-09-03
closed = 2026-09-03
outcome = "declined"
+++

**The per-element dispatch dance, re-examined and declined a fourth time**
(2026-09-03) — no change directory, which is why it is recorded here. The
six-line classification dance appears at 9 sink/generator sites and
longhand across 9 collector boxes, and is the largest literal duplication
in the repository. It was re-opened from a fresh angle: not another attempt
to unify the *code* — `add-callsite-dispatch` closed that — but an attempt
to unify the *check*, an AST-level build test asserting the sites share one
skeleton, on the `tests/test_name_visibility.py` precedent of enforcing
mechanically what cannot be enforced structurally. It costs nothing at
runtime, so the benchmark objection does not reach it.

**Declined, on a reason that is not the benchmark.** The check would assert
a skeleton that carries no invariant. What the canonical comment in
`callable_dispatch.py` actually warns about is *state placement* — hoisting
the `is_async`/`checked` pair out of the per-composition body, which leaks
classification across compositions and racing branches and violates
`callable-dispatch`'s "Classification does not leak across compositions".
That is the one silent failure worth a mechanical guard, and all three
families already make it unexpressible:

| Family | State lives on | Allocated once per |
|---|---|---|
| 8 sink sites | the sink instance, via `AsyncDispatch._init_dispatch` | sink chain (`op.link()`) |
| 9 collector boxes | the supplier-made container | collection (`supplier()`) |
| `Stream.iterate()` | locals in the generator body | composition |

So `AsyncDispatch` is not a code-sharing device — it shares three attribute
declarations and a three-line seeder. It is what puts the state on the
instance, and that is the whole of the guarantee. The only way to
reintroduce the leak is to allocate the state somewhere else deliberately,
which is a redesign and not a slip.

The dance's remaining obligation — awaiting correctly — is already pinned
per site: `tests/test_callable_dispatch.py` section 5.6 exists to take the
`elif not checked` arc "at every call site, not just
map/filter/summing_int", and `ops.py`, `terminals.py` and `collector.py`
sit at 100% branch coverage, so every arc of every copy is exercised.

**What this adds to the record**, since `add-callsite-dispatch`'s
benchmark-findings.md is otherwise the whole of it: the duplication is not
only cheap but *safe*, on an argument independent of measurement. Anyone
re-opening this should know both halves — the runtime half is closed by
that benchmark ("the cost of any abstraction here is not the abstraction
versus a cheaper abstraction but the abstraction versus free"), and the
build-time half is closed by the table above.

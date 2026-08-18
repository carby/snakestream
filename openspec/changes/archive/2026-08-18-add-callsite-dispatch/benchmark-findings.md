# Benchmark findings — task 3.2 gate

Harness: this repo's dev environment, Python 3.14.5, 20,000 elements, chain of
8 `.map()` ops, best of 5 runs, three independent invocations per variant.
Same shape `optimize-callable-dispatch` and `redesign-pipeline-sink-chain` used,
and the unmodified baseline reproduces the latter's recorded 1,872.6 ns/element.

Only `_MapSink` was converted for this measurement, so with 8 `.map()` ops in
the chain the figures isolate the per-site, per-element dispatch cost exactly.

| Variant | ns/element (3 runs) | vs baseline |
|---|---|---|
| **Baseline** — inline five-branch shape, as shipped | 1907, 1992, 2162 | — |
| **Floor** — dispatch logic deleted entirely (sync-only, incorrect; measured only to size the headroom) | 1826, 1878, 1998 | ~0% |
| **Option A** — `CallSite` with `async def __call__`, call site is `await site(x)` | 3399, 3444, 3468 | **+75%** |
| **Option B** — `CallSite.call()` sync, returns value-or-awaitable, caller branches on `site.is_async` | 2529, 2589, 2840 | **+32%** |

## What the floor measurement establishes

The decisive number is the floor. Deleting the dispatch logic outright buys
nothing measurable over the baseline — the inline five-branch shape costs
approximately zero. It is two attribute loads and two branches that the CPU
predicts correctly every time after the first element, with no Python-level
call and no allocation.

That means the cost of any abstraction here is not "the abstraction versus a
cheaper abstraction" but "the abstraction versus free". Both options pay a
Python-level function call per element per site that the inline code does not:

- Option A additionally allocates and drives a coroutine frame per element per
  site — roughly 180 ns/site/element on this machine.
- Option B avoids the coroutine frame but still pays the bound-method call —
  roughly 70 ns/site/element.

There is no third variant that removes the call itself while keeping the state
encapsulated, because encapsulating the state is what requires going through
the object.

## Consequence for the change as proposed

`optimize-callable-dispatch` bought 2.6x (5,949 → 2,247 ns/element) by hoisting
exactly these branches out of the per-element path. Option A gives back roughly
half of that gain; Option B roughly a fifth. Design's stated fallback ("a
two-shape `CallSite` whose `__init__` picks a sync fast path") does not help:
the fast path still has to be reached through a call, which is the cost.

Per task 3.3 this is material, so implementation stopped here rather than
converting the remaining 23 sites. The working tree was reverted to HEAD; the
two variants are preserved in the session scratchpad.

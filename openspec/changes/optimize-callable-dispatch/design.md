## Context

This change came out of sizing the roadmap's **Next**-bucket item "Redesign
pipeline execution from nested async-generator delegation to a push-based
(Sink-chain) model." That item's stated justification was `RecursionError` on
long chains plus implied per-element overhead. Benchmarking to size it showed
the overhead was not where the item assumed, and that most of it is removable
without touching the execution model at all.

All measurements: Python 3.14.5, N=20,000 elements, k chained `.map()` ops,
best of 3 runs, figures are **total nanoseconds per element**. Benchmark
harnesses were throwaway scripts; the variants and their semantics assertions
are reproduced below in enough detail to re-derive.

## Finding 1: the execution-model redesign is not a performance win

Comparing today's nested async-generator chain against both candidate
push-based designs:

| k | today | flat driver | true Sink chain | baseline (no pipeline) |
|---|---|---|---|---|
| 1 | 848 | 1192 | 911 | 298 |
| 2 | 1618 | 1957 | 1507 | 317 |
| 4 | 2977 | 3369 | 2617 | 364 |
| 8 | 5681 | 5972 | 4806 | 456 |
| 16 | 11767 | 11375 | 9087 | 652 |
| 32 | 23324 | 23167 | 19370 | 914 |

- The **flat driving loop** (one driver generator threading each item through a
  flat `for op in ops:` loop) is level with today, and slower at short chains.
  Its only gain is constant stack depth.
- The **true Sink chain** (Java-faithful: `accept()` pushes to `downstream.accept()`)
  gains 15–17%. Note it is still O(k) stack-deep per element — Java's design does
  not give constant depth, it just has cheap frames — so it does not fix
  `RecursionError` either.

For reference, the recursion ceiling was measured directly: a `.map()` chain
consumes successfully at k=800 and raises `RecursionError` at k=1000, against
`sys.getrecursionlimit() == 1000` — roughly one frame per chained op.

## Finding 2: the cost is `isawaitable`, not the wrapper

Isolating the dispatch layer, holding the execution model fixed:

| k | `_maybe_await` (today) | inlined `isawaitable` | classified per callable | direct call (no async support) |
|---|---|---|---|---|
| 1 | 848 | 737 | 402 | 416 |
| 4 | 2949 | 2447 | 1173 | 1219 |
| 8 | 5727 | 4850 | 2045 | 2094 |
| 32 | 23187 | 18792 | 7664 | 7911 |

Inlining the `async def _maybe_await` wrapper recovers only ~20%. Classifying
the *callable* once instead of the *result* per element reaches the
no-async-support floor — 2.8x at k=8. The wrapper coroutine allocation is a
minor cost; `inspect.isawaitable` is the dominant one, because it runs
`isinstance` against `types.CoroutineType`, `types.GeneratorType`, and
`collections.abc.Awaitable` — the last an ABC check — on every result.

The win is not confined to sync callables. With an `async def` mapper,
classified dispatch still beats today 2,791 ns vs. 4,242 ns at k=8 (~1.5x).

## Decision: implementation shape

Three shapes reach floor speed. They differ in restructuring cost and, more
importantly, in correctness:

| shape | k=8 | single loop body | handles async `__call__` | handles sync `__call__` returning a coroutine |
|---|---|---|---|---|
| `_maybe_await` (today) | 5775 | yes | yes | **yes** |
| two specialized loops | 2018 | no | yes | **no** |
| hoisted `is_async` flag | 2099 | yes | yes | **no** |
| **hoisted flag + first-element check** | **2064** | **yes** | **yes** | **yes** |
| direct call | 2030 | yes | no | no |

**Chosen: hoisted flag + first-element check.**

The two faster-looking variants are both wrong. A callable object with a plain
`def __call__` that returns a coroutine is classified sync by any build-time
test, and both variants then yield an un-awaited coroutine downstream — which
is precisely the defect `add-maybe-await-helper` was written to fix, reappearing
in a new shape. Reintroducing it to save 46 ns per element would be a bad
trade.

The chosen shape pays one bool test per element (`elif not checked`) and one
`isawaitable` call per composition, and lands within 2% of the unsafe variant
and within 2% of the no-async-support floor. It also keeps a single loop body
per call site, so the 30 sites change shape only slightly rather than each
splitting into two specialized bodies.

## Decision: narrowing the dispatch contract

Committing to a classification after the first invocation means the contract
changes from **per-result** to **per-callable-per-composition**. A callable that
returns an awaitable for some elements and a plain value for others — e.g.
`def f(x): return coro() if x else 5` — is handled correctly today and will not
be after this change.

Accepted deliberately:

- It has no Java analogue. Java's functional interfaces are homogeneous by
  construction; a `Function<T,R>` cannot return `R` sometimes and
  `CompletableFuture<R>` other times.
- It is not a documented or tested behavior of this library; it falls out of
  `_maybe_await`'s implementation rather than being an intended capability.
- The alternative — per-result checking — is exactly the 2.8x cost.

It is specified explicitly rather than left implicit, so the narrowing is a
stated contract and not an undocumented regression. Tracked as **BREAKING** in
README's migration log per `CLAUDE.md`'s convention.

## Decision: classification state lives per composition, not per op

The `is_async`/`checked` pair must be initialized inside the generator body
that runs once per composition, not in the enclosing function that runs once
per `.map()`/`.filter()` call. Placing it in the outer scope would let a
classification decided during one composition persist into a later composition
of the same chain — the same defect class as the `distinct()`/`limit()` state
leak fixed in `fix-stream-rerun-state`, which is why `_DistinctOp`/`_LimitOp`
exist as callable classes with `make_state()`.

Classification is cheap and idempotent, so this needs no `make_state()`
participation — a plain local inside the generator body is sufficient. Under
`ParallelStream`, each racing branch composes its own generator and therefore
classifies independently; since classification is a pure function of the
callable, branches always agree, so no sharing via `state_map` is needed.

## Decision: `_maybe_await` is retained, not deleted

Specialization only pays where dispatch happens per element. Call sites invoked
once per composition — `collect()`'s `supplier`, for instance — gain nothing
measurable and read better through the helper. `_maybe_await` stays for those,
and the `callable-dispatch` spec continues to require that both paths honor the
same four sync/async cases.

## Non-goals

- Any change to the pipeline execution model. The Sink-chain item stays in the
  roadmap's **Next** bucket with its justification rewritten to drop the
  performance claim (see roadmap.md).
- Fixing `RecursionError` on ~1000-op chains. Unaddressed here, and not
  addressed by the Sink-chain design either; only a flat driving loop or
  trampoline would, at zero measured speed benefit.
- `flat_map`'s up-front `iscoroutinefunction` rejection, which is a pre-call
  classification with different intent and is explicitly out of scope per the
  existing spec.

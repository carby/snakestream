+++
id = "fork-join-executor-and-spliterator"
title = "The racing executor becomes fork/join over a `Spliterator` (`fork-join-executor-and-spliterator`)"
filed = 2026-09-04
closed = 2026-09-04
outcome = "shipped"
shipped_as = "fork-join-executor-and-spliterator"
+++

**`fork-join-executor-and-spliterator`** (2026-09-04) — the racing executor
is gone. `.parallel()` now decomposes the source into contiguous batches via
a public `Spliterator`, runs each batch's chain in a worker thread on that
thread's own event loop, and concatenates in batch order. `execution.py`
goes **676 -> 494 lines**: `_Window`, `_guarded()`, `_group_through()`,
`_releasable()`, `_release_in_order()`, `_run_ordered_tail()`,
`_racing_branches()`, `_race_through()`, `_IN_FLIGHT_PER_WORKER` and
`_in_flight()` are all deleted, because contiguous batches never destroy
encounter order and so nothing has to restore it. Three properties replace
the whole apparatus, each free: `asyncio.gather()` preserves argument order
(intra-batch), batches are contiguous and consumed in order (inter-batch),
and batch size bounds in-flight work. `split_point()` survives — a stateful
op still cannot run independently per batch — but the barrier it drives is
now an ordered pass over batches that already arrive in order.

Measured against `a872f25` on the same harness, medians of 3-5 in-process
trials (`benchmark-findings.md` in the archived change carries the full
table):

| shape | old | new |
|---|---:|---:|
| async I/O, `.parallel()` | 3.82x | **54.00x** |
| CPU-bound, free-threaded | — | **~2x** |
| CPU-bound, GIL build | 0.93x | 0.95x |
| cheap sync mapper | 0.05x | 0.05x |

**`unordered()` narrowed, and the narrowing is not a Java-parity break.**
Delivery-order relaxation survives but is now batch-granular rather than
per-element, and an order-blind terminal can be delayed by its own batch's
slowest element. Java's `BaseStream.unordered()` is documented as "may
return itself" — a permission to disregard encounter order, never a promise
to scramble it — so preserving order is conformant. What changed is a
performance property, not a semantic one, and the README migration entry
says so in that order.

**The near-miss worth recording, and it corrects the entry below.** The
first implementation rebuilt a sink chain per element in `_run_element()`,
which made `is_async_callable()` run **once per element** instead of once
per composition — 1001 calls against 3, on a 500-element two-callable
pipeline — violating `callable-dispatch`'s "Awaitability is classified once
per composition" with no delta written. Caught in review before archive;
fixed by classifying once on the `Op` at construction and passing the result
through `link()`. Worth ~18ms of an ~88ms cheap-mapper regression at n=8192.

The entry below (2026-09-03) concluded that the only way to reintroduce this
class of failure is "to allocate the state somewhere else deliberately,
which is a redesign and not a slip". The redesign duly happened, and the
reasoning was **incomplete in a specific way**: it reasoned about *where the
state lives* and not about *how long the sink lives*. `AsyncDispatch` did
put the state on the sink instance exactly as designed; what broke the
guarantee was the sink's lifetime shrinking from one-per-composition to
one-per-element. No site-level check — including the AST skeleton check that
entry declined — would have seen it, so the decline still stands. What does
not stand is the confidence that a redesign could not do this quietly.

**The gate's blind spot, which is the transferable lesson.** The change's
test audit (`test-audit.md`, 125 tests classified) asked one question: *does
this test map to a requirement that survives?* It never asked the inverse —
*which specs might the new implementation violate?* — and `callable-dispatch`
was never in the blast radius because nothing in it mentions racing. Any
future change that replaces a mechanism should run both sweeps; the combiner
change carries the inverse sweep as its own task section.

**Deferred, not resolved:** the `racing-encounter-order` capability keeps a
directory name describing a retired mechanism, and `test_racing_*.py` keep
theirs, because the openspec workflow forbids renaming a capability and
emptying it into a new one would leave two half-specs. A known wart with an
honest fix — a rename once the requirements settle — not an oversight.

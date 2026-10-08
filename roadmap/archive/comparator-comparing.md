+++
id = "comparator-comparing"
title = "`comparing(key_extractor)` ported from Java's `Comparator.comparing`"
filed = 2026-08-27
closed = 2026-08-27
outcome = "shipped"
+++

**`comparing(key_extractor)` ported from Java's `Comparator.comparing`**
(2026-08-27). `sorted()`, `min()`, `max()`, `min_by()` and `max_by()`
previously accepted only a 3-way `Comparator`, the most expensive way Python
can express an ordering — every comparison forces a `cmp_to_key` call, and an
async comparator forces the hand-written `merge_sort` because `list.sort`'s C
loop has no point to return control to the event loop. Measured sorting dicts
by one field: **6.8-8.8x** for a sync key extractor over a sync comparator,
**4.8-5.4x** for async, where it also collapses the interleaved-await count
from O(n log n) to O(n). See
`openspec/changes/archive/2026-08-27-add-comparator-comparing`.

**`comparing()` returns an object, not a closure.** A literal port of Java's
`(a, b) -> k(a).compareTo(k(b))` would be a regression: the key would be
called twice per comparison, O(n log n) times, so an async key would cost
`2n log n` awaits. The returned `_KeyComparator` instead exposes the key
extractor as a plain attribute so `sort()` can recognize it and take a
decorate-sort-undecorate fast path, while still implementing `__call__` as an
ordinary `Comparator` for `min()`/`max()`/`min_by()`/`max_by()`, none of which
know about the fast path.

**The fast path sorts on the key alone, never on `(key, element)`.** An
explicit key selector over the paired list, not a bare tuple sort — Timsort's
stability then gives encounter order for equal keys for free with no
tie-break index, and the *elements* are never compared, so one that doesn't
support `<` still sorts as long as its key does. No sign or `bool` validation
reaches this path either: a key extractor returns a key, not a comparison
result, so `check_comparator_result_type`/`_checked`/the trial probe are all
skipped, and an incomparable-key `TypeError` propagates from `list.sort`
unwrapped.

**Async key extraction gathers concurrently, reversing a task written before
benchmarking.** The design deferred "sequential loop or `asyncio.gather`?" as
an open question, and the sequential loop shipped first, per its own task,
with no trial-comparison probe — reasoned as unnecessary since a loop always
has an `await` point available. Benchmarked before the gate run with an
I/O-bound extractor (`sleep(0.001)` per key, the shape a real async extractor
actually has): 1,000 elements cost **1325ms sequential vs. 9ms gathered**. A
sequential loop was paying the full `n * latency` regardless of the extractor
being async — exactly the concurrency `comparing()`'s async case exists to
buy, and the loop was throwing it away. Switched to `asyncio.gather()`, which
*reinstates* a trial call on the first element (the same shape as `sort()`'s
own trial comparison) so the one-time `isawaitable` safety net's coroutine
joins the gather instead of being discarded — invocation count stays exactly
n either way. The reversal is recorded in design.md rather than the
now-stale task line being silently correct in hindsight, on this project's
rule that a superseded decision is annotated, not erased.
**Accepted trade-off:** `gather`'s failure semantics apply — first exception
wins, not left-to-right — and every element's key coroutine is in flight
concurrently rather than one at a time. Both follow from the same reason the
capability exists: an async key extractor's value is entirely in not
serializing its awaits.

**New capability spec `comparator-comparing`**, five requirements: builds a
`Comparator` from a key extractor and is accepted anywhere one is; the
extractor may be sync or async; sorting invokes it exactly once per element,
not once per comparison (the property the capability exists for); ordering by
key is stable; keys must be mutually comparable, with `bool` keys explicitly
a legitimate ordering rather than an error. `comparator-contract`'s
bool-rejection rule is unaffected — a key extractor returns a key, never a
comparison sign, so there is no `bool <: int` hazard on this path to guard.
27 new tests in `tests/test_comparing.py`, including a drift test asserting
the fast path and the `__call__` path agree on the same comparator (ties,
`bool` keys, a property-based comparator-vs-`cmp_to_key` check), an exact
invocation-count test, and the misclassified-sync safety-net path (a `def
__call__` that manually returns a coroutine).

**README gained a third parity table** — `Comparator`, alongside `Stream` and
`Collectors` — recording `comparing()` as implemented and `thenComparing`,
`reversed`, `naturalOrder`, `reverseOrder` as deliberately skipped with their
reasons, in the same struck-through style the `Stream` table already uses so
"not yet" reads differently from "decided against". `thenComparing()`'s
workaround (`comparing(lambda x: (a(x), b(x)))`) is documented in
`comparing()`'s own docstring, since it is exactly what a future
`thenComparing()` would compile to.

**Not breaking.** Every existing comparator path, `merge_sort` included, is
untouched; `comparing()` is a new way to build a `Comparator`, not a change
to what one means. 673 tests green, `ruff`, `ruff format --check`,
`ty check src`, and `--cov-fail-under=98` at 98.30% all pass.

**Landing this is the precondition for two items `add-comparator-comparing`'s
own proposal named out of scope**: replacing `merge_sort` with a smaller
algorithm, and retiring the async comparator path altogether. Both were
deferred specifically because they become easier to judge once `comparing()`
exists and it is visible how much traffic still reaches the comparator path
rather than the key path — that visibility didn't exist until now.

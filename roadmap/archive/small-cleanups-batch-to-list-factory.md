+++
id = "small-cleanups-batch-to-list-factory"
title = "Took the small-cleanups batch: `to_list` as a factory, the race loop's scans, `_maybe_aclosing`"
filed = 2026-08-21
closed = 2026-08-21
outcome = "shipped"
+++

**Took the small-cleanups batch: `to_list` as a factory, the race loop's
per-element scans, `_maybe_aclosing`, and private box types in public
signatures.** Four independent edits, three behaviour-neutral and one a
public-API break, landed as one change with each part revertable on its own.

**(a) `to_list` is now a factory, `to_list()`** — it was the single bare
`Collector` instance in the public surface, so the API read
`collect(to_list)` next to `collect(to_set())` for two equally stateless
collectors. The direction was the real decision: the inconsistency could
equally have been resolved by making `to_set` an instance, and both are
breaking. Chose the factory because Java's `Collectors.toList()` and
`toSet()` are both factories, and because it makes the rule statable without
an exception — *every collector in `collector.py` is a factory* — where the
reverse would have required callers to know which collectors are stateless.
A callable-`Collector` shim keeping both forms working was rejected for the
same reason `concat`'s `__await__` shim was: it makes the type permanently
worse to spare a one-line migration. It breaks loudly — the bare name is a
function, not a `Collector`, so an unmigrated call site hits the existing
`collect()` guard and raises `StreamBuildException`. 151 call sites in the
tests moved; `grouping_by`/`partitioning_by`'s `downstream` default is now
`to_list()` evaluated once at definition time, which the "one instance is
safe to reuse" property (still true, now pinned as a spec scenario rather
than used as a justification for the shape) makes safe. Migration-log entry
added; README gained a `to_list()` row it never had.

**(b) The race loop's per-element list and linear scan are gone** —
`any([n is not None for n in tasks])` allocated a throwaway list per
iteration and `tasks.index(task)` was an O(branches) equality scan per
element. Both collapse into one `{task: branch}` dict that doubles as the
waitlist and as the "any branch still running" test, so the `tasks` list and
its `None` holes disappear entirely rather than being kept alongside a
counter. **Measured, per the standing rule, and the honest answer is no
measurable win** (Python 3.14.5, 20,000 elements, no intermediate chain,
best of 5, three invocations, driving `_parallel()` directly): `processes=4`
6666/6712/6695 -> 6405/6631/6674 ns/element, a -1.0% median; `processes=16`
5057/5054/5137 -> 5020/5016/4996, -0.8%. Both inside noise and clear of the
no-regression gate. The absolute numbers say why: at ~6.7 microseconds per
element the cost is `asyncio.wait()`'s own per-call set construction and
scheduling, three orders of magnitude above a 4- or 16-entry scan. Kept for
the clarity and the removed bookkeeping, not for throughput — recorded here
so it is not re-proposed as a performance item.

**(d) `_maybe_aclosing` is a 5-line `@asynccontextmanager`**, down from a
14-line class. The `try`/`finally` is load-bearing and was the one real trap:
without it the source leaks on every path that does not run to exhaustion.
Three existing tests already covered the early-`break` paths (`flat_map`
short-circuit, `any_match`, `find_first`) — verified by removing the
`finally` and watching them fail — but **nothing covered the exception
path**, so a test was added first and confirmed to fail without the
`finally` before the rewrite landed.

**(e) No private accumulator box is reachable from a public signature** —
`summing_int() -> Collector[Any, _SumBox, int]` and 17 siblings widen their
`A` parameter to `Any`. `T` and `R`, the parameters callers reason about,
are untouched, and the private helpers (`_summing`, `_averaging`,
`_summarizing`, `_extremum`) keep their precise box types, since that is the
internal contract the checker should still see. `to_collection`'s
`Collector[Any, _C, _C]` was deliberately left alone: there `A` genuinely is
the caller's own container type, not an internal box.

Parts (b), (d) and (e) held the "green with no test file edited" tripwire —
the only test-file change outside part (a)'s mechanical rename was the new
close-on-exception test. 518 tests green, coverage 98%. Eight capabilities
took deltas, six of them (`collector-mapping`,
`collector-collecting-and-then`, `pipeline-immutability`, `stream-iterator`,
`terminal-sinks`, `generic-stream-typing`) only because their scenario text
quoted the bare `collect(to_list)` form. See
`openspec/changes/batch-small-cleanups`.

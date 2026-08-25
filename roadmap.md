# Roadmap

Now/Next/Later view of open code-quality and test-rigor items, generated from
the review-pass notes below. Completed items from that review remain in
**Done** for history.

**Guiding principle (stated 2026-08-21):** keep a 1:1 match on the *public API
surface*, and exploit Python's capabilities *underneath* for simplicity and
performance. Java is the API contract, not the implementation blueprint. A
divergence from Java's internals is not a defect; a divergence in observable API
behaviour is — that framing is what found the position-dependent `.parallel()`
bug. Where Java's structure exists only to solve a Java problem, drop it: one
`_copy_into()` where Java needs `copyInto()` plus `copyIntoWithCancel()`,
`_maybe_aclosing()` as an `@asynccontextmanager`, collectors as one `Collector`
value rather than a class hierarchy, `summing_int`/`summing_long` sharing a body.

## Now

**Empty as of 2026-08-25.** The six-story batch that bundled the fourteen
findings of the legibility and stdlib-usage read of all twelve modules in
`src/snakestream/` (2026-08-25, at `946fff0`) is **closed** — stories 1
through 6 are all in **Done**. The dependency chain finished with story 5, and
story 6, which nothing waited on, went last.

The **Implementation notes for the 2026-08-25 batch** that used to sit here —
repros, line anchors, the tripwire and the benchmark gate — have gone with the
batch. Each story's **Done** entry carries what it actually found.

**Now needs a refill**, and so does **Next**. **Later** is not the place to
pull from without a decision: every entry there is parked behind an explicit
call (real multiprocess parallelism and the two items that depend on it, Java 9
sequencing, `Stream.of()`'s arity semantics), not behind sequencing. The
natural next source is a fresh read, or the Java-8 parity gaps README still
tracks as unimplemented.

## Next

**Empty as of 2026-08-25.** The 2026-08-25 batch closed out of **Now** without
refilling this, since it was the whole of both buckets. See **Now** for where
the next items should come from.

## Later

Bigger, structural — needs explicit buy-in before starting since it changes a
core semantic.

| Item | Why later |
|---|---|
| **Implement real (multiprocess) parallelism for `.parallel()` / `ParallelStream` / `PROCESSES`** — today it's just `asyncio` tasks racing over a shared generator (I/O-bound only, GIL-bound, no multiprocessing). Decided to keep the `.parallel()`/`PROCESSES` naming as-is (see README) rather than rename to the more accurate `.concurrent()`/`CONCURRENCY`, specifically so that *if* real parallelism is ever implemented under the same names, it's not a second breaking rename. | No concrete use case for true CPU parallelism has come up yet, and the path there is blocked on a real problem, not just unscoped effort: a `ProcessPoolExecutor`-backed implementation needs to serialize the mapper/predicate/comparator/accumulator/combiner across the process boundary, and stdlib `pickle` can't handle lambdas or local closures (the idiomatic way to call every op in this library), can't pickle generators/async generators at all (so the source itself can never be shipped whole), and even picklable *sync* callables don't solve it since async user callables would need each worker to bootstrap its own event loop rather than just running a function. Revisit only once there's both a concrete need and an answer for lambdas/closures across the process boundary (`cloudpickle`/`dill`, or a restricted sync-only picklable-callable mode) and for running async user callables inside a worker process. **The executor-value redesign is done** (see **Done**), which is the enabler this entry used to point forward to: real parallelism is now *a third executor* implementing `elements()`/`value()`, not a third subclass, and `execution.py` is the natural owner for whatever has to cross the process boundary. It does not solve the pickling blocker. The `ParallelStream` name in this item's title is retired; the mode is now `Racing`. |
| **`BaseStream.spliterator()`** — Java's parallel-decomposition iterator, used by `parallelStream()` to split a source into chunks shared threads can each work over. | Depends on the item above: Java's `Spliterator` assumes shared-memory thread decomposition, which only becomes meaningful once real (multiprocess) partitioned execution is decided — until then there's nothing for it to expose, and it may end up intentionally-skipped rather than implemented. Moved down from **Now**, where it was flagged as decision-blocked rather than ready to build. |
| **Wire up `reduce(identity, accumulator, combiner)` and `collect(supplier, accumulator, combiner)`'s `combiner`** — both accept a `combiner` for Java signature parity but never invoke it, since `stream.py` always folds over one composed stream, sequential or parallel, with no independent partitions to merge. | Same blocker as the item above: a real combine step only makes sense once real partitioned (multiprocess) execution exists, which is now explicitly parked until there's both concrete demand and a solution for the pickling/async-worker problem. See `openspec/changes/add-collect-supplier-accumulator-combiner`. |
| **Java 9 `Stream` additions** — `takeWhile(predicate)`, `dropWhile(predicate)`, `Stream.ofNullable(t)`, and the 3-arg `iterate(seed, hasNext, next)` overload (distinct from the already-implemented 2-arg `iterate(seed, next)`). | README states the project's intent explicitly: "once we reach some sort of feature parity with Java 8 then maybe we move on to implement the improvements in Java 9." The **Now**/**Next** buckets are still closing out Java 8 parity gaps (`unordered()`, the `Collectors` framework, etc.), so pulling Java 9 work forward would jump the stated sequencing rather than reflecting lower value — revisit once Java 8 parity is substantially done. |
| **`Stream.of()`'s arity-dependent semantics** — `Stream.of([1, 2])` spreads the single collection into two elements, while `Stream.of([1, 2], [3, 4])` yields two lists. The number of arguments changes what the arguments mean, there is no way to express a stream of exactly one list, and Java's `of(T...)` treats every argument atomically. | Decision-blocked rather than effort-blocked, which is what this bucket is for. The spreading form is not an oversight: it is the primary documented idiom, used in nearly every README example and throughout the test suite, and `Stream.iterate()` is built on it. Changing it would be a far larger break than the `str`/`bytes` and kwargs changes already in the migration log, touching essentially every call site in the docs and tests. Needs an explicit call on whether Java parity is worth that, or whether the divergence should instead be documented as intentional next to the `str`/`bytes` note. Surfaced 2026-08-20 in the same code-quality read that produced **Now** items 1-4. |

## Done

- **Collector containers, and the duplicate-key exception** (2026-08-25).
  Story 6 of the 2026-08-25 batch — independent of the other five, and the one
  that closed the batch. Three unrelated defects that shared a neighbourhood.

  **(a) Nine hand-written containers became `@dataclass(slots=True)`.**
  `_SumBox`, `_AvgBox`, `_SummaryBox`, `_ExtremumBox`, `_ReduceBox`,
  `_ToMapBox`, `_GroupBox`, `_MappingBox`, `_CollectAndThenBox` each declared a
  `__slots__` tuple and then wrote the same field list again in an `__init__`.
  `slots=True` emits the same descriptors, so this is not the rejected
  `CallSite` proposal wearing a new hat: those containers are built once per
  collection by a collector's `_supply()`, never per element, and attribute
  access inside `_accumulate` is unchanged. **Verified rather than asserted** —
  a before/after harness compared slot names, constructed values and the
  absence of `__dict__` across all nine and found them identical.

  **The "~90 lines of boilerplate" the roadmap row claimed is not the number.**
  The real saving is **-34 lines** (`collector.py` -25, `sink.py` -9). The ~90
  counted the gross volume of `__slots__` tuples plus `__init__` bodies, but
  the dataclass field declarations that replace them occupy most of that space
  — a field is still a line. Only `_ToMapBox` is a large win (-10), because its
  seven-field `__slots__` tuple was formatted across nine lines. The other
  eight are -2 each. Legibility, not line count, is what this part bought:
  the field list is now stated once.

  **One field order had to change.** `_SummaryBox` took `seed` positionally but
  declared `count` first, and a required dataclass field cannot follow
  defaulted ones, so `total` moved to the front. Its single construction site
  is `_SummaryBox(seed)`, so it still binds correctly — but it is a real
  reordering, not a transcription, and it is the one place where the "change
  nothing but the boilerplate" goal bent.

  **(b) `Counter` is deleted, not renamed.** It shadowed `collections.Counter`
  and added exactly one thing to `Box`: a default of `0`. Deleting it was the
  user's call over a rename. The two `ops.py` `make_shared_state()` bodies
  return `Box(0)`, and `counting()` — which had been passing the class object
  itself as the supplier, `Collector(Counter, ...)`, relying on that default —
  became `Collector(lambda: Box(0), ...)`. `partial(Box, 0)` was rejected as a
  `functools` import for one call site.

  **(c) `to_map` raises `IllegalStateException`, and it stays a `ValueError`
  break.** Java's `Collectors.toMap` throws `IllegalStateException` on a
  duplicate key, and this project already defines that class and already raises
  it for pipeline reuse. The tempting softener — deriving `IllegalStateException`
  from `ValueError` so existing `except ValueError` sites keep working — was
  **rejected, and the reason is the other raise site**: the same class is what a
  reused-stream error raises, and a stream-reuse error is not a `ValueError`
  under any reading. Softening the break here would have mis-typed it there.
  Loud for `except ValueError`, invisible to a bare `except`; spec delta on
  `collector-to-map` and a README migration-log entry.

  **The historical migration-log entry was deliberately left wrong.** README's
  `redesign-collector-shape` entry illustrates interleaved downstream side
  effects with "e.g. `to_map`'s duplicate-key `ValueError`". That was true at
  that release. The log is read chronologically, so editing it would falsify
  history; the new entry states the current type and the old one keeps its own.

  **The tripwire held, with one honest exception.** 562 tests green,
  `git diff --stat -- tests/` naming exactly the two files the row predicted.
  But the row listed five `Counter` sites in `test_sink.py` and there were
  **six** — a nested `_CountingStatefulOp` at lines 371-372 that the read
  missed. It is in a named file and the import would not have resolved without
  it, so it was converted rather than escalated. The lesson is about the
  enumeration, not the tripwire: a grep would have found it and the row was
  built from a read.

  **Coverage went 98.05% -> 98.03%, and that is arithmetic, not a regression.**
  The task list said to treat a drop as a lost test, so it was investigated:
  missed statements (2), branches (288) and partial branches (26) are identical
  before and after, and the uncovered set is the same two lines in
  `_summarizing`. Total statements fell 1147 -> 1136 because the change deletes
  eleven *covered* statements, which raises the weight of a fixed uncovered
  remainder. **A pure-deletion change can lower a coverage percentage without
  uncovering anything** — worth remembering the next time this gate moves.

  `ruff`, `ruff format --check`, `ty check src` and
  `openspec validate --strict` all pass, plus a clean-interpreter
  `import snakestream` to rule out a cycle from `collector.py`'s new
  `exception` import. See `openspec/changes/tidy-collector-containers`.

- **`comparator.py` split out of `sort.py`** (2026-08-25). Story 5 of the
  2026-08-25 batch, and the last of the dependency chain. (Story 6, which
  nothing waited on, landed after it and closed the batch.)

  `sort.py` was named for one of the three things it held.
  `check_comparator_result_type` and `is_new_extremum` are comparator
  *semantics*, and their consumers — `_MinMaxSink` in `terminals.py`,
  `min_by`/`max_by` in `collector.py` — sort nothing, yet both imported them
  from a module called `sort`. That misdirection was the whole defect.

  **Two modules, not one, and that was the user's call.** The roadmap row's
  literal reading was to fold everything into one `comparator.py`, defensible
  since `comparator-contract` governs all five functions. Rejected because it
  renames around the defect rather than fixing it: one big `comparator.py`
  would leave `ops.py` importing a *sort dispatcher* from a module named
  `comparator` — the same misdirection pointed the other way. Split, each
  importer gets a module whose name is accurate for what it takes from it, and
  the already one-way dependency (sorting calls semantics; never the reverse)
  becomes a visible import edge instead of an implicit file ordering.

  **The row's open question — where `sort()` lands — was answered `sort.py`,
  on the rule that the seam belongs with the caller, not the definer.**
  `sort()` consumes comparator semantics exactly as `_checked` and `_merge` do.
  Putting it in `comparator.py` would have left that module owning a function
  whose only caller is `ops.py`, and `sort.py` reduced to `_checked` plus
  `merge_sort` with no entry point — a module nothing imports directly. The
  confirmation is `ops.py:15`: `from snakestream.sort import sort` reads
  correctly before and after, unchanged, and `_SortedSink.end()`'s comment
  naming `sort.py` stayed true. The decision that required no edit at the only
  external call site is the one that matched what was already there.

  **Beyond the story as written: `type.py` gained an alias, and `ty` is what
  forced it.** The plan said to annotate `merge_sort`/`_merge` with the
  `Comparator` union, reasoning it was a safe supertype and that adding a
  narrowed alias was a different story. That was wrong on a checkable fact.
  `Comparator` is `Callable[[T, T], int | Awaitable[int]]` and `_merge` awaits
  it unconditionally, so annotating turned the await into
  `invalid-await: int | Awaitable[int] is not awaitable`. The union is not a
  safe supertype where the body does something only the narrow arm supports.
  While the functions were bare, `ty` inferred nothing and said nothing —
  **annotating is what surfaced it**, which is the argument for closing out
  unannotated code rather than leaving it. Nothing else in the codebase hit
  this because every other comparator await goes through
  `_maybe_await`/`AsyncDispatch`, which return `Any`; `_merge` is the only site
  awaiting a `Comparator` directly. Resolved with one line in `type.py` —
  `AsyncComparator = Callable[[T, T], Awaitable[int]]` — and
  `cast("AsyncComparator", comparator)` at `sort()`'s two reroute sites, where
  `is_async_callable` or the trial comparison has just *proved* the narrowing.
  A `cast("Awaitable[int]", ...)` inside `_merge`'s loop was rejected: it
  states the narrowing at the least informative point and puts a cast on the
  per-comparison path. Flagged and user-approved rather than absorbed.

  **The annotation strand was an assumption, and it is worth recording as
  one.** The roadmap row named the module's bare functions, so the work was
  taken into scope without being confirmed. It paid for itself by finding the
  `Comparator` gap, but the precedent is the assumption, not the luck. `src/`
  now has **no unannotated function at all** (verified by `ast`, not grep).

  **A pure move, and the instruments say so.** 562 tests green with **no test
  file modified**, and coverage back at exactly **98.05%** — a move cannot
  shift coverage, so an unchanged number is the evidence nothing else happened.
  The `sort.py` diff is three hunks: one added import, the two removed
  functions, and one docstring phrase (`_checked`'s "the same trick
  is_new_extremum uses *above*", which the split falsified). `ruff`,
  `ruff format --check`, `ty check src` and `openspec validate --strict` all
  pass, plus a clean-interpreter `import snakestream` to rule out a cycle
  between the two new modules. No spec impact — `skip_specs: true`; every
  moved function kept its name, signature and body. See
  `openspec/changes/split-sort-into-comparator-and-sort`.

- **The sync-comparator fast path** (2026-08-25). Story 4 of the 2026-08-25
  batch, and the only one in it that makes the library faster rather than
  easier to read.

  `_SortedSink.end()` routed every comparator-based sort through `merge_sort`,
  and its own comment stated the cost as if unavoidable — *"Trades away
  Timsort's speed for sync comparators"*. Only the async case actually needs a
  hand-written merge with an `await` in its inner loop. `sort.py` gained one
  entry point, `sort(arr, comparator)`, which owns the choice: sync comparators
  now go to `list.sort(key=cmp_to_key(...))`, async ones to `merge_sort`.
  `_SortedSink.end()` calls `sort()` and says so in two lines instead of five.

  **Confirmed figures**, 20,000 random floats, sync 3-way comparator, best of
  9, Python 3.14.5: **69.4 ms -> 38.7 ms end-to-end through `sorted()`
  (1.8x)**, and **58.4 ms -> 27.5 ms measuring the sort alone (2.1x)**. The
  end-to-end number is the smaller one because the pipeline's own per-element
  cost is unchanged and now dominates a larger share. The async path is
  unaffected: 6.7 ms -> 6.8 ms on a 2,000-element async-comparator sort, within
  noise.

  **The 3.6x the proposal's table showed is not available, and the reason is a
  spec.** `comparator-contract`'s "Comparators must not return bool" makes
  `sorted()` responsible for raising `TypeError` on a `bool` result. A `bool`
  compares perfectly well under `cmp_to_key` — it is an `int` — so handing it
  the raw comparator would silently produce a wrong order instead of raising.
  `_checked()` keeps a per-comparison type test, inlined with a call-out only
  on the raising path, the same trick `is_new_extremum` already uses one
  function up. **1.3x is the price of the contract; the contract wins.**

  **The open question the roadmap left for this story — the one-time
  `isawaitable` safety net — was answered with a trial comparison.** A
  comparator with a plain `def __call__` returning a coroutine classifies as
  sync, and `list.sort` is sync all the way down, so a coroutine seen mid-sort
  cannot be awaited from inside the key function. `sort()` therefore makes one
  trial `comparator(arr[0], arr[1])` before the sort when classification says
  sync and the buffer holds two or more elements; an awaitable result is
  awaited (so nothing is left un-awaited) and the whole sort reroutes to
  `merge_sort`. The alternative the notes floated — documenting a narrowing for
  `sorted()` alone — was **rejected**: it would break `callable-dispatch`'s
  "Sync-signatured callable that returns a coroutine" scenario, which names no
  operation and so covers `sorted()`, and the
  `test_sorted_sync_call_returning_coroutine_comparator` test that pins it.
  The cost is one extra comparator invocation per comparator sort of two or
  more elements; nothing constrains the invocation count, and nothing could,
  since Timsort and merge sort make different numbers of comparisons on the
  same input anyway.

  **Beyond the story as written: `merge_sort` lost its `state` list, and
  branch coverage is what found it.** The plan said to leave `merge_sort`
  byte-for-byte alone. That could not hold — once `sort()` settles asyncness
  ahead of the call, *every* comparator reaching `merge_sort` returns
  awaitables, either because `is_async_callable` said so or because the trial
  proved it, so `_merge`'s `elif not state[1]` ladder can never fire. The
  suite stayed green and said nothing; the `branch-coverage-gate` at 98% is
  what caught it, as two unreachable arms dropping the total to 97.79%. The
  ladder and the `state` list are gone, `merge_sort` recurses into itself
  rather than into a `_merge_sort` that existed only to thread state, and
  `_merge` does a plain `await comparator(...)`. Ten lines lighter, and it now
  says what is true — *this function is the async path* — where the surviving
  ladder said the opposite. Same removal this batch made to
  `_ForEachSink._finish`.

  **One test added, no test modified.** Both bool-rejection tests now raise
  from the trial comparison, one comparison earlier, which left `_checked()`'s
  own `TypeError` line uncovered. `test_sorted_rejects_non_int_on_a_later_comparison`
  sorts `[3, 1, 2.5]` with `lambda a, b: a - b` — `int` for the trial pair
  `(3, 1)`, `float` once `2.5` is involved — covering the line and pinning a
  contract requirement the suite never asserted: the `int` contract holds for
  *every* comparison, not just the first.

  562 tests green, 98.05% coverage. `ruff`, `ruff format --check`,
  `ty check src` and `openspec validate --strict` all pass. No spec impact —
  `skip_specs: true`, since `sorted()`'s results, stability, `reverse`
  handling, `bool` rejection and async support are all unchanged. See
  `openspec/changes/sort-with-cmp-to-key`.

- **Chain-building and dead-code smalls** (2026-08-25). Story 3 of the
  2026-08-25 batch, and the last of its three `stream.py` stories. Four
  independent findings, one commit each, none of them observable.

  **(a)** The eight intermediate ops were each the same 90-column line —
  `cast("Stream[X]", self._derive(self._chain + [_SomeOp(...)], self._executor))`
  — so the chain-extension rule was written eight times while the one thing
  each method is *about*, the `Op` it queues, was the least visible part of
  the line. A private `_extend(op)` now holds
  `self._derive(self._chain + [op], self._executor)`, and each op is a
  one-liner: `return self._extend(_MapOp(mapper))`.

  `_extend` takes a **built** `Op` rather than the class plus its arguments.
  The eight `Op` constructors take between zero and two arguments of unrelated
  types (`_DistinctOp()` takes none, `_SortedOp` takes a comparator and a
  flag), so an `_extend(op_cls, *args)` form would degrade to `*args: Any` and
  lose exactly the type information the call site has. It also does not run
  `_check_not_consumed()` — `_derive()` already does, and duplicating the
  guard one frame up would make it ambiguous which one is load-bearing.
  `_derive_executor()` was deliberately left out: `parallel()`/`sequential()`
  pass `self._chain` **unchanged** under a different executor, the opposite of
  what `_extend` does, and folding both into one helper would re-couple what
  the batch's earlier stories separated.

  **Beyond the story as written: the eight `cast()` wrappers went too, and
  that is most of the win.** The `cast` was never necessary — `_derive()`
  returns `Stream[Any]`, and `Any` is assignable to each method's declared
  return type, so the cast narrowed nothing while reading like a real
  narrowing. Verified against the `ty` version CI runs on the 3.14 leg before
  committing to the shape, since `cast` is erased at runtime and no test can
  tell the two forms apart. The `cast` import stays: `sequential()`,
  `parallel()`, `iterate()` and the 3-arg `collect()` still use it.

  **(b)** `_ForEachSink._finish` deleted. `TerminalSink._finish` is
  `return container`, `_ForEachSink._create_container` is `return None`, and
  the sink assigns `self._container` nowhere else — so the override returned
  `None` for the one input on which the base already returns `None`. Recorded
  in the commit message because the override *looks* load-bearing: a reader
  who assumes `for_each` must discard a result will read it as the thing doing
  the discarding. It is not; `result()` being `None` comes from
  `_create_container`. The three other `_finish` overrides in `terminals.py`
  were checked and kept — each translates the `_UNSET` sentinel, which the
  base does not do.

  **(c)** `sorted(..., reverse: bool = False)`. `stream.py` now has no
  unannotated parameter at all (AST-checked, not eyeballed).

  **(d)** `asyncio.ensure_future` -> `asyncio.create_task` at both
  `race_through()` sites. The benchmark exemption was written as
  **conditional** rather than granted — it held only while the diff stayed a
  one-word substitution at each site, and it did: two lines, one word each,
  nothing else moved. Both arguments are `branch.__anext__()` on an async
  generator, always a coroutine, so `ensure_future`'s
  `isfuture`/`iscoroutine`/`isawaitable` ladder always landed on the coroutine
  arm and called its internal `loop.create_task` anyway.

  561 tests green, **no test file edited** — the entire verification story for
  a change with no new behaviour to assert. `ruff`, `ruff format --check`,
  `ty check src` and `openspec validate --strict` all pass, 98.03% coverage.
  No spec impact: the change set `skip_specs: true`, the same treatment as
  `split-ops-into-ops-module` and `collapse-terminal-drive-loop`. See
  `openspec/changes/tidy-stream-chain-building`.

- **Settled what counts as a source, and how a racing branch consumes one**
  (2026-08-25). Story 1 of the 2026-08-25 batch, and the only crash in it.

  **(a)** `.parallel()` raised `AttributeError` on any source the sequential
  path accepts but that is not a full async generator: `_guarded()` called
  `await source.aclose()` unconditionally and pulled with
  `source.__anext__()`, while `_accept()` admits any `AsyncIterable`. Both
  halves fixed — `race_through()` now calls `aiter(source)` **once** for all
  branches, and `_guarded()`'s `finally` closes only if the source is
  closeable.

  **The trap worth recording:** the obvious placement for `aiter()` is the
  first line of `_guarded()`, and it is silently wrong. `_guarded()` runs once
  per branch, so a source whose `__aiter__` hands back a fresh iterator would
  give each branch its own and yield the elements `PROCESSES` times over — a
  wrong answer strictly worse than the crash it replaces. The
  `__aiter__`-returns-a-separate-iterator test asserts the exact multiset for
  this reason, and was confirmed to fail against the per-branch placement
  before being accepted.

  **(b)** `_accept()` collapsed to one `isinstance(source, AsyncIterable)` —
  `AsyncGenerator` is a subclass of it, so the narrower arm could never
  decide. **(c)** `_normalize()`'s `hasattr(source, "__iter__")` became
  `isinstance(source, Iterable)`.

  **Deliberately not done, and now recorded in the code rather than here:**
  the neighbouring `hasattr(source, "__next__")` branch stays a `hasattr`.
  `Iterator`'s `__subclasshook__` requires *both* dunders, so an object with
  only `__next__` is neither `Iterable` nor `Iterator`; converting it would
  reintroduce the bug fixed at `3554cc1` and break
  `stream-construction`'s "Iterator source exposing only `__next__`"
  scenario. The comment on that branch now says so, so the tidier-looking
  conversion cannot be re-proposed as an oversight.

  **(d) was the open decision, and it went to consistency:** `bytearray` and
  `memoryview` are now scalar sources alongside `dict`/`str`/`bytes`.
  `Stream.of(bytearray(b"ab"))` yields the one `bytearray`, not `[97, 98]`.
  `bytes` was already scalar, so the mutable buffer and the view over a buffer
  were spreading while the immutable buffer of the same data was not. This
  **breaks silently** — results change, nothing raises — so it carries a
  README migration-log entry. The `memoryview` half is a genuine judgement
  call rather than pure consistency, since a `memoryview` cast to a non-byte
  format has meaningful per-item iteration; spreading stays available as
  `Stream.of(*mv)`.

  One implementation detail beyond the plan: `_maybe_aclosing()`'s conditional
  close was split into a `_maybe_aclose()` coroutine that both it and
  `_guarded()` call. The context-manager form cannot hold the shared lock
  across its own exit, and `_guarded()` must close under that lock, so
  reusing the helper as-is was not available — the split keeps one definition
  of "close if closeable" rather than duplicating the check.

  546 tests green (536 + 10 new), **no existing test edited** — both test
  files are pure additions. `ruff`, `ruff format --check`, `ty check src` and
  `openspec validate --strict` all pass, 98% coverage. No benchmark gate:
  every site runs once per stream construction or once per racing branch,
  never per element. Spec impact: `stream-construction`'s scalar and
  spreading requirements MODIFIED, and a new
  "Source acceptance does not depend on execution mode" requirement ADDED to
  `stream-execution-model` — the gap the crash fell through. See
  `openspec/changes/define-and-guard-stream-sources`.

- **Settled `stream.py`'s API surface outside the chain: `iterate`, `concat`,
  `close`** (2026-08-25). Story 2 of the 2026-08-25 batch. Three independent
  edits, one commit each, landed in order so a bisect lands on one behaviour.

  **(a)** `Stream.iterate()`'s `nxt` was the one user-supplied callable in the
  library not routed through the `is_async_callable`/`isawaitable` dispatch
  shape every other callable uses — an `async def nxt` silently produced a
  stream of un-awaited coroutine objects:

  ```python
  async def nxt(x):
      return x + 1


  await Stream.iterate(1, nxt).limit(3).to_array()
  # [1, <coroutine object nxt>, <coroutine object nxt>]   -- no error raised
  ```

  `_make_iterator` is now an `async def` generator carrying the same
  `is_async`/`checked` locals as the canonical shape in
  `callable_dispatch.py`, and `nxt`'s type moved from `Callable[[T], T]` to
  the existing `Mapper[T, T]` — dispatched rather than pre-call-rejected
  (the `flat_map` shape), since an async `nxt` is not structurally impossible
  the way an async `flat_mapper` is, and rejection would still miss a
  callable object with an async `__call__`. New capability spec
  `stream-iterate`, covering the lazy seed/`nxt` sequence and all four
  sync/async function/callable-object forms — nothing had specified
  `iterate()`'s own contract before this.

  **(b)** `Stream.concat(a, b)` built its result with an empty close-handler
  list, discarding both operands' handlers. It now constructs the result with
  `a._close_handlers + b._close_handlers` — a fresh list, so registering a
  handler on either input after `concat()` returns does not retroactively
  reach the result — matching Java's `Stream.concat`, whose result closes
  both inputs. ADDED requirement on the `stream-concat` capability, a clean
  spec gap rather than a rule change.

  **(c)** `close()` collected every handler's exception but discarded every
  one except the first. It still raises the first — that rule is unchanged,
  pinned by the existing `test_close_with_multiple_raising_handlers_runs_all_and_raises_first`,
  verified to pass unmodified — but now attaches the later exceptions to it
  via `BaseException.add_note()` (Python 3.11+) in encounter order, so a
  traceback shows all of them. On 3.10 the behaviour is exactly what shipped
  before: first exception raised, no notes. `sys.version_info >= (3, 11)`
  narrows for `ty` without a cast, which `hasattr(exc, "add_note")` would
  not. MODIFIED requirement on `stream-close-handling`.

  **Tripwire held exactly as scoped:** the only test files touched are
  `tests/test_iterate.py`, `tests/test_concat.py` and `tests/test_close.py`,
  and the pinned multi-raise test needed no edit. 561 tests green (536 + 25
  new), `ruff`, `ruff format --check`, `ty check src` and
  `openspec validate --strict` all pass, coverage 98.03%. No benchmark gate:
  every site here runs once per stream, once per `concat()` call, or once
  per `close()` call, never per element — story 4 is the batch's only
  benchmark-gated story. README's `iterate` row now notes `nxt` may be sync
  or async; no migration-log entry, since the only call shape whose result
  changed was already producing garbage. See
  `openspec/changes/settle-stream-api-outside-the-chain`.

- **Took the final three-part smalls batch: `unordered()`/`on_close()`
  docstrings, the `PROCESSES` top-level export, and the dead `pylint`
  pragmas in `collector.py`** (2026-08-24). The last item of the 2026-08-24
  legibility batch, closing it out entirely.

  **(a)** `unordered()` (`stream.py:151`) and `on_close()` (`stream.py:158`)
  each gained a one-line docstring stating they mutate and return `self` by
  design, unlike the eight derive-and-consume intermediate ops — pointing at
  the `stream-ordering` spec and `pipeline-immutability` spec line 58
  respectively, the requirements that already made this deliberate.

  **(b)** `PROCESSES` is now exported from `snakestream/__init__.py`
  (`from snakestream.execution import PROCESSES as PROCESSES`), so
  `from snakestream import PROCESSES` works. Decided in favor of exporting
  rather than narrowing README, matching how README already documented
  `.parallel()`/`PROCESSES` as a stable public pair. New capability
  requirement added to `stream-execution-model` covering the import path;
  no README wording change was needed, and no existing top-level-exports
  table needed touching (none exists). Covered by a new
  `tests/test_package_exports.py`.

  **(c)** The four `# pylint: disable=missing-*-docstring` /
  `# pylint: disable=invalid-name` pragmas at the top of `collector.py`
  were confirmed dead (no `pylint` config or invocation anywhere in the
  repo — only comment pragmas, here and in two unrelated test files left
  out of scope) and deleted.

  536 tests green (535 + the new export test) with **no existing test file
  edited**; `ruff`, `ruff format --check`, `ty check src` and
  `openspec validate --strict` all pass, 98% coverage. Off the per-element
  path (docstrings are read not executed; the export and pragma removal are
  import-time/lint-time only), so no benchmark gate applied. See
  `openspec/changes/archive/2026-08-24-batch-small-fixes-2026-08-24`.

- **Added module docstrings to `execution.py`, `sink.py` and `ops.py`**
  (2026-08-24). All three opened straight into imports; the map that
  explains how the chain-of-ops model executes — the four execution
  primitives and the two executors, the op/sink `begin`/`accept`/`end`
  protocol, one `Op`/`Sink` pair per intermediate operation — lived only in
  `CLAUDE.md`, a file a reader opening any of the three directly might never
  see.

  Each docstring is four or five lines and orientation only, not a
  restatement of what the per-class docstrings in the same file already
  say: `execution.py` names `stream_through`/`race_through`/`feed_through`/
  `drain` and `Sequential`/`Racing`, and points at `Sequential.value()`'s
  docstring for the fused-push figures rather than repeating them;
  `sink.py` names the `Sink` protocol and the shapes built on it;
  `ops.py` states it holds no execution logic, which lives in
  `execution.py`.

  Pure documentation, `skip_specs: true`: no spec-level behavior changed,
  only what a reader sees before the imports. 535 tests green with **no
  test file edited**; `ruff`, `ruff format --check` and `ty check src` all
  pass. Off the per-element path (docstrings are read, never executed), so
  no benchmark gate applied. See
  `openspec/changes/add-execution-module-docstrings`.

- **Trimmed the `IllegalStateException` message to drop "or terminally
  consumed"** (2026-08-24). `stream.py:97` read "this stream has already been
  extended into a new instance **or terminally consumed**", but `_consumed =
  True` is only ever set by `_derive()`, the shared copier behind the eight
  intermediate ops and `.parallel()`/`.sequential()` — never by a terminal.
  `pipeline-immutability` spec explicitly requires a merely-terminally-consumed
  stream to stay usable, and `terminal-sinks` spec already worded the scenario
  without the "or terminally consumed" clause; only the exception string
  disagreed with both.

  One-line change to `_check_not_consumed()`, scoped to the message string.
  `skip_specs: true`: the specs already described the correct behavior, so
  nothing in `openspec/specs/` changed. No test asserts the message text
  (verified 2026-08-24 against all eight `pytest.raises(IllegalStateException)`
  sites across `test_pipeline_immutability.py` and `test_execution_model.py`),
  so 535 tests passed with **no test file edited**; `ruff`, `ruff format
  --check` and `ty check src` all pass. Off the per-element path (raised only
  on reuse of a consumed stream reference), so no benchmark gate applied. See
  `openspec/changes/archive/2026-08-24-fix-illegal-state-exception-message`.

- **Extracted a neutral `_ArgsOp` base for `StatelessOp`/`StatefulOp`**
  (2026-08-24). `StatefulOp`'s docstring spent a paragraph disclaiming its own
  base class — "Subclassing `StatelessOp` is a mechanical convenience ... It
  does not mean a stateful op is a kind of stateless one" — while the two
  classes shared only `__init__` and the `_sink_cls` `ClassVar` declaration
  and differed solely in `link()`. When a class docstring has to argue
  against the hierarchy it sits in, the hierarchy is misleading the reader,
  not the docstring.

  `sink.py` now has `_ArgsOp(Op)` holding the shared `__init__(self, *args)`
  and `_sink_cls` declaration, with `StatelessOp(_ArgsOp)` and
  `StatefulOp(_ArgsOp)` as siblings, each defining only its own `link()`.
  `StatefulOp` no longer subclasses `StatelessOp`, so the disclaimer
  paragraph is deleted rather than kept — its docstring now only explains
  what shared state is and how a subclass declares it. Both names stay
  importable and subclassable exactly as before, which is what
  `tests/test_sink.py`'s existing imports and subclasses of both exercise.

  Pure structural refactor, scoped to `sink.py`'s `Op` hierarchy alone;
  `ops.py`'s op definitions and every caller of `link()`/construction are
  unaffected. `skip_specs: true`: no spec-level behavior changed, only where
  two private class declarations sit in the hierarchy. 535 tests green with
  **no test file edited**; `ruff`, `ruff format --check` and `ty check src`
  all pass. Off the per-element path (`Op` construction and `link()` run once
  per composition, never per element), so no benchmark gate applied. See
  `openspec/changes/extract-op-base-class`.

- **Renamed `Stream._stream` to `Stream._source`** (2026-08-24). `stream.py`
  named the normalized `AsyncGenerator` source `self._stream`, while every
  function in `execution.py` that receives the same value (`stream_through`,
  `race_through`, `feed_through`, `_guarded`) names it `source` — reading
  `self._executor.elements(self._chain, self._stream)` required stopping to
  work out whether `_stream` was the raw source or something already
  composed. Now every call site reads as the `(chain, source)` pair the three
  execution primitives already take.

  Pure private rename, scoped to `stream.py`'s field declaration, `_derive`,
  `_compose` and `_evaluate` — the only methods referencing it after the
  `_evaluate()`/`_derive()` consolidations. `skip_specs: true`: no
  spec-level behavior changed, only an internal attribute's name. 535 tests
  green with **no test file edited** (a grep for `_stream` across `src/` and
  `tests/` confirmed zero references before archiving, matching the item's
  own prediction); `ruff`, `ruff format --check` and `ty check src` all pass.
  Off the per-element path (read once per composition or drive-entry), so no
  benchmark gate applied. See
  `openspec/changes/rename-stream-source-field`.

- **Routed every terminal through `_evaluate()`.** `_evaluate()`'s docstring
  called itself "the one place a stream's execution mode is consulted", but
  `for_each_ordered()` and `find_first()` each bypassed it and hand-rolled
  `self._check_not_consumed()` + `SEQUENTIAL.value(self._chain, self._stream,
  sink)` directly — three drive sites instead of one. `_evaluate()` gained an
  optional `executor: Executor | None = None` parameter
  (`(executor or self._executor).value(...)`); both terminals now read
  `await self._evaluate(sink, SEQUENTIAL)`.

  Landed exactly to the shape this entry's own implementation notes proposed,
  with no surprises: no behaviour changed (both terminals still force
  sequential/ordered execution regardless of the stream's mode,
  `find_first()`'s `is_ordered()` short-circuit to `find_any()` untouched),
  and the `stream-find-first` spec's wording ("achieve this by naming the
  sequential executor explicitly for that drive") held verbatim against the
  new call shape — checked directly, no edit needed. `skip_specs: true`: no
  spec-level behavior changed, only how many places decide which executor
  drives a terminal. 535 tests green with **no test file edited**; `ruff`,
  `ruff format --check`, `ty check src` and `openspec validate --strict` all
  pass. A grep for `self._stream` after the edit confirms only `__init__`,
  `_derive`, `_compose`, `_evaluate` and `_derive_executor` reference it now —
  `for_each_ordered()` and `find_first()` were the only two hand-rolled call
  sites, and both are gone. See
  `openspec/changes/route-terminals-through-evaluate` (pending archive).

- **Merged `_derive()` and `_derive_executor()` into one copier** (2026-08-24).
  `stream.py:99-106` and `stream.py:132-137` were line-for-line the same
  five-field copy — `self._stream`, `self._close_handlers`, `self._chain`,
  `self._ordered`, `self._executor` — differing only in whether `_chain` or
  `_executor` was the field that varied. Now one `_derive(self, chain:
  list[Op], executor: Executor) -> Stream[Any]` takes both as parameters: the
  eight intermediate ops call `self._derive(self._chain + [op],
  self._executor)`, and `parallel()`/`sequential()` call
  `self._derive(self._chain, RACING)` / `self._derive(self._chain,
  SEQUENTIAL)`. `_derive_executor()` is gone.

  Landed to the shape the roadmap's own implementation notes proposed, with
  one adjustment: the pre-existing `_derive()` took a single `op: Op` and
  composed `self._chain + [op]` internally rather than taking a pre-built
  chain, so the call sites (not just the method body) needed the `self._chain
  + [op]` expression moved onto them — the unified signature is
  `_derive(chain, executor)` exactly as designed, only the caller-vs-callee
  split of that one line differs from the sketch. The check-before-copy /
  consume-after-copy ordering is unchanged: `_check_not_consumed()` still runs
  before the copy and `self._consumed = True` still after, so a raising copy
  leaves the receiver valid. The `_derive_executor()` docstring ("must not
  compose", "must not assign onto self") moved onto `parallel()` and
  `sequential()` rather than being deleted with the method, since those two
  are the only call sites its warning actually protects.

  535 tests green with **no test file edited**; `ruff`, `ruff format --check`
  and `ty check src` all pass. A grep for `_derive_executor` across `src/` and
  `openspec/specs/` after the edit returns nothing. `skip_specs: true`: no
  spec-level behavior changed, only where the copy-constructor logic lives.
  Off the per-element path (chain-building/mode-switch code, run once per
  composition), so no benchmark gate applied. See
  `openspec/changes/unify-derive-copier`.

- **Moved `to_collection()`'s private `_C` TypeVar and `_SupportsAdd`
  protocol from `collector.py` to `type.py`** (2026-08-24). The last public
  collector signature naming a type outside `type.py`, the project's
  established home for shared callable/composite type aliases —
  `to_collection(collection_supplier: Supplier[_C]) -> Collector[Any, _C,
  _C]` kept `_C`/`_SupportsAdd` defined locally instead. Deliberately left
  alone on 2026-08-21 when the other 18 collector factories widened their
  accumulator parameter to `Any`, because here `A` genuinely is the caller's
  own container type rather than an internal box, so `_C` had to move rather
  than be erased.

  Pure relocation, both names moved together as a pair since `_C`'s bound is
  `_SupportsAdd`: `to_collection`'s signature and behavior are unchanged, and
  both stay private (leading underscore) and unexported — a caller never
  writes `_C` themselves, the checker infers it. Full suite green (535
  tests) with **no test file edited**, `ruff`, `ty check src` and `openspec
  validate --strict` all pass. `skip_specs: true`: no spec-level behavior
  changed, only where two private type declarations live. See
  `openspec/changes/archive/2026-08-24-move-to-collection-typevar-to-type-module`.

- **Collapsed `BaseStream` into `Stream`; `base_stream.py` is gone**
  (2026-08-24). The split existed because Java needs `BaseStream` as the shared
  parent of `Stream`/`IntStream`/`LongStream`/`DoubleStream`. This library never
  implemented the primitive specializations, and after the `ParallelStream`
  retirement below there was exactly one concrete subclass left — so the
  two-level tree held state on one class and operations on the other for no
  remaining reason. Exactly what the guiding principle targets: Java structure
  with no remaining Python reason to exist.

  **The roadmap entry demanded confirmation rather than assumption, and got
  it.** `BaseStream` was never exported from `__init__.py`; nothing in `src/` or
  `tests/` did `isinstance(x, BaseStream)` or subclassed it directly — the
  README's documented subclassing use case (wrapping an I/O-like resource via
  `on_close()`) already subclasses `Stream`; and the one test dependency on the
  split, `tests/test_sequential.py`'s `from snakestream.base_stream import
  _wrap_sink`, turned out to be importing a re-export of `execution.py`'s
  `_wrap_sink` rather than anything `base_stream.py` defined — a one-line
  import-path fix, not a behaviour edit.

  `Stream` is now `Generic[T]` directly, with every merged method keeping its
  signature and behaviour. README's separate `### BaseStream` API table was
  merged into `### Stream` (both always listed instance methods of the same
  runtime class), and `CLAUDE.md`'s architecture section, which attributed
  `self._stream`/`self._chain`/`self._executor`/`self._consumed` and the
  AutoClose pair to `BaseStream`, now describes `Stream`. Full suite green with
  that single import-path edit as the only test change; `ruff`, `ty` and
  `openspec validate --strict` all pass. The one surviving `BaseStream`
  reference in `openspec/specs/` is deliberate: `stream-ordering`'s Purpose
  cites *Java's* `BaseStream.unordered()` as the mirrored API. See
  `openspec/changes/archive/2026-08-24-collapse-base-stream-into-stream`.

  **Opened the 2026-08-24 legibility batch** now sitting at **Now** items 2-8:
  with the state and the operations finally in one file, reading `stream.py`
  end-to-end surfaced the three-drive-sites/one-docstring mismatch, the
  duplicated derive bodies and the `_stream`-vs-`source` naming split.

- **Retired the `ParallelStream` name from the specs and docstrings**
  (2026-08-24). `replace-parallel-stream-with-executor` deleted the class on
  2026-08-21 but not the name: two requirements whose deltas were never written
  or were missed by a truncated scan, ten spec `## Purpose` sections (a delta
  cannot touch Purpose — OpenSpec ignores `MODIFIED` blocks against it, so
  these needed direct edits), five docstrings in `sink.py` and
  `callable_dispatch.py`, and four scenario titles kept back because a
  `MODIFIED` block may not drop a scenario name the main spec still has.

  No behaviour gap anywhere in it — every described behaviour was correct and
  covered throughout — which is what made it worth one pass rather than a leak
  across several commits: readability debt of the misleading kind, where a
  reader grepping for `ParallelStream` found specs and docstrings promising a
  class the codebase no longer had. `grep -rn ParallelStream openspec/specs/
  src/` now returns nothing. Full suite green with **no test file edited**.
  Out of scope deliberately, and still true today: test-file comments and
  section headers, and the README migration-log entry that has to name the
  retired class to explain what was retired. See
  `openspec/changes/archive/2026-08-24-retire-parallelstream-name`.

- **Replaced the `Stream` -> `ParallelStream` subclass with execution mode as a
  value, and made `.parallel()`/`.sequential()` position-independent.** These
  landed together because they are mechanically the same edit: the
  compose-and-handoff is what carried mode as a type *and* what made the
  switches positional.

  **The exploration changed the shape of the item before it was proposed.** It
  had been framed as an internals cleanup — inverted default/override, two
  dispatch seams, an import cycle. Tracing `.parallel().map(f).count()`
  end-to-end surfaced two things the entry had not:

  *One name carried two meanings.* `_drive_to_sequential()` was both the fused
  fast path (performance) and "force encounter order, ignore the stream's mode"
  (semantics, used by `for_each_ordered` and `ParallelStream.find_first`). They
  shared an implementation by coincidence, so reading
  `ParallelStream.find_first() -> _drive_to_sequential()` gave no way to tell
  which was meant. They are now separate: the fast path is an implementation
  detail of `Sequential`, and forcing order is `SEQUENTIAL.value(...)` written
  at the call site.

  *`.parallel()` was position-dependent and Java's is not.* Because `_handoff()`
  composed the chain-so-far into a generator, ops declared before the switch
  were frozen under the old mode. Measured, 8 elements through a 100 ms async
  mapper: `.parallel().map(slow)` took 0.20s, `.map(slow).parallel()` took
  0.81s — identical to fully sequential. Java's `AbstractPipeline.parallel()` is
  `sourceStage.parallel = true; return this;`, a flag on the source stage, so
  the whole pipeline is affected wherever the call appears. With 1:1 public API
  parity as this project's first priority, that made it an API divergence rather
  than an internals detail. After the change both forms take 0.20s. **Note this
  inverts the trap the old roadmap entry warned about** — it cautioned that
  flipping a flag instead of handing off would "silently change semantics",
  which is true, but the semantics it changes *to* are Java's. What survived
  from that warning is the immutability half: the switch must still return a new
  instance and consume the receiver, so it is `_derive_executor()`, never
  `self._executor = X; return self`.

  **Racing was kept deliberately, not by omission.** Partition-plus-combine
  (spliterator splits, per-partition pipelines, a `combiner` merge) was explored
  and set aside: Java's own answer for a non-splittable source
  (`Spliterators.IteratorSpliterator.trySplit()`, which drains a growing batch
  into an array) trades latency-to-first-element for throughput, which is the
  wrong trade for an async/IO-first library where racing yields an element the
  instant any branch produces one. The rule adopted: **Java is the public-API
  contract, not the implementation blueprint.** Partitioning, `spliterator()`
  and combiner wiring stay in **Later**.

  **The one asymmetry in the new protocol is there on measurement.**
  `Executor.value()`'s generic default is `drain(elements(...), terminal)`,
  which `Racing` inherits unchanged; `Sequential.value()` overrides it with the
  fused push. The task list put a gate before the design was allowed to keep
  that override, and it came back far larger than the +10-50% band the
  flush-dedup measurements had set as the expectation (Python 3.14.5, 20,000
  elements, no intermediate chain, best of 5, ns/element):

  | Variant | Fused | Generic | Delta |
  |---|---|---|---|
  | `count()` | 303 / 296 / 320 | 669 / 664 / 745 | **+125%** |
  | `reduce(acc)` sync | 353 / 351 / 348 | 745 / 739 / 775 | **+112%** |

  More than twice the cost per element, because this removes the async-generator
  round trip entirely rather than adding one object to a loop that already had
  one. The override stays and carries these figures in its docstring.

  **What went away:** `ParallelStream` and `parallel_stream.py`; `_drive`,
  `_drive_to`, `_drive_to_sequential`, `_parallel` and `_handoff`; both dispatch
  seams, replaced by `_compose()` and `_evaluate()`, one line each; the
  `stream.py` <-> `parallel_stream.py` import cycle and its two function-local
  import workarounds; `ParallelStream.find_first()`, unified into one
  implementation selecting on the ordering flag; and one generator layer per
  element on parallel pipelines, since a mode switch no longer composes
  (`.parallel().map(f).count()` went from five async-generator frames to four).
  **What arrived:** `execution.py` with four primitives, two executors and
  `PROCESSES`. It also **fixed a live bug**: `.parallel()`/`.sequential()` were
  the only ops in the library that discarded a `Stream` subclass and its
  attributes, despite CLAUDE.md documenting subclassing as supported.

  **The "green with no test edited" tripwire could not apply** — the behaviour
  change is the point — so it was replaced with a diff check: only the test
  sites identified *before* any source edit were allowed to differ. The
  pre-analysis found 51 `.parallel()` sites across 17 files, zero with an op
  before `.parallel()` on the same line, and four multi-line chains that change
  what runs raced. All four assertions were predicted to survive, and did; the
  two in `test_close.py` passed untouched. The two in `test_sequential.py` and
  `test_parallel.py` were rewritten rather than patched, because they tested
  mid-chain mode switching — a concept this change retires — and their names
  were already inverted relative to what they did. They now assert the new rule
  by timing, the same measurement that found the divergence. 535 tests green,
  coverage 98.08%. One new capability (`stream-execution-model`) and 11 spec
  deltas. See `openspec/changes/replace-parallel-stream-with-executor`.

  **Two decisions resolved along the way, recorded so they are not re-opened.**
  `Racing` holds `workers` as a field, which makes a public `.parallel(n)`
  trivially available — **deliberately not exposed**, because Java has no such
  overload and 1:1 surface parity is the first priority. Tune `PROCESSES`
  instead. And `unordered()` **stays a stream flag rather than moving onto the
  executor**: the executor answers *how* a pipeline runs, the flag answers
  *whether the caller requires encounter order*. Folding the flag in would mean
  `Racing` needed ordered and unordered variants, which is how `find_first()`
  ends up with two implementations again — the exact thing this change removed.

  **Left open deliberately:** whether `BaseStream` should collapse into `Stream`
  now that `ParallelStream` is gone. Java has `BaseStream` because
  `IntStream`/`LongStream`/`DoubleStream` share a parent; this library has no
  primitive specializations and already collapsed that distinction, so the split
  may be organizing nothing. It roughly doubles the diff and is independently
  revertable, so it is a follow-up rather than part of this change.

- **Took the small-cleanups batch: `to_list` as a factory, the race loop's
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

- **Dropped the pointless `async` on `Stream.concat`.** `concat` was an
  `async def` whose body never awaited anything — it built `_concat(a, b)`, an
  async generator (so *calling* it runs none of its body), and wrapped it in a
  `Stream`. The `async` bought nothing and cost every caller an `await` that
  could not suspend, plus the requirement to be inside a coroutine to call it
  at all. It is now a plain `def`, matching the other four static factories
  (`of`, `empty`, `builder`, `iterate`) and Java's static `Stream.concat`.

  **The one real decision was clean break vs. compatibility shim.** A `Stream`
  subclass with `__await__` returning itself would have kept both call forms
  working through a deprecation window; rejected because it puts an
  `__await__` on a `Stream` either permanently or until a *second* breaking
  change removes it, making the type worse than the one being fixed. The
  project's pre-1.0 convention is a hard break plus a migration-log line
  (`stream_of()` -> `Stream.of()`, the `Stream.of()` kwargs removal, the
  `str`/`bytes` change), and that is what this took. No custom error either:
  an unmigrated call site raises `TypeError: object Stream can't be used in
  'await' expression`, which names the exact expression at fault, and a bespoke
  `StreamBuildException` would have needed the rejected `__await__` to raise
  from.

  Scope stayed at one line of `src/`: `_concat`, the generator bridge, and the
  `_consumed` bookkeeping are all untouched, so `concat` still leaves both
  input streams unconsumed. A variadic `concat(*streams)` was named a non-goal
  rather than left open — Java's is two-arg. Seven tests added in
  `tests/test_concat.py` on top of the two existing ones dropping their
  `await`: returns a `Stream` rather than a coroutine, `await` on the result
  raises `TypeError`, callable from plain sync code with no running loop,
  empty input on either side, and both laziness properties checked through
  `peek` (nothing pulled at construction; the second stream untouched while
  the first is being consumed). Those last two codify behaviour that was
  already true — worth pinning precisely because the removed `async` is what a
  reader might mistake for the source of the laziness.

  Also corrected by omission: README's API table row for `concat` already
  listed the return type as `Stream` while sibling rows mark awaitables
  explicitly (`collect` reads `R (awaited)`), so the row was wrong before this
  change and is right now — no edit needed. New spec capability
  `stream-concat`; nothing in `openspec/specs/` covered `concat`'s own
  behaviour before, only `terminal-sinks`' note that it composes through the
  generator bridge, which still holds verbatim. 512 tests green, coverage
  98.20%. See
  `openspec/changes/archive/2026-08-21-drop-async-on-concat`.

- **Measured and rejected: collapsing `Stream.min`/`max`, `count` and `reduce`
  onto the `min_by`/`max_by`, `counting()` and `reducing()` collectors.**
  The duplication was real — `_MinMaxSink` and `_extremum` were the same
  algorithm down to a verbatim copy of the comparator-contract comment,
  `_CountSink` and `counting()` the same `+= 1`, `_ReduceSink` and
  `reducing()`'s two-arg form the same `_UNSET`-seed fold — and the collapse
  was implemented in full to find out what it cost.

  **Equivalence is not in doubt**, which is what makes the rejection a pure
  cost decision. With all three terminals routed through `collect(...)` and
  the three sinks deleted, the **whole 505-test suite passed with no test file
  edited**, and a separate 21-case audit (empty sources, singletons, falsy
  identities, first-of-tied tie-break, the `bool`-comparator `TypeError`, async
  callables, and all three on a `ParallelStream`) found **zero** differences
  between the two forms.

  **Killed on measurement at the gate the change's own tasks placed after the
  collapse.** Both forms are public API today, so baseline and collapsed ran
  interleaved in one process against the same source — a tighter comparison
  than the usual edit-and-remeasure. Harness otherwise as established (Python
  3.14.5, 20,000 elements, best of 5, three independent invocations), with one
  deliberate change: **no intermediate chain**, since here the terminal is the
  subject and an empty chain maximizes its share of per-element cost. Gate was
  +10% on the sync variant, the level `collapse-terminal-drive-loop` already
  treated as real:

  | Variant | Baseline ns/element | Collapsed ns/element | Median delta |
  |---|---|---|---|
  | `count()` | 298 / 306 / 299 | 360 / 332 / 357 | **+19.6%** |
  | `min(cmp)` sync | 467 / 442 / 422 | 608 / 560 / 522 | **+26.5%** |
  | `min(cmp)` async | 558 / 551 / 513 | 648 / 626 / 651 | +16.2% |
  | `reduce(acc)` sync | 332 / 356 / 354 | 622 / 562 / 601 | **+69.6%** |
  | `reduce(0, acc)` sync | 369 / 331 / 355 | 630 / 590 / 601 | **+70.6%** |
  | `reduce(acc)` async | 454 / 468 / 466 | 657 / 720 / 714 | +53.3% |

  All three failed, so all three took the fallback. The cause is the same one
  `add-callsite-dispatch` established: a `Collector` must be reusable across
  concurrent collections, so its per-collection dispatch state lives on a
  supplier-made box reached through a Python-level `async def` call, where a
  sink has it inline on `self`. `reduce` is worst by a wide margin because
  `reducing()` additionally routes every element through `_classify_step`,
  which is a function call plus a tuple allocation and unpack per element per
  callable — precisely the cost `optimize-callable-dispatch` hoisted out of the
  per-element path in the first place.

  **What landed instead — the per-terminal fallbacks, all behaviour-neutral,
  505 tests passing unedited at 98.20% coverage:**

  - **`min`/`max`: the shared rule was extracted, and it made both sides
    faster.** `sort.py` gained `is_new_extremum(sign, asc)`, holding the
    comparator-contract check, the sign test and the first-of-tied rule — the
    part that had been duplicated verbatim — called by both `_MinMaxSink` and
    `_extremum`. It *replaces* their existing `check_comparator_result_type()`
    call rather than adding a second one, and inlines the `type(sign) is not
    int` test so only the raising path calls out. Net one fewer Python-level
    call per element: `min` sync went **442 -> 404 ns/element**. (Delegating to
    `check_comparator_result_type` instead of inlining the test measured ~5%
    slower, which is why it does not.)
  - **`count`: roadmap item 2(c) taken as the fallback.** `_CountSink` now
    accumulates into a plain `int` instead of a `Counter` box, since the sink
    owns its container exclusively — 300 vs 299 ns/element, i.e. neutral on
    time, with one allocation and one indirection gone. `counting()` keeps its
    box, which it genuinely needs: its accumulator is a free function that has
    to mutate a container it was handed. `Counter` itself stays regardless —
    `ops.py`'s `_LimitOp` and `_SkipOp` use it as state shared across a
    `ParallelStream`'s branches, the case a plain `int` cannot serve.
  - **`reduce`: cross-referenced, not merged.** The shared part is the
    `_UNSET`-seed rule and the empty-finishes-as-`None` rule — two lines and a
    comment, not an extractable function. `_ReduceSink`'s docstring and
    `reducing()` now each point at the other, recording that the duplication is
    deliberate and measured and that a change to either rule belongs in both.

  **Consequence:** routing these terminals through a `Collector` is now a
  deliberately-accepted cost with numbers behind it rather than an open cleanup
  item, and should not be re-proposed without new evidence — the same posture
  `add-callsite-dispatch` established. The narrower reading that *did* pay off
  is worth keeping in mind: extracting a **sync** helper that replaces an
  existing per-element call is free or better, while anything adding a
  coroutine frame or a box to the per-element path is not. `stream.py` is
  untouched; `README.md` changed only in the `min_by`/`max_by` rows, whose
  "Wraps `Stream.min()`'s existing logic" wording is now "shares the rule
  with", which is what the code actually does. See
  `openspec/changes/collapse-terminal-collector-duplication`.

- **Collapsed the two terminal drive loops into `_copy_into()`.**
  `BaseStream._drive_to_sequential()` and `ParallelStream._drive_to()` each
  spelled out the same begin / cancellation-guard / accept-loop / end sequence;
  both now call a module-level `_copy_into(head, src, state_map)` in
  `base_stream.py`, named after Java's `AbstractPipeline.copyInto()` the way
  `_wrap_sink()` is named after `wrapSink()`. The pre-first-pull guard's
  reasoning — a chain can already be cancelled before it has seen anything
  (`limit(0)`) — now has one home instead of being a comment in one of three
  copies. `ParallelStream._drive_to()`'s `_maybe_aclosing` scope widened to
  cover the whole drive, matching the sequential form; the only delta is
  constructing (never starting) the composed generator on the already-cancelled
  path, verified to start no task and leave nothing pending. Two source files,
  +21/-19 lines, no test assertion changed (two stale comment references in
  `tests/test_sink.py` were repointed at `_copy_into()`), coverage 98.15% ->
  98.21%. **No README edit was needed**: every name involved — `_copy_into`,
  `_drive`, `_drive_to`, `_drive_to_sequential`, `_maybe_aclosing`,
  `_wrap_sink` — is private and unexported, and no parity table entry changes.

  Folded in before archiving: `_compose()` gained the docstring it was missing.
  It is the third member of the dispatching/overridden family alongside
  `_drive_to` and `_drive_to_sequential` — the seam where execution mode is
  decided, which `ParallelStream` overrides to fan the chain into a race — and
  it was the only one not saying so, which made it read as a pointless
  delegation to `_drive()`. `_drive()` cannot be that seam: `_parallel()` calls
  it once per racing branch, so overriding it would make each branch fan out
  again.

- **Rejected: deduplicating `BaseStream._drive()`'s bridge-buffer flush block.**
  The same roadmap item proposed a local closure for the two verbatim four-line
  flush blocks at `base_stream.py:120-123` and `127-130`. `_drive()` has to
  `yield` mid-loop, so it cannot use `_copy_into()` at all, and every
  single-flush-site form puts a per-element object on the `iterator()` /
  `to_generator()` / parallel-branch path — the in-loop flush runs once per
  element; only the post-`end()` flush is once per stream. Measured on the
  established harness (Python 3.14.5, 20,000 elements, chain of 8 `.map()` ops,
  best of 5, three independent invocations), baseline reproducing the
  1,907 ns/element `add-callsite-dispatch` recorded:

  | Variant | ns/element (3 runs) | vs baseline |
  |---|---|---|
  | **Baseline** — duplicated block, as shipped | 1929, 2091, 1907 | — |
  | Single site via **async-generator** closure | 3002, 2932, 3009 | **+50%** |
  | Single site via **sync-generator** closure | 2137, 2123, 2217 | **+10%** |

  This is the same trade `GeneratorBridgeSink`'s docstring already records
  rejecting for a `drain()` returning a fresh list. By contrast `_copy_into()`,
  entered once per stream, measured free: 1686/1620/1741 baseline vs.
  1625/1654/1739 with the helper on a `count()` terminal — noise in both
  directions. **Do not re-propose the flush dedup without new figures.**

- **Fixed the dead `__next__` branch in `_normalize()`.** The guard admitted a
  source on `hasattr(source, "__iter__") or hasattr(source, "__next__")` while
  the body was `for i in source`, so a sync iterator implementing only
  `__next__` passed the guard and then died with `TypeError: 'X' object is not
  iterable`. **Decided to make the advertised support real rather than narrow
  the guard**, because three things already promised it and only the code
  disagreed: README lists `Iterator` among accepted sources, the
  `stream-construction` spec's "Iterable source spreading" requirement names
  `__next__` explicitly, and `_maybe_aclosing`'s docstring exists precisely so
  a bare `__anext__`-only async iterator works — narrowing would have meant
  retracting a capability in all three and leaving the sync and async sides
  deliberately asymmetric.

  `__iter__` is still checked first, so lists, tuples and every other plain
  iterable run exactly the code they did before (`next([1, 2, 3])` is a
  `TypeError`, so one merged path was never an option); the new arm only
  catches sources with `__next__` and no `__iter__`. The non-obvious part is
  PEP 479: a `StopIteration` escaping an async generator body surfaces as
  `RuntimeError: async generator raised StopIteration`, so the loop guards the
  `next()` call alone and keeps the `yield` outside the `try` — which also
  means a `StopIteration` thrown in at the yield still propagates instead of
  being swallowed into a silent end-of-stream.

  Behaviour-preserving for every source that worked before; the only sources
  whose behaviour changed are ones that raised `TypeError`. No public API
  change, so no migration-log entry. Seven tests added in
  `tests/test_normalize.py`, including an `assert not hasattr(obj, "__iter__")`
  guard so they can't drift onto the `__iter__` path, the immediately-exhausted
  case that covers the `except StopIteration` arm, and a laziness check that
  `limit(2)` advances the source exactly twice. See
  `openspec/changes/archive/2026-08-20-fix-next-only-source-normalization`.

- **Added the four remaining Java 8 `Collectors`** — `mapping(mapper,
  downstream)`, `collecting_and_then(downstream, finisher)`,
  `summarizing_int`/`summarizing_long`/`summarizing_double`, and
  `to_collection(supplier)`. `mapping`/`collecting_and_then` are
  downstream-adapting collectors built on the same downstream-`Collector`
  composition `grouping_by`/`partitioning_by` already used; the `summarizing_*`
  trio shares the `_summing` dispatch idiom and finishes to a new
  `SummaryStatistics` `NamedTuple` rather than Java's mutable
  `IntSummaryStatistics` — with `min`/`max` as `None` on an empty stream,
  following `min_by`/`max_by`'s convention here instead of Java's sentinel
  ints; and `to_collection` generalizes `to_list`/`to_set` to any
  `add()`-supporting container. Additive, no public API change. This closes out
  Java 8 `Collectors` parity, and unblocked the min/max/count/reduce collapse
  that was a **Now** item at the time — since implemented in full, measured,
  and rejected on cost (see the entry above). See
  `openspec/changes/archive/2026-08-20-add-remaining-java8-collectors`.

- **Redesigned `collector.py`'s collectors around a `Collector(supplier,
  accumulator, combiner, finisher)` shape**, matching Java's `Collector<T,A,R>`
  interface. Every factory (`to_list`, `joining`, `counting`, `summing_*`,
  `averaging_*`, `min_by`/`max_by`, `reducing`, `to_map`, `to_set`,
  `grouping_by`, `partitioning_by`) now returns a `Collector` instead of a
  monolithic `async def _collect(composition): async for n in composition:
  ...` closure, driven through one new `_CollectorSink` (`TerminalSink`
  adapter) rather than each factory hand-rolling its own drain loop. This
  deletes the second, independent implementation of `terminals.py` that
  `collector.py` used to carry: `_extremum` (gone, replaced by a shared
  `_extremum` collector factory using the same tie-break and
  comparator-guard as `_MinMaxSink`), the duplicate `_UNSET` sentinel (now
  one, in `sink.py`), and the separate counting/reducing bodies.

  Two **BREAKING** changes, both pre-1.0 and both contained — no test in the
  457-test suite exercised either pattern: `collect(collector)` now requires
  a `Collector` (or `to_generator`, wrapped as the one `StreamingCollector`
  exception) rather than an arbitrary callable, and `grouping_by`/
  `partitioning_by`'s `downstream` now requires a `Collector` too. The second
  break has a real behavioral consequence: each group/partition now
  accumulates into its own downstream container as elements arrive, instead
  of being buffered as a list and replayed through `downstream` in a
  post-pass — invisible for a pure downstream, but a downstream with side
  effects (e.g. `to_map`'s duplicate-key `ValueError`) now observes them
  interleaved with the source. Both are logged in README's migration log.

  **The central design problem was dispatch-state lifetime, not the adapter
  shape.** A `Collector` is explicitly reusable across streams and
  compositions (`to_list` is a single shared module-level instance), so its
  accumulator is one fixed function — it cannot hold the
  `is_async`/`checked` classification flags a per-element user callable
  (a mapper, comparator, key function) needs, the way the old per-collection
  closures could. Every such factory's supplier now returns a small
  `__slots__` container carrying that state alongside the accumulation
  itself, so classification is created fresh per collection and never leaks
  across collections or across a `ParallelStream`'s racing branches. This
  keeps the per-element dispatch shape exactly as `add-callsite-dispatch`
  left it — no per-element method call was added on any user callable's
  hot path.

  `TerminalSink.begin()`/`end()` in `sink.py` now await what
  `_create_container()`/`_finish()` return (via the existing `_maybe_await`),
  so an async `Collector` supplier or finisher works without every sink
  needing its own override — every existing sink's plain return value passes
  through unchanged. `sink.py` also gained `Box` (`Counter` is now a `Box`
  subclass) as the general mutable-value container the scalar collectors'
  per-collection state boxes build on.

  Measured (interleaved reps, one process, 200k elements, matching the
  `collapse-collector-sink-duplication` benchmark protocol): `collect(to_list)`
  -37%, `collect(counting())` -39%, `collect(summing_int(...))` -18% —
  faster in every case, not just neutral, since `collect()`'s single-`Collector`
  path no longer goes through the generator bridge at all (it drives a
  terminal sink directly, like every other terminal operation). 477 tests
  pass (20 new, covering the `Collector` class itself, reuse-safety across
  sequential/concurrent/parallel collections, the unused-`combiner`
  guarantee, both rejection paths, and downstream-container isolation) at
  98% coverage. See `openspec/changes/redesign-collector-shape`.

- **Collapsed the duplicated bodies in `collector.py` and the repeated
  dispatch-state boilerplate in the sinks**, the four-part item that came out
  of the 2026-08-19 simplification read. All four parts landed, all
  behaviour-neutral, no public API change and no README edit. 457 tests pass
  unchanged at 98% coverage; `tests/` was not touched at all.

  **(a) The six summing/averaging bodies became two private factories.**
  `_summing(mapper, seed, coerce)` and `_averaging(mapper)`; the six public
  names survive as one-line wrappers, each keeping its own return annotation,
  which is where the Java-primitive distinction is actually expressed. The
  `collector.py` comment defending them was reworded: it defends six *names*,
  and had been read as defending six *bodies*. `coerce` is `None` rather than
  an identity callable on the int/long path, so no call is added per element
  and a mapper returning `Decimal`/`Fraction` still sums in its own type.

  **The design's hoisting decision was reversed mid-implementation, and this
  is the interesting part.** design.md required the `coerce is None` test to be
  hoisted out of the `async for`, which means writing the loop twice. Measured
  (interleaved, 41 reps, 200k elements) that was right on its own terms: the
  hoisted form matches the pre-change code and the single-loop form costs a
  reproducible ~2% on `summing_int`/`summing_long`. But `ruff` then fails with
  `C901 _summing is too complex (11 > 10)` — the duplicated loop trips the
  project's own mccabe gate, which the design had not accounted for.
  Suppressing that gate on a function whose complexity comes *entirely from
  duplication*, inside a change whose purpose is removing duplication, was the
  wrong trade. Shipped as one loop with a per-element `coerce is None` test:
  a branch, not a call, and ~2% against the +32-75% that got
  `add-callsite-dispatch` rejected.

  **(b) Eight sinks lost their hand-copied dispatch triple** to an
  `AsyncDispatch` mixin in `callable_dispatch.py` — the module already named
  for the concept, and already holding the canonical-shape comment the mixin
  now makes checkable. `_FilterSink`/`_MapSink`/`_PeekSink` and
  `_ForEachSink`/`_ReduceSink`/`_MinMaxSink`/`_MutableReductionSink`/
  `_MatchSink` mix it in and call `_init_dispatch(fn)` from `__init__`. It is
  a plain method, not an `__init__`, so it stays out of the MRO: those eight
  sit on two different bases with different constructor signatures. The stored
  callable unified on `self._fn`, replacing five different names
  (`_predicate`, `_mapper`, `_consumer`, `_accumulator`, `_comparator`);
  constructor parameters keep their descriptive names and annotations.
  `_SortedSink` keeps its own `_comparator` — it never had the triple.
  `_MatchSink` keeps its own `_cancelled`, which is short-circuit state, not
  dispatch state. **Verified mechanically** that all eight `accept()` bodies
  are identical to their pre-change form modulo that one rename, by AST-
  extracting each and diffing against `git show HEAD:` with the rename applied
  — so nothing was added to the per-element path, which is the whole reason
  this part was allowed where `CallSite` was not.

  **(c) `grouping_by`/`partitioning_by` now share `_group_into()`.** The
  design said `partitioning_by` would pass a `key_fn` wrapping its predicate
  in `bool(...)`. **That is unimplementable and the suite catches it:**
  dispatch classifies `key_fn` and awaits its *result*, so a sync `bool()`
  wrapper sees an unawaited coroutine for an async predicate — always truthy —
  and sorts every element into the `True` bucket
  (`tests/test_partitioning_by.py:37`). Shipped instead with a separate
  optional `coerce_key` applied to the awaited key. Not hoisted, unlike (a):
  this loop body already does a `setdefault` and an `append`, and hoisting
  would duplicate the only code the part extracts. The `downstream`
  comprehension deliberately stays at both call sites — it is the line the
  `Collector` redesign rewrites.

  **(d) `StatefulOp` now subclasses `StatelessOp`**, overriding `link()` alone.
  Gated on a grep first: the only `isinstance` touching these names
  (`tests/test_op_protocol.py:84`) tests concrete subclasses, not the two
  bases, so the part was safe to do. Both docstrings kept, plus a note that
  the subclassing is mechanical convenience and that the docstrings, not the
  hierarchy, carry the shared-state distinction.

  **Came in well under estimate: -69 code lines** (excluding comments and
  docstrings), or -79 coverage-measured statements, against the ~150
  estimated. The estimate counted the raw span of the deleted bodies including
  their blank and comment lines, and this change adds explanatory comments the
  old copies did not carry. See
  `openspec/changes/collapse-collector-sink-duplication`.

- **Landed the small-cleanups batch**, the ten-entry residue left by the
  Sink-chain redesign and its four follow-up changes. Nine entries were
  behaviour-neutral; one was a real defect.

  **The one behaviour change: a chain cancelled before its first element no
  longer pulls one.** `BaseStream._drive()` and `_drive_to_sequential()`
  queried `cancellation_requested()` only *after* an `accept()`, so a chain
  already cancelled at `begin()` consumed one source element and ran every
  upstream op's side effects on it. Both loops now check once after `begin()`
  and skip the `async for` entirely; `end()` stays outside the guard, so the
  lifecycle still completes. `ParallelStream._drive_to()` got the same guard.

  **The roadmap's framing of this item was wrong and is corrected here.** It
  said "a satisfied `limit()` still pulls one extra element from the source".
  It did not: `_LimitSink` sets `_cancelled` inside the `accept()` that fills
  the last slot, so the existing post-`accept()` check already broke without an
  extra pull. The only reachable over-pull was the *pre-settled* case —
  `limit(0)`, or any op cancelled before the first element. Verified before
  starting: `Stream.of([1,2,3]).peek(seen.append).limit(0).to_array()` returned
  `[]` but left `seen == [1]`.

  **The fix needed a second half not in the original write-up.** The loop guard
  alone does nothing, because `_LimitSink._cancelled` was only ever set inside
  `accept()` — a `limit(0)` sink reported `False` right after `begin()`. Added
  `_LimitSink.begin()`, which calls `super().begin()` (that is what resolves
  `self._state`) and then settles `self._cancelled = self._state.value >=
  self._max_size`. Once per composition, not per element. `accept()` was left
  byte-identical, since a shared counter can still fill between one sink's
  `begin()` and its next `accept()`.

  **The nine neutral entries.** `BaseStream._sequential()` — which did no
  sequential execution and never touched `self` — became a module-level
  `_wrap_sink()`, after Java's `AbstractPipeline.wrapSink()`, which is exactly
  this operation; the old name sat three lines from `_drive_to_sequential()`,
  which *does* mean the execution mode. `_compose()`'s `self._chain[:]` and
  `_parallel()`'s per-branch `intermediaries[:]` were dropped (nothing mutates
  the chain, and `_derive()` already copies on extend). `GeneratorBridgeSink`
  now exposes a plain `buffer` attribute the driving loop clears in place,
  replacing a `drain()` that allocated a fresh list once per element on the
  generator path — a plain attribute, not a `@property`, since the loop reads
  it twice per element and a descriptor call would give back most of what the
  removed allocation buys. `to_generator()` dropped its hand-rolled
  `hasattr(composition, "aclose")` branch for the existing `_maybe_aclosing`
  (no import cycle: `base_stream.py` never imports `collector`, and
  `parallel_stream.py` already imported it from there). `sequential()`/
  `parallel()`, identical but for the class they construct, were factored onto
  `_handoff(cls)`, each keeping its own local import so a `sequential()` call
  does not import `parallel_stream`. `Stream.__init__` and
  `ParallelStream.__init__`, both pure `super().__init__` pass-throughs, were
  deleted, as was `to_array()`'s duplicate `_check_not_consumed()`. And
  `Accumulator` (`type.py`) was widened to
  `Callable[[T, T | R], T | R | Awaitable[T | R]]` — `_ReduceSink.accept()`
  awaits it and the suite already covered async accumulators, but
  `fix-type-py-callable-alias-defects` had scoped the terminal aliases out.

  No public API change and no README edit: every name touched is private except
  `Accumulator`, whose widening is additive to its union and whose README row
  names only the alias. All 448 pre-existing tests pass, with three mechanical
  edits: `tests/test_sequential.py` calls the module-level `_wrap_sink()`
  instead of reaching for it through an instance, and `tests/test_sink.py` and
  `tests/test_op_protocol.py` assert on `bridge.buffer` where they had asserted
  on `bridge.drain()`. 457 tests pass at 99% coverage — 9 new, covering
  `limit(0)` on `Stream` and `ParallelStream`, that no source pull happens, the
  full `begin()`/`end()` lifecycle on a chain that pulled nothing, the
  protocol-level cancelled-at-`begin()` case against both the test double and
  the real driving loop, and the bridge's in-place clear and buffer identity.
  `sink-protocol` gained the pre-first-pull requirement; `pipeline-composition`
  gained the `limit(0)` guarantee and the no-defensive-copy invariant; the
  `_sequential()` references in `pipeline-composition` and `stream-iterator`
  were re-pointed. See `openspec/changes/batch-small-cleanups`.

- **Converted the terminal operations to real `TerminalSink`s**, closing the
  half-conversion the Sink-chain redesign explicitly scoped out. `BaseStream`
  gained `_drive_to(terminal)` — link the chain onto a terminal sink, push
  source → head → terminal, return `terminal.result()` — and
  `_drive_to_sequential(terminal)`, the never-overridden ordered form. The pair
  mirrors the existing `_compose()`/`_drive()` split: `_drive_to()` dispatches
  (`ParallelStream` overrides it), `_drive_to_sequential()` stays ordered on
  either subclass. A new `src/snakestream/terminals.py` (206 lines) holds seven
  terminal sinks — `_CountSink`, `_ForEachSink`, `_ReduceSink`, `_MinMaxSink`,
  `_MutableReductionSink`, `_FindSink`, `_MatchSink` — plus `_UNSET`, which
  moved out of `stream.py` since a sink cannot import it back. Every terminal
  method in `stream.py` is now one or two lines; `stream.py` went from 215
  statements to 111.

  `_drive()`/`GeneratorBridgeSink` were kept for exactly what needs a
  generator, as scoped: `iterator()`, `collect(collector)` (so `to_array()` and
  every collector are untouched), `_concat`, the `sequential()`/`parallel()`
  handoff, and `flat_map`'s inner-stream composition. No terminal reaches the
  bridge any more, and the `TerminalSink` seat now has six real occupants that
  use `_create_container`/`_finish`/`result()` as intended rather than
  overriding them — which is the template the **Next**-bucket `Collector`
  redesign needed, and which it is now **unblocked** by.

  **Two behavior changes, both intended, neither breaking.** (a) Short-circuiting
  terminals now report `cancellation_requested()`, so a settled `any_match` /
  `all_match` / `none_match` / `find_first` / `find_any` stops the whole chain
  instead of abandoning a generator: `.peek(fn).any_match(p)` calls `fn` once,
  not once per element, and `.flat_map(m).find_first()` takes one element from
  the first inner stream and closes it rather than draining it. A user relying
  on a side-effecting `peek()` or mapper firing past the short-circuit point
  would see the difference — it is the same class of fix `limit()` got, so it is
  a behavior note rather than a **BREAKING** migration-log entry; no signature
  or return value changed. (b) `ParallelStream` terminals gained cancellation at
  the outer loop only.

  **`ParallelStream` drives the terminal over the racing generator** rather than
  sharing one terminal sink across the branches: `_drive_to()` is overridden to
  push `_compose()`'s output into the single terminal. Parallel semantics are
  therefore identical to before and the bridge's cost stays on that path — the
  measured win is sequential-only. Sharing a terminal across branches was
  rejected: it would make `begin()`/`end()` refcounted, the accumulator
  concurrently mutated, and would need `_ReduceSink`/`_MinMaxSink` to define a
  merge across partitions, which is exactly the `combiner` work parked in
  **Later** behind real partitioned execution. Consequence, accepted: an
  in-flight branch's own `_LimitSink`/`_FlatMapSink` never sees a terminal's
  cancellation, since the terminal is not in that branch's chain. `_parallel()`'s
  existing `finally:` already cancels and gathers the pending tasks, so teardown
  is clean — a missed optimization, not a correctness gap.

  **One defect found by the new tests, and one fix beyond the planned scope.**
  `_FindSink.accept()` initially overwrote its container on every element, which
  is correct only if nothing pushes after cancellation — but `_SortedSink.end()`
  flushes its entire buffer downstream in one go with no driving loop in
  between, so `.sorted().find_first()` returned the *last* element. Fixed by
  guarding both short-circuiting sinks to ignore anything pushed after they
  settle. That exposed the real gap one level up: `_SortedSink.end()` did not
  check `cancellation_requested()` while flushing, so `peek()` still fired for
  every element after the answer was known. Added that check between pushes
  (`ops.py`), mirroring `_FlatMapSink`'s existing inner-loop check — two lines,
  outside the change's planned task list, but without it the change's headline
  benefit has a hole for any chain containing `sorted()`. The terminal-side
  guards were kept rather than resting on that invariant and are pinned by
  direct sink-level tests.

  **Benchmark (2026-08-19, same harness: Python 3.14.5, 20,000 elements, chain
  of 8 `.map()` ops, best of 5, three interleaved rounds per condition via
  `git stash`; best round per condition shown, round 1 was a cold outlier for
  both):**

  | Scenario | Before | After | Δ |
  |---|---|---|---|
  | `collect(to_list)` — unchanged generator path, control | 1974.3 | 2004.7 | ~flat |
  | `count()` | 1938.5 | 1644.3 | **−15.2%** |
  | `for_each()` | 1982.4 | 1622.9 | **−18.1%** |
  | `reduce()` | 1994.1 | 1671.6 | **−16.2%** |

  The flat control on the generator path is what rules out machine drift: only
  the paths that stopped round-tripping through the bridge moved. This recovers
  a good part of what the redesign measured and gave back to the buffer-and-yield
  step, as that item predicted.

  No public API change — every name added is private and unexported, so README
  needed no parity-table or migration-log edit. All 421 pre-existing tests pass
  **unmodified**, which was the primary regression signal; 27 new tests were
  added (`tests/test_terminal_sinks.py`, plus two protocol-level cases in
  `tests/test_sink.py`) covering `reduce()`'s reseeding edge cases, terminal
  cancellation reaching `peek`/`limit`/`flat_map`, the ordered drive on a
  `ParallelStream`, parallel terminals, and the two short-circuit guards. 448
  tests pass at 99% coverage (98.63% branch), `terminals.py` at 100%. New
  `terminal-sinks` spec; `sink-protocol` and `pipeline-composition` extended for
  terminal-originated cancellation. See
  `openspec/changes/convert-terminals-to-sinks`.

- **Split the op/sink definitions out of `stream.py` into `ops.py`.** The eight
  op/sink pairs (`_FilterSink`/`_FilterOp` through `_SkipSink`/`_SkipOp`) moved
  verbatim into a new `src/snakestream/ops.py`, leaving `stream.py` as the public
  `Stream` API plus `PROCESSES`, `_UNSET` and `_concat`. `stream.py` went from
  485 to 312 lines; `ops.py` is 199. The class bodies are byte-identical to what
  they were in `stream.py` — verified by diffing the moved block against the
  original lines before deleting them — so the whole change is the cut, the new
  module's import header, and one import line in `stream.py`.

  Sinks moved with their ops rather than staying behind: after the op-collapse
  change each op is a two-to-four-line `_sink_cls = <its sink>` declaration, so
  the pair is only readable together. The ops were not folded into `sink.py`
  either — that file is the protocol (`Sink`, `Op`, `IntermediateSink`,
  `TerminalSink`, `StatelessOp`/`StatefulOp`, `GeneratorBridgeSink`), and mixing
  the concrete ops into it would re-create the same two-concerns-in-one-file
  problem one module over.

  No import cycle: `ops.py` imports from `sink.py`, `sort.py`,
  `callable_dispatch.py` and `type.py` only. `_FlatMapSink` is the one op that
  touches a `Stream`, and it does so purely by duck typing
  (`self._flat_mapper(element)._compose()`); its `FlatMapper` annotation resolves
  through `type.py`'s existing `TYPE_CHECKING` guard, so no guard was needed in
  `ops.py`. `stream.py` shed `aclosing`, `merge_sort` and all seven `sink.py`
  imports in the cut, keeping `check_comparator_result_type`, `is_async_callable`
  and `isawaitable`, which the `Stream` API still uses.

  Behavior-neutral, and no spec or README edit was needed: every moved name is
  private and unexported, so no public API surface changed and neither
  `sink-protocol` nor `pipeline-composition` describes which module the concrete
  ops live in (they describe the protocol classes in `sink.py`). The change
  therefore declared `skip_specs: true` and shipped no spec delta. The only test
  edit was `tests/test_op_protocol.py`'s import of the eight op classes moving to
  `snakestream.ops`; `tests/test_sequential.py` and `tests/test_sink.py` define
  their doubles against `sink.py` and needed no change. 421 tests pass at 99%
  coverage — identical to the pre-change run, with `ops.py` at 100%. The **Small
  cleanups** item's `stream.py` line references were re-pointed to their new
  lines. See
  `openspec/changes/archive/2026-08-19-split-ops-into-ops-module`.

- **Collapsed the eight op classes onto shared bases.** `sink.py` gained
  `StatelessOp` and `StatefulOp` — both storing the arguments the op was
  constructed with and forwarding them to a class-level `_sink_cls`, the
  stateful one also passing `self` so its sink can key the state map — plus a
  `StatefulSink` base and a `Counter` value type. All eight ops are now
  declarations: five are two lines (`class _MapOp(StatelessOp): _sink_cls =
  _MapSink`), three add a one-line `make_shared_state()`. `stream.py` went from
  537 to 485 lines and `_DistinctSink`/`_LimitSink`/`_SkipSink` lost their
  hand-written `begin()` overrides.

  The state-map lookup written out at three sites became one `state_map.get()`
  in `StatefulSink.begin()`, and its fallback now comes from the op's own
  `make_shared_state()` rather than a literal retyped in the sink — so an op's
  state shape is stated exactly once and shared and local state cannot drift.
  That guarantee was added to the `sink-protocol` spec as a new scenario under
  **Shared state is delivered through begin**, the change's only spec delta.
  `_LimitSink._count: list[int]` and `_SkipSink._skipped: list[int]` became a
  `Counter` with a `value` attribute, so the reserve-before-await race block
  now reads `self._state.value >= self._max_size`.

  Naming follows Java's `StatelessOp`/`StatefulOp`, with the class docstrings
  pinning that the axis here is *shared* state — state crossing
  `ParallelStream`'s branches — not local buffering, which is why the
  whole-stream-buffering `_SortedOp` is a `StatelessOp`.

  Behavior-neutral and no public API change; every name touched is private or
  unexported, so README needed no edit. `parallel_stream.py` needed no edit
  either — it already called `make_shared_state()` unconditionally and keyed
  only non-`None` results. 421 tests pass at 99% coverage (six new: the
  factory-sourced fallback, `Counter` independence, shared-counter increment
  across two sinks from one op, and argument forwarding through both bases).
  Two existing tests were touched: `test_op_protocol.py`'s fresh-container
  assertion asserted emptiness as `first in ([0], set())`, which named the old
  list representation, and two test-local doubles (`_StatelessOp`,
  `_StatefulOp`/`_StatefulSink`) were renamed to `_LinkOnlyOp` and
  `_TallyingOp`/`_TallyingSink` since their names now collide with the real
  protocol classes. The doubles still subclass `Op`/`IntermediateSink`
  directly, deliberately: their job is to pin the protocol, not the
  convenience bases.

  **Benchmark (2026-08-19, same harness: Python 3.14.5, 20,000 elements, best
  of 5, interleaved before/after rounds to control for machine drift):** 8×
  `.map()` 1935–2026 ns/element before, 2001–2071 after; `.skip(1).limit(n)`
  1081–1120 before, 1037–1145 after. Run-to-run spread within either condition
  (±5–8% on this WSL2 box) exceeds the gap between them, and the 8× `.map()`
  path's per-element code is byte-identical across the change — everything the
  change touches per element is the `Counter` attribute load replacing a list
  index, and everything else (`link()`, `begin()`) runs once per composition.
  No measurable regression.

  **Unblocks** the `ops.py` split still in **Now**, which is now a pure move.
  See `openspec/changes/collapse-op-classes`.

- **Introduced an `Op` ABC** (`sink.py`) and typed the chain against it,
  completing the op/sink protocol the Sink-chain redesign left half-specified.
  `Op` has one abstract member, `link(downstream) -> Sink`, and one concrete
  `make_shared_state() -> Any` returning `None`; all eight shipped ops
  (`_FilterOp`, `_MapOp`, `_PeekOp`, `_SortedOp`, `_FlatMapOp`, `_DistinctOp`,
  `_LimitOp`, `_SkipOp`) now subclass it, the three stateful ones keeping their
  `make_shared_state()` overrides unchanged.

  `_chain`, `_derive`, `_sequential`, `_drive` and `ParallelStream._parallel`
  are typed `list[Op]` instead of `list[Any]`, so `ty` — gated in CI on the
  3.14 leg — can now see the pipeline's central data structure. The
  `getattr(op, "make_shared_state", None)` sniff in `parallel_stream.py` is
  gone, replaced by an unconditional call keying the state map only on a
  non-`None` result; `None` is now a specified contract meaning "no shared
  state", so a stateful op returns a container and never `None`.

  Behavior-neutral by construction: no method body was edited and no public API
  changed (`Op` is not exported, and all eight op classes stay private), so
  README's parity tables need no edit. 415 tests pass at 98.58% coverage. The
  existing op test doubles in `tests/test_sink.py` and `tests/test_sequential.py`
  were made to subclass `Op` so they stay faithful to the protocol. See
  `openspec/changes/archive/2026-08-19-introduce-op-abc`.

  **Unblocks** the op-class-collapse item still in **Now** — the shared
  `*args`/`_sink_cls` base that item wants now has a typed base class to hang
  off, and the `StatefulSink` base it also wants can rely on every op having a
  `make_shared_state()` to key against.

- **Investigated and rejected** replacing `callable_dispatch.py`'s hand-copied
  async-dispatch pattern with a `CallSite` object. The pattern is genuinely
  duplicated — `callable_dispatch.py` documents a 6-line shape as a 40-line
  comment and 24 per-element sites across `stream.py`, `collector.py` and
  `sort.py` retype it by hand, with `_classify_step` existing only to relieve
  mccabe pressure in `to_map`/`reducing` and `sort.py` carrying the same state
  as a positionally-indexed `state = [is_async, checked]` list. The proposal
  was to wrap each callable in a small object owning that state.

  Killed on measurement, at the benchmark gate the change's own tasks placed
  after converting a single site. Harness matched the one
  `optimize-callable-dispatch` and `redesign-pipeline-sink-chain` used (Python
  3.14.5, 20,000 elements, chain of 8 `.map()` ops, best of 5, three runs per
  variant); only `_MapSink` was converted, so with 8 `.map()` ops the figures
  isolate per-site, per-element cost:

  | Variant | ns/element | vs baseline |
  |---|---|---|
  | Baseline (inline shape, as shipped) | 1907, 1992, 2162 | — |
  | Floor (dispatch logic deleted; sync-only, incorrect) | 1826, 1878, 1998 | ~0% |
  | `CallSite.call()` sync, caller branches on `.is_async` | 2529, 2589, 2840 | **+32%** |
  | `CallSite` with `async def __call__` | 3399, 3444, 3468 | **+75%** |

  The decisive figure is the floor: deleting the dispatch logic outright buys
  nothing measurable over the baseline, so the inline five-branch shape costs
  approximately zero — two attribute loads and two branches the CPU predicts
  correctly after the first element, with no Python-level call and no
  allocation. The comparison is therefore not "abstraction vs. cheaper
  abstraction" but "abstraction vs. free", and both variants pay a
  Python-level call per element per site that the inline code does not (~180
  ns/site/element for the coroutine frame, ~70 ns for the bound-method call
  alone). The design's stated fallback — a two-shape `CallSite` picking a sync
  fast path in `__init__` — does not help, since the fast path still has to be
  reached through the call that is itself the cost. `optimize-callable-dispatch`
  bought 2.6x by hoisting exactly these branches out of the per-element path;
  the two variants give back roughly half and roughly a fifth of that.

  **Consequence:** the duplication is now a deliberately-accepted cost with
  numbers behind it rather than an open cleanup item, and should not be
  re-proposed without new evidence. Anyone adding a 25th dispatch site should
  still copy the canonical-shape comment in `callable_dispatch.py` — that
  comment is load-bearing, not a smell to be refactored away. No code changed;
  the working tree was reverted to HEAD and the full suite (394 tests) passes
  unmodified. See
  `openspec/changes/archive/2026-08-18-add-callsite-dispatch` for the proposal,
  design, and `benchmark-findings.md`.

  **One residual finding was salvaged and acted on.** The investigation
  established that per-callable classification independence — `to_map`'s
  key/value/merge functions and `reducing`'s mapper/binary operator each
  classifying on their own, so any mixture of sync and async among them works
  — was real behavior with **no test coverage**: `tests/test_to_map.py` and
  `tests/test_reducing.py` each covered all-sync and all-async but never a
  mixed pair. Closed by adding the five mixed-mode tests (sync key + async
  value, async key + sync value, sync mappers + async merge on a colliding
  key, sync mapper + async operator, async mapper + sync operator) and
  promoting the rejected change's drafted delta into the `callable-dispatch`
  spec as a new **Classification state is per callable** requirement. All five
  passed on first run — the behavior was already correct, so this is coverage
  and documentation of existing behavior, not a fix. Written directly to
  `openspec/specs/callable-dispatch/spec.md` rather than through a change of
  its own, since the requirement text already existed in the rejected
  change and would otherwise have been archived away unapplied.
- Redesigned pipeline execution from nested async-generator delegation to a
  push-based `Sink` protocol (`begin(state_map)`/`accept(element)`/`end()`/
  `cancellation_requested()`), replacing the closures-in-`_chain` model. New
  `src/snakestream/sink.py` defines the protocol plus `IntermediateSink` (a
  `downstream`-holding base that propagates `begin()`/`end()` and forwards
  `cancellation_requested()`) and `TerminalSink` (creates its container in
  `begin()`, accumulates in `accept()`, exposes the finished value via
  `result()`) — the terminal seat a future `Collector` redesign can plug
  into directly. `GeneratorBridgeSink` occupies that seat to let
  `BaseStream._compose()` keep returning a plain `AsyncGenerator`: pushing
  stays entirely internal to the chain, with a buffer-and-drain driving loop
  (`BaseStream._drive()`) converting pushes back into yields, so all 11
  terminal ops, every collector, `iterator()`, and `_concat` needed no
  changes. All eight intermediate ops (`filter`, `map`, `flat_map`, `sorted`,
  `peek`, `distinct`, `limit`, `skip`) are now op/sink pairs in `stream.py`
  (`_FilterOp`/`_FilterSink`, etc.) — the op is a stateless, reusable
  descriptor exposing `link(downstream) -> Sink` (and, for stateful ops, a
  `make_shared_state()` factory), while the sink is built fresh per
  composition and holds the actual per-composition state.
  `make_state()`/`state_map` `getattr`-introspection is gone:
  `ParallelStream._parallel()` now calls each op's `make_shared_state()`
  directly to build one shared state map, passed into every racing branch's
  `begin()`. `limit()`'s short-circuit moved from the op reaching up to
  `aclose()` its own upstream to `cancellation_requested()` propagating to
  the driving loop, which now owns closing the source (via a
  `_maybe_aclosing()` helper tolerant of sources with no `aclose()`, needed
  since `_drive()` — unlike the old bare-`_stream`-passthrough on an empty
  chain — always wraps the source). `flat_map()` drops its
  `collect(to_generator)` wrapper layer, iterating the inner stream's own
  `._compose()` directly while keeping `aclosing()` around it, and checks
  `downstream.cancellation_requested()` between pushed elements so a
  downstream `.limit()` still stops it mid-inner-iteration instead of
  over-pushing.

  **Two scoping decisions taken (from `design.md`):** (a) push stays
  internal only — `_compose()` still returns an `AsyncGenerator`, avoiding
  the pull-bridge (`Spliterator`) that pushing all the way to the terminal
  would need; (b) the terminal seat ships now, with one implementation
  (`GeneratorBridgeSink`), rather than deferring it to the Collector
  redesign.

  **Benchmark (2026-08-18, this repo's dev environment, Python 3.14.5,
  20,000 elements, chain of 8 `.map()` ops, best of 5):** 2,480.6 ns/element
  before, 1,872.6 ns/element after — a ~24.5% gain, consistent with (and
  better than) the proposal's 15–17% estimate; the bridge's buffer-and-yield
  step gives back some but not all of the fully-pushed-to-terminal figure
  the proposal separately measured.

  The entire pre-existing test suite passed unmodified except one
  internals-facing test (`test_sequential_long_chain_does_not_recurse_at_
  build_time`) updated to construct fake ops with `.link()` instead of raw
  closures, since `_sequential()`'s signature is now `(intermediaries,
  terminal_sink) -> Sink` rather than `(intermediaries, iterable) ->
  AsyncGenerator` — an intentional, documented signature change, not a
  behavior regression. Added `tests/test_sink.py` covering the
  `sink-protocol` spec directly (lifecycle ordering, empty source, zero/one/
  many pushes per accept, pushing from `end()`, state-map lookup/fallback/
  sharing, cancellation propagation, terminal `result()`). Added a direct
  `to_generator()`-with-no-`aclose()`-source test (`tests/test_collect.py`)
  to keep that branch covered, since `_compose()` no longer ever returns a
  bare source without `aclose()` the way the old empty-chain passthrough
  did. New `sink-protocol` spec; `pipeline-composition` updated to describe
  state and cancellation via `begin(state_map)`/`cancellation_requested()`
  instead of the old `make_state()`/`state_map` convention and `limit()`'s
  self-closing upstream. No public API change; `collector.py` untouched.
  See `openspec/changes/redesign-pipeline-sink-chain`.
- Added `sorted()`'s row to README's Stream API table. `sorted()` had been
  implemented since before this roadmap existed (`stream.py:191`) but was
  never given a row in the table; the migration log referenced it three
  times, which is what made the omission easy to miss. Doc-only, no code
  change.
- Specialized `callable_dispatch.py`'s dispatch from per-result to
  per-callable: `is_async_callable(fn)` classifies a callable once
  (recognizing a plain `async def` function and a callable object whose
  `__call__` is `async def`), and the 26 per-element call sites across
  `stream.py`, `collector.py` and `sort.py` hoist an `is_async` flag out of
  their loop instead of calling `inspect.isawaitable` on every result.
  A first-invocation `isawaitable` check is kept as a safety net so a
  sync-signatured callable that returns a coroutine (the defect
  `add-maybe-await-helper` fixed) is still handled correctly. `_maybe_await`
  is retained for the handful of call sites invoked once per composition
  (e.g. `collect()`'s `supplier`), where specialization buys nothing.
  Measured in this repo's dev environment (Python 3.14.5, 20,000 elements,
  a chain of 8 `.map()` ops, best of 5 runs): 5,949 ns/element before,
  2,247 ns/element after — a 2.6x speedup, in line with the throwaway
  benchmark harness's 5,775 → 2,064 ns/element (2.8x) recorded in
  `design.md`. Carries one deliberate contract narrowing, tracked as
  **BREAKING** in README's migration log: a callable invoked once per
  element must be consistently sync or consistently async — one that
  returns an awaitable for some elements and a plain value for others is no
  longer supported (it has no Java analogue). See
  `openspec/changes/optimize-callable-dispatch`.
- Decided and implemented the mutable-builder vs. immutable-pipeline
  question (the former top **Next**-bucket item, previously "Decide
  mutable-builder vs. immutable-pipeline semantics"). Explored three
  positions during a design session: (A) keep mutate-and-return-self and
  just document the aliasing risk; (B) copy-on-write with the old
  reference left silently usable (superficially "forkable," but still a
  footgun since the underlying `self._stream` is single-pass, so both
  forks would race it exactly like `ParallelStream` branches do); (C)
  Java-exact — new instance plus invalidating the old reference on reuse.
  Landed on a scoped version of (C): every intermediate op (`map`,
  `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) and
  both mode switches (`sequential()`, `parallel()`) now return a **new**
  `Stream`/`ParallelStream` instance via a new `BaseStream._derive()`
  helper (`base_stream.py`) instead of mutating and returning `self`;
  using an already-superseded old reference for any further
  pipeline-building or terminal call now raises a new
  `IllegalStateException` (`exception.py`), checked via a
  `self._consumed` flag set only by the ops that build a new instance.
  Deliberately did **not** go full Java-exact: terminal ops
  (`collect`, `reduce`, `for_each`, etc.) check `self._consumed` but never
  set it, so repeating a terminal op on a reference that was never used to
  build a further instance keeps today's exact behavior (an exhausted
  source yields an empty result rather than raising) — reversing that
  would have undone the already-shipped, tested `fix-stream-rerun-state`
  contract that `pipeline-composition` documents, which was judged a
  separate, already-settled decision this change shouldn't revisit.
  `on_close()`/`close()` were kept completely exempt from the new check,
  matching how Java itself tracks close handlers at the pipeline's source
  stage rather than per operation, independent of any per-op immutability
  question. Discovered during implementation: `BaseStream.__init__`'s
  `self._close_handlers = close_handlers or []` treated an *empty* list as
  falsy and silently created a new list instead of keeping the passed-in
  reference — invisible before since intermediate ops never re-invoked the
  constructor, but every op does now via `_derive()`, breaking
  close-handler continuity across the very first op called before any
  `on_close()`. Fixed to `[] if close_handlers is None else close_handlers`.
  Added `tests/test_pipeline_immutability.py`: new-instance-per-op checks
  and invalidation-raises checks for all 8 intermediate ops, invalidation
  checks across all terminal ops and both mode switches, derived-instance
  usability, the unextended-reference non-regression case, and the
  `on_close()`/`close()` exemption. Added a new `pipeline-immutability`
  spec. Updated README's migration log (**BREAKING**). See
  `openspec/changes/make-stream-ops-immutable`.
- Implemented `Stream.find_first()` (`stream.py`), matching Java's
  `Stream.findFirst()`. The previous body was a dead
  docstring-commented-out stub — a string literal, never executed — with a
  comment claiming it was blocked on "ordered parallel stream." That
  blocker didn't actually apply to `Stream`: `Stream._compose()` is already
  sequential, so `find_first()` there is identical in body to `find_any()`.
  The real gap was narrower and `ParallelStream`-specific:
  `ParallelStream._compose()` races `PROCESSES` branches via
  `asyncio.wait(..., FIRST_COMPLETED)`, so first-*arrival* isn't
  first-*encounter-order*. Fixed by adding a `ParallelStream.find_first()`
  override that checks `self.is_ordered()`: when ordered (the default),
  pulls via `self._sequential(self._chain[:], self._stream)` — the same
  building block `for_each_ordered()` uses — for a strictly ordered,
  single-flight pull through the chain, guaranteeing the true first element
  in encounter order at the cost of `.parallel()`'s concurrency for this
  one terminal call (the same trade-off Java's own `forEachOrdered()`/
  ordered `findFirst()` make); when the stream has been marked
  `unordered()`, delegates to `find_any()`'s existing racing behavior,
  matching Java's documented relaxation of `findFirst()`'s encounter-order
  guarantee for unordered streams. This is the first consumer of the
  `is_ordered()`/`unordered()` flag added by `add-stream-unordered`. Added
  `tests/test_find_first.py`: non-empty/empty `Stream`,
  first-element-only pulled, and — mirroring `test_for_each_ordered.py`'s
  jumbled-source-with-positional-delay pattern — ordered-`ParallelStream`
  coverage proving `find_first()` returns the true first element rather
  than the first to arrive, plus unordered-`ParallelStream` coverage
  showing it races without waiting for a full ordered pull. Updated
  README's parity table (`find_first()` row, previously "Not implemented
  yet"). No breaking changes. See
  `openspec/changes/add-stream-find-first`.
- Fixed three resource/lifecycle defects found in review: (a) `flat_map()`
  (`stream.py`) leaked the current inner stream's async generator when the
  outer chain short-circuited (e.g. a downstream `.limit()`) — each outer
  element's fresh `flat_mapper(i).collect(to_generator)` generator was only
  ever exhausted, never explicitly `.aclose()`'d, so an early `GeneratorExit`
  on the outer chain abandoned whatever inner generator was mid-iteration.
  Fixed by wrapping that inner generator in `contextlib.aclosing()`
  (`stream.py`). Discovered during implementation: `aclosing()` alone wasn't
  sufficient — `collect(to_generator)` returns a second-layer wrapper
  generator (`collector.py`'s `to_generator()`) whose `async for n in
  composition: yield n` body didn't propagate `.aclose()` to `composition`
  either, confirmed with a minimal repro showing a plain `async for` never
  auto-closes what it iterates. Fixed `to_generator()` to also wrap
  `composition` in `aclosing()`, guarded by `hasattr(composition, "aclose")`
  since `to_generator()` also accepts plain `AsyncIterable`/`AsyncIterator`
  objects without an `aclose` method (e.g. a custom `__anext__`-only
  iterator, already covered by `tests/test_of.py::test_input_async_iterator`).
  This closes the gap only as deep as `flat_map()`'s stated repro case (a
  single-level inner stream); N-layers-deep propagation across every op in
  `stream.py` remains out of scope, tracked under the **Next**-bucket
  Sink-chain redesign item. (b) `BaseStream.close()` (`base_stream.py`)
  iterated `_close_handlers` with a plain `for` loop and no `try`/`except`,
  so a raising handler stopped every handler after it from running, unlike
  Java's try-with-resources convention of running every closer regardless.
  Fixed by calling every handler inside a per-handler `try`/`except
  Exception`, collecting failures, then raising the first captured exception
  once every handler has run (not an `ExceptionGroup`, since this project's
  CI matrix still targets Python 3.10). (c) `StreamBuilder.build()`
  (`stream_builder.py`) passed `self._elements` into `Stream(...)` by
  reference rather than snapshotting it, so `add()`/`accept()` calls made
  *after* `build()` leaked into the already-built stream. Fixed by
  snapshotting via `list(self._elements)`. Added regression tests in
  `tests/test_close.py`, `tests/test_flat_map.py`, and a new
  `tests/test_stream_builder.py`. Added a new `stream-builder` spec
  capturing `StreamBuilder`'s previously-undocumented `add()`/`accept()`/
  `build()` contract, and extended `stream-close-handling` and
  `pipeline-composition` for the `close()`/`flat_map()` fixes. Updated
  README's migration log: `StreamBuilder.build()`'s snapshot behavior is
  tracked as **BREAKING** per `CLAUDE.md`'s convention (relying on
  post-build mutation leaking into a built stream was never a documented
  feature). See `openspec/changes/fix-resource-lifecycle-defects`.
- Fixed three `type.py` callable-alias defects found in review: (a)
  `Mapper = Callable[[T], R | None]` now includes `Awaitable[R | None]`,
  matching `Predicate`/`Comparator`'s existing sync-or-async pattern and
  `map()`'s actual `_maybe_await`-based dispatch, which already supported
  async mappers without the type declaring it; (b) `Consumer` changed from
  `Callable[[T], T]` (wrong return type — a consumer's return value is
  discarded, not a `T`) to `Callable[[T], None | Awaitable[None]]`, and
  `for_each()`/`for_each_ordered()` (`stream.py`), which previously inlined
  their own `Callable[[T], Any]` instead of using the alias, now use
  `Consumer[T]`; (c) deleted `Filterer = Callable[[T], T]`, dead code never
  referenced anywhere in `src/` (`filter()` uses `Predicate`). Both alias
  widenings are additive to their unions, so no previously-valid sync usage
  is affected. Typing-only change, no runtime behavior differs. See
  `openspec/changes/fix-type-py-callable-alias-defects`.
- Added `groupingBy(classifier, [downstream])` / `partitioningBy(predicate,
  [downstream])`, implemented as `grouping_by`/`partitioning_by`
  (`collector.py`) — `collector.py`'s equivalent of `Collectors.groupingBy`/
  `partitioningBy`, closing out the roadmap's `Collectors`-parity effort.
  Both bucket elements first (`grouping_by` via a `classifier` mapper into a
  `dict[R, list[T]]`; `partitioning_by` via a `predicate` into a fixed
  `{True: [...], False: [...]}`, always populating both keys even when one
  partition is empty, matching Java's `Collectors.partitioningBy` exactly)
  then re-drives each bucket's elements through an optional `downstream`
  collector (default `to_list`) via a small `_generator_of(items)` helper
  that re-wraps the buffered list as a fresh `AsyncGenerator`, since
  downstream collectors are written to consume a composition, not a plain
  list — enabling `grouping_by(classifier, counting())`-style composition
  immediately, without downstream collectors needing to know they're being
  reused this way. `grouping_by`'s `classifier` and `partitioning_by`'s
  `predicate` reuse the same sync/async dispatch (`_maybe_await`) as every
  other collector. Added `tests/test_grouping_by.py`,
  `tests/test_partitioning_by.py`. Updated README's `Collectors` table with
  two new rows. No breaking changes. See
  `openspec/changes/archive/2026-08-18-add-collectors-groupingby-partitioningby`.
- Added `toMap(keyMapper, valueMapper, [mergeFunction])` / `toSet()`,
  implemented as `to_map`/`to_set` (`collector.py`) — structural collectors
  materializing into a `dict`/`set` instead of `to_list`'s `list`, matching
  `Collectors.toMap`/`Collectors.toSet`. `to_map` maps each element to a
  key/value pair via `key_mapper`/`value_mapper` (sync or async, dispatched
  through `_maybe_await`); a duplicate key raises `ValueError` unless a
  `merge_function` is given, in which case the collision resolves via
  `merge_function(existing, new)`, matching Java's
  `toMap(keyMapper, valueMapper, mergeFunction)` overload. `to_set()` takes
  no arguments and simply collects into a `set`, deduplicating via
  element `__hash__`/`__eq__` same as Java's `HashSet`-backed collector.
  Added `tests/test_to_map.py`, `tests/test_to_set.py`. Updated README's
  `Collectors` table with two new rows. No breaking changes. See
  `openspec/changes/archive/2026-08-18-add-collectors-tomap-toset`.
- Added `min_by(comparator)`, `max_by(comparator)`, and `reducing(...)`
  (`collector.py`) — collector wrappers around `Stream.min`/`max`/`reduce`'s
  already-implemented logic, exposed as `collect()`-compatible collectors
  rather than terminal-op methods, matching Java's `Collectors.minBy`/
  `maxBy`/`reducing` (adapted to this project's existing snake_case naming
  convention, e.g. `for_each`/`to_array`/`summing_int`, not literal Java
  camelCase). `min_by`/`max_by` reuse `check_comparator_result_type`
  (`sort.py`) and mirror `Stream._min_max`'s tie-break (first of equal
  elements wins) and `None`-on-empty-stream behavior exactly. `reducing`
  implements all three Java overload shapes — `reducing(binary_operator)`
  (no identity, mirrors `Stream.reduce(accumulator)`),
  `reducing(identity, binary_operator)` (mirrors
  `Stream.reduce(identity, accumulator)`), and
  `reducing(identity, mapper, binary_operator)` (maps each element before
  folding, argument order matching Java's
  `reducing(U identity, Function<T,U> mapper, BinaryOperator<U> op)`
  exactly) — dispatched via `@overload` + a runtime `_UNSET` sentinel, the
  same pattern `Stream.reduce` already uses. The loop bodies are
  intentionally duplicated from `Stream._min_max`/`reduce` rather than
  retrofitting those methods to accept an arbitrary `AsyncGenerator`, since
  a collector's contract has no `Stream` instance in scope and the loops are
  short and stable; `check_comparator_result_type` stays imported from
  `sort.py` as the single source of truth for the one piece of real shared
  logic. Discovered during implementation: the three `reducing` `@overload`
  stub bodies pushed combined branch coverage below the repo's 98% gate
  (each unreachable `def ...: ...` stub counts as a never-taken branch);
  fixed with `# pragma: no cover` on each stub line, an already-supported
  `exclude_lines` pattern in `pyproject.toml` — no config change needed.
  Added `tests/test_min_by.py`, `tests/test_max_by.py`,
  `tests/test_reducing.py`: extremum selection, empty-stream `None`,
  tie-break, async comparator/mapper/operator awaiting, `TypeError` on a
  bool-returning comparator, and all three `reducing` overloads including
  empty-stream/single-element edge cases. Updated README's `Collectors`
  table with three new rows. No breaking changes. See
  `openspec/changes/archive/2026-08-17-add-collectors-minby-maxby-reducing`.
- Added `counting()`, `summing_int`/`summing_long`/`summing_double`, and
  `averaging_int`/`averaging_long`/`averaging_double` (`collector.py`) —
  numeric reducing collectors, `collector.py`'s equivalent of the matching
  `Collectors` statics, following the same factory-returns-closure shape
  `joining()` established. `counting()` returns the `int` element count;
  `summing_int`/`summing_long`/`summing_double` map each element then sum
  the results (`int` for the first two, `float` for the last);
  `averaging_int`/`averaging_long`/`averaging_double` map each element and
  return the arithmetic mean as a `float` (`0.0` for an empty stream).
  Java's `Collectors` distinguishes `summingInt`/`summingLong`/
  `summingDouble` and the `averaging*` trio by primitive type — a
  distinction Python's numeric tower doesn't have — so each pair/trio is
  implemented identically apart from `summing_double`'s explicit `float()`
  coercion; kept as separate, Java-parity-named functions rather than
  collapsing to `summing(mapper)`/`averaging(mapper)`, since these are
  distinct Java method names (not one overloaded method, unlike `joining()`'s
  three arg-count variants). Added a new `NumberMapper` type alias to
  `type.py`. Mapper dispatch reuses the existing `_maybe_await` helper, so
  sync and async mappers both work. Added `tests/test_counting.py`,
  `tests/test_summing.py`, `tests/test_averaging.py`: non-empty/empty
  streams and sync/async mappers for each function, plus a `float`-type
  assertion for `summing_double`. Updated README's `Collectors` table with
  seven new rows. No breaking changes. See
  `openspec/changes/add-collectors-counting-summing-averaging`.
- Added `joining()` / `joining(delimiter)` / `joining(delimiter, prefix,
  suffix)` (`collector.py`) — a string-concatenation collector for use with
  `Stream.collect()`, `collector.py`'s equivalent of `Collectors.joining`
  and the first entry in the `Collectors`-parity effort tracked by this
  roadmap. Implemented as a single `joining(delimiter: str = "", prefix:
  str = "", suffix: str = "")` factory function, collapsing Java's three
  overloads into default arguments rather than `@overload`s, since the
  underlying behavior doesn't actually branch by argument count (contrast
  with `collect()`'s two genuinely different code paths, which do use
  `@overload`). It returns a plain `async def` closure over the composed
  `AsyncGenerator[str, None]`, matching `collector.py`'s existing
  plain-function collector shape (`to_list`/`to_generator`) rather than a
  callable class — no per-composition state is needed since
  prefix/delimiter/suffix are fixed at factory-call time. The join uses
  `delimiter.join(parts)`, so a non-`str` element naturally raises
  `TypeError` (matching Java's `Collectors.joining()`, defined only on
  `Stream<CharSequence>`) with no explicit `isinstance` check needed; an
  empty stream returns `prefix + suffix`, matching Java's Javadoc exactly.
  Added a new `Collectors` table section to README (none existed yet) to
  give this and future `Collectors`-family additions a place to be
  tracked. Added `tests/test_joining.py`: no-arg join, delimiter-only,
  delimiter+prefix+suffix, single-element (no delimiter applied), empty
  stream with and without prefix/suffix, and the `TypeError` regression for
  a non-`str` element. No breaking changes. See
  `openspec/changes/add-collector-joining`.
- Added `Stream.to_array()` (`stream.py`) — a terminal operation returning a
  `list` of every element pulled through the composed chain, functionally
  identical to `collect(to_list)`. Java's `toArray()`/`toArray(generator)`
  exist because arrays are a distinct, reified type from `List` and Java has
  no runtime generic-array construction; neither motivation applies to
  Python, where `list` is already the general-purpose ordered collection, so
  only the no-arg form was added — implemented as `to_array()` (snake_case),
  matching every other Java-name adaptation already in the class
  (`for_each`, `find_any`, `flat_map`), not the literal Java casing. The
  `toArray(generator)` overload was decided against and is documented in
  README as intentionally skipped rather than tracked as future work. Added
  `tests/test_to_array.py`: non-empty and empty streams, equivalence with
  `collect(to_list)`, `ParallelStream` coverage, and a `TypeError` regression
  for calling it with an argument. Updated README's parity table and
  removed the item from its "Left to do" list. No breaking changes. See
  `openspec/changes/add-stream-toarray`.
- Added `Stream.collect(supplier, accumulator, combiner)` (`stream.py`) —
  Java's 3-arg mutable-reduction overload of `collect()`, alongside the
  existing single-arg `collect(collector)` form. Implemented as an
  `@overload` pair dispatching on arg count, mirroring the precedent already
  set by `reduce()`'s identity/no-identity overloads: `supplier` is called
  once with no arguments to produce a fresh mutable container, `accumulator`
  is called once per pulled element as `accumulator(container, element)`,
  and both may be sync or async, dispatched via the existing `_maybe_await`
  helper. `combiner` is accepted for signature parity with Java but is
  never invoked — `collect()`, like the already-shipped `reduce()`, always
  folds over a single composed `AsyncGenerator` (sequential or parallel)
  with no independently-accumulated partitions to merge, so wiring up a real
  combine step is tracked separately in **Later** below, alongside the
  `.parallel()`/`PROCESSES` semantics decision it's blocked on. Added new
  `Supplier`/`BiConsumer` type aliases to `type.py`. Added 5 new tests in
  `tests/test_collect.py`: sync and async supplier/accumulator, an empty
  stream, and `combiner`-never-called coverage for both sequential `Stream`
  and `ParallelStream`. Updated README's parity table. No breaking changes.
  See `openspec/changes/archive/2026-08-17-add-collect-supplier-accumulator-combiner`.
- Added `Stream.for_each_ordered(consumer)` (`stream.py`) — an ordered variant
  of `for_each()`, invoking `consumer` in the stream's encounter order even
  when called on a `ParallelStream` instance, matching Java's
  `Stream.forEachOrdered()`. `for_each()` drives consumption via
  `self._compose()`, which `ParallelStream` overrides to fan the chain out
  across racing branches with no order guarantee; `for_each_ordered()`
  instead drives consumption via `self._sequential(self._chain[:],
  self._stream)` directly — the same building block `Stream._compose()`
  already uses — so it gets a strictly ordered, single-flight pull through
  the chain regardless of which subclass `self` is. This intentionally
  forfeits `.parallel()`'s concurrency for that one terminal call, the same
  trade-off Java's own `forEachOrdered()` makes on a parallel stream. The
  existing `BaseStream._ordered`/`unordered()` flag (see below) is not
  consumed here — every snakestream source has a real underlying order, and
  Java's own `forEachOrdered()` Javadoc ties the "if the stream has one"
  caveat to streams with no defined encounter order to begin with, which
  `unordered()` doesn't currently model. `for_each()`'s existing behavior is
  unchanged. Added `tests/test_for_each_ordered.py`: ordered/async-consumer
  coverage on sequential `Stream`, plus a same-chain-and-timing pair of
  parallel tests using a jumbled source and a positional (not value-based)
  per-element delay in a `.map()` step — one showing plain `for_each()` on a
  `ParallelStream` can come out scrambled under that reordering pressure, the
  other showing `for_each_ordered()` on the identical chain stays in source
  order. See `openspec/changes/add-stream-foreach-ordered`.
- Removed duplicate `_close_handlers` initialization. `BaseStream.__init__`
  (`base_stream.py`) always set `self._close_handlers = []`, but both
  `Stream.__init__` (`stream.py`) and `ParallelStream.__init__`
  (`parallel_stream.py`) immediately overwrote it with
  `close_handlers or []` right after `super().__init__(source)`, making the
  base assignment dead code on every instantiation. Fixed by giving
  `BaseStream.__init__` a `close_handlers` parameter and having it perform
  `self._close_handlers = close_handlers or []` directly; `Stream`/
  `ParallelStream` now just forward their own `close_handlers` argument via
  `super().__init__(source, close_handlers)` instead of reassigning the
  field themselves. No change to `on_close()`/`close()` or any observable
  behavior. Added a new `stream-close-handling` spec capturing the
  previously-undocumented `on_close()`/`close()`/construction/mode-switch
  contract, and new tests in `tests/test_close.py` covering scenarios not
  already exercised: registration order preserved across multiple
  `on_close()` calls, `close()` as a no-op with zero handlers registered,
  `Stream(source, [handler])` construction invoking the handler, and close
  handlers surviving a `.sequential()` switch (a `.parallel()` switch was
  already covered). See
  `openspec/changes/remove-duplicate-close-handlers-init`.
- Rewrote `BaseStream._sequential()` (`base_stream.py`) from recursion +
  `list.pop(0)` to an iterative loop over the queued closures. The old
  implementation recursed once per chained intermediate operation and
  popped from the front of the list on each call, giving O(n) Python stack
  depth (risking `RecursionError` on a long `.map()/.filter()/...` chain)
  and O(n²) time (since `list.pop(0)` is itself O(n), called n times) for a
  chain of n ops. Fixed by iterating the closures in order with a plain
  `for` loop and threading `iterable` through each step, dropping the
  `pop(0)` entirely — `_compose()` (`_sequential()`'s only caller) needed
  no changes since it already passes a fresh list copy. No change to
  `_sequential()`'s signature, return value, or `state_map` per-closure
  state lookup. Added `test_sequential_long_chain_does_not_recurse_at_build_time`
  (`tests/test_sequential.py`), calling `_sequential()` directly with a
  chain of `sys.getrecursionlimit() * 2` identity closures to isolate the
  build-time traversal this fix addresses.

  **Scope note, discovered during implementation:** this only fixes
  *building* the pipeline. Each individual op in `stream.py` (`filter`,
  `map`, `flat_map`, `sorted`, `peek`, `_DistinctOp`, `_LimitOp`,
  `_SkipOp`) is itself implemented as `async def fn(iterable): async for i
  in iterable: yield ...`, so *consuming* a long chain still recurses once
  per chained op at the `async for`/`__anext__()` delegation level,
  confirmed unchanged before and after this fix by testing a long
  `.map()` chain end-to-end. Fully closing the original roadmap item's
  stated risk requires a push-based execution-model redesign across every
  op in `stream.py` and `parallel_stream.py` — out of scope here and
  tracked as a new **Next**-bucket item. See
  `openspec/changes/rewrite-sequential-iterative`.
- Fixed `ParallelStream` crashing on any source with a real `await`
  suspension point. `ParallelStream._parallel` (`parallel_stream.py`) fanned
  `PROCESSES` racing branches out over the *same* shared `self._stream`
  async generator, each calling `__anext__()` on it independently; a source
  with a genuine `await` inside `__anext__()` raised
  `RuntimeError: anext(): asynchronous generator is already running` as soon
  as two branches' pulls overlapped. Fixed by adding a `_guarded(source,
  lock)` wrapper generator (`parallel_stream.py`): each branch gets its own
  wrapper instance, but all wrappers serialize their calls into the shared
  source's `__anext__()` (and `aclose()`) through one `asyncio.Lock` created
  per `_parallel()` call, so only one pull is ever in flight while
  downstream per-branch processing (`map`/`filter`/etc.) still runs
  concurrently. Fixing this surfaced a second, previously-latent race in
  `_LimitOp` (`stream.py`): its check-then-pull-then-increment sequence
  against the shared `size_holder` wasn't atomic once the pull could
  genuinely cede control, letting multiple branches pass the size check
  before any incremented and yield more than `n` elements in total. Fixed
  by reordering to reserve the slot (increment) *before* pulling, so the
  check-and-reserve step has no `await` between them and stays atomic
  across racing branches. Added `tests/test_parallel.py` coverage using a
  source with a real `await asyncio.sleep(0)` suspension point: empty and
  non-empty chains no longer raise, `.limit(n)` stays at-or-under `n` and
  closes the shared source safely across branches, and downstream mapper
  invocations still overlap despite serialized upstream pulls (timing
  assertion). No public API change. See
  `openspec/changes/fix-parallel-stream-await-crash`.
- Added `BaseStream.unordered()` — marks a stream instance as not
  order-dependent, mirroring Java's `BaseStream.unordered()`. Implemented as
  a `self._ordered: bool` flag on `BaseStream` (`base_stream.py`), defaulting
  to `True`; `unordered()` sets it `False` and returns `self`, matching the
  mutate-and-return-self convention every other chainable method already
  follows; `is_ordered()` exposes the current value, mirroring the existing
  `is_parallel()` query method. `sequential()`/`parallel()` now copy the
  flag onto the new instance they construct rather than resetting it, so an
  `unordered()` declaration survives a mode switch. Purely additive
  bookkeeping — no change to actual iteration order in `Stream` or
  `ParallelStream`; it exists to unblock the planned `forEachOrdered()` and
  `find_first()`/`find_any()` distinction (`stream.py`'s disabled
  `find_first` stub), neither of which consume the flag yet. Added
  `tests/test_unordered.py` covering: ordered-by-default for both `Stream`
  and `ParallelStream`, `unordered()` mutation and chaining (returns `self`,
  composes with other intermediate ops), isolation across separate `Stream`
  instances, and flag propagation across `.parallel()`/`.sequential()` mode
  switches (both directions, with and without `unordered()` called). See
  `openspec/changes/add-stream-unordered`.
- Added `BaseStream.iterator()` — exposes the composed stream chain as a
  plain `AsyncGenerator` without going through a collector, so a caller can
  drive consumption directly via `async for`, `__anext__()`, or partial
  iteration. Implemented as a thin wrapper around the existing `_compose()`
  mechanism already used by terminal operations (`base_stream.py`), so it
  works identically for `Stream` (sequential) and `ParallelStream` (parallel)
  with no subclass-specific override, and — like other terminal ops —
  composes non-destructively, leaving `self._chain` intact for later reuse.
  Added `tests/test_iterator.py` covering: no elements pulled before
  iteration starts, same elements/order as `collect(to_list)` for an
  equivalent chain, partial consumption, `ParallelStream` behavior (racing
  branches, unordered), and non-destructive composition (a second terminal
  op after `iterator()` still sees the full chain). No public API removal;
  purely additive. See `openspec/changes/archive/2026-08-13-add-stream-iterator`.
- Added `Stream.reduce(accumulator)` — the 1-arg, no-identity overload,
  returning `T | None` (`None` for an empty stream) rather than a wrapped
  `Optional[T]` type, matching the existing `find_any()`/`max()`/`min()`
  convention already used elsewhere in `stream.py`. Implemented as a single
  `reduce()` method carrying two `@overload` signatures (identity form and
  no-identity form) with one runtime body: a private `_UNSET` sentinel
  distinguishes "no identity given," in which case the first pulled element
  seeds the fold and an empty stream short-circuits to `None` before the
  accumulator is ever called; a single-element stream likewise returns that
  element without calling the accumulator. Delegates to the same
  `_maybe_await`-based accumulator dispatch the 2-arg form already used, so
  sync and async accumulators both work with no duplicated dispatch logic.
  Added a new `BinaryOperator` alias to `type.py` for the no-identity
  accumulator's `T, T -> T` shape, following the project's convention that
  composite/callable type shapes used in public signatures live in
  `type.py` rather than being written inline. Added 6 new tests in
  `tests/test_reduce.py` (empty stream, single-element stream, multi-element
  fold order, async-accumulator awaiting, a hypothesis property test against
  `functools.reduce`, and a regression check that the existing 2-arg form is
  unchanged). No changes to the existing `reduce(identity, accumulator)`
  behavior. See `openspec/changes/add-reduce-no-identity`.
- Added `Stream.skip(n)` — drops the first `n` elements pulled from upstream
  and yields the rest, symmetric with the already-implemented `limit(n)`.
  Implemented as `_SkipOp` (`stream.py`), mirroring `_LimitOp`'s
  `make_state()`/shared-state pattern so `ParallelStream._parallel()`'s
  existing generic `make_state()`-detection wires up correct parallel
  behavior (exactly `n` total elements dropped across all racing branches,
  not per-branch) with no `parallel_stream.py` changes needed. Unlike
  `limit()`, `skip()` has no short-circuit available — the first `n`
  elements must actually be pulled and discarded to advance upstream past
  them. Added `tests/test_skip.py` plus parallel-specific regression tests
  in `tests/test_parallel.py` (drops exactly `n` across branches, state
  fresh across separate streams). No public API change to existing methods.
  See `openspec/changes/add-stream-skip`.
- Made `Stream` generic (`Stream[T]`): `BaseStream`/`Stream`/`ParallelStream` were
  plain classes, so the `T`/`R` in their method signatures were unbound
  `TypeVar`s and element types were `Unknown` end to end — `ty` accepted
  `Stream.of([1,2,3]).map(lambda s: s.upper())` without complaint despite
  `int` having no `.upper()`. Fixed by making `BaseStream`/`Stream`/
  `ParallelStream` `Generic[T]`; `map()`/`flat_map()` now return `Stream[R]`
  via a narrowly-scoped `cast(Stream[R], self)` since the chain-of-closures
  model mutates and returns the same `self` rather than a new instance
  (deliberately not revisiting the separate mutable-builder-vs-immutable-
  pipeline decision below); type-preserving ops (`filter`, `distinct`,
  `peek`, `limit`, `sorted`) return `Stream[T]` directly; terminal ops are
  typed against the stream's bound `T`. Also fixed `type.py`'s `FlatMapper`
  alias, which hardcoded an unparameterized `Stream` instead of `Stream[R]`,
  and `StreamBuilder.build()`, which dropped its already-declared `T`
  instead of returning `Stream[T]`. Typing-only change, no runtime behavior
  differs. Added `tests/test_static_typing.py` plus `tests/typing/`
  fixtures that shell out to `ty check` to regression-test that the
  motivating bug is now caught and that valid generic usage still
  type-checks cleanly. See `openspec/changes/make-stream-generic`.
- Made `limit(n)` a real short-circuit: `_LimitOp.__call__` (`stream.py`) pulled
  an element from upstream *before* checking whether `max_size` had already
  been reached, so every `limit(n)` pipeline pulled `n+1` elements instead of
  `n` — e.g. `Stream.of([1,2,3,4,5]).peek(seen.append).limit(2)` returned
  `[1, 2]` but left `seen == [1, 2, 3]`. Fixed by checking the size before
  pulling rather than after, so upstream is closed without ever pulling an
  `n+1`th element. Under `.parallel()`, the shared `size_holder` in
  `ParallelStream._parallel`'s `state_map` already gave a global (not
  per-branch) limit guarantee; the fix changes *when* the shared source gets
  closed — whichever branch observes the shared count reaching `max_size`
  closes it before pulling further — and closure was made idempotent so a
  second racing branch closing (or pulling from) an already-closed shared
  source doesn't raise out of the task loop. No public API change. See
  `openspec/changes/archive/2026-08-12-fix-limit-short-circuit`.
- Replaced the repeated `if iscoroutinefunction(x): await x(...) else: x(...)`
  dispatch pattern (10 sites across `filter`, `map`, `sorted`'s comparator,
  `peek`, `reduce`, `for_each`, `min`/`max` via `_min_max`, and the
  `all_match`/`any_match`/`none_match` family) with a single
  `async def _maybe_await(fn, *args)` helper in a new
  `callable_dispatch.py`, which calls first and awaits the result only if
  `inspect.isawaitable(result)`. Fixes a real bug: `iscoroutinefunction()`
  is `False` for a class instance with an `async def __call__`, so passing
  such a callable object as a predicate/mapper/etc. previously produced an
  un-awaited coroutine flowing downstream as if it were a real value, with
  only a `RuntimeWarning` — no exception. `flat_map`'s existing
  `iscoroutinefunction()` check, which *rejects* coroutine-returning
  mappers up front, is a distinct pre-call classification and was left
  untouched. Also collapsed `all_match`/`any_match`/`none_match`'s three
  near-identical bodies into one shared `_match(predicate, short_circuit_on,
  default)` helper built on `_maybe_await`.

  `sorted()`'s comparator dispatch turned out not to fit the same
  call-then-await shape: its `iscoroutinefunction()` check picks between
  two different sort algorithms (`merge_sort`, which unconditionally
  awaits the comparator, vs. `list.sort()` with a sync `cmp_to_key`
  wrapper) rather than gating a single await. Fixed by moving `_merge`
  (`sort.py`) onto `_maybe_await` internally and always routing `sorted()`
  through `merge_sort` when a comparator is given, dropping the
  `cmp_to_key`/`list.sort()` branch entirely — this also closes the same
  async-callable-object gap for `sorted()`/`min()`/`max()`. Added
  regression tests (`tests/test_callable_dispatch.py`) covering
  `_maybe_await` directly (sync/async function, sync/async callable
  object) and each affected operation with an async-`__call__` callable
  object.
- Fixed two compounding bugs that made a second terminal operation on the
  same `Stream`/`ParallelStream` instance silently return wrong (usually
  empty) results instead of repeating the first run's behavior. First,
  `BaseStream._sequential()` (`base_stream.py`) was handed `self._chain`
  directly and called `pop(0)` on it, draining the caller's own chain list
  during `_compose()`; fixed by passing `self._chain[:]` (a copy) from
  `_compose()` instead — matching the copy `ParallelStream._parallel()`
  already made for its own branches, so both subclasses now honor the same
  non-destructive contract. Second, `distinct()`/`limit()` (`stream.py`)
  each built their `seen`/`size` state in the outer function that runs once
  per `.distinct()`/`.limit()` call, rather than in the closure that runs
  once per composition, so that state silently persisted across separate
  compositions of the same chain; fixed by replacing the two closures with
  small callable classes (`_DistinctOp`, `_LimitOp`) whose `__call__` takes
  an optional external state and falls back to fresh per-call state via
  their own `make_state()` when none is given — giving `Stream` (sequential)
  fresh state on every composition by default. For `ParallelStream`, where
  multiple racing branches must share one `seen`/`size` per composition to
  stay globally correct (matching Java's guarantee that parallel `distinct`/
  `limit` never silently degrade into a per-partition, unreconciled result,
  even though it costs more to coordinate — see
  `openspec/changes/fix-stream-rerun-state/design.md`), `_parallel()` now
  builds one state map per composition via each op's `make_state()` and
  passes the same map into every racing branch's `_sequential()` call.
  Added regression tests covering: chain length unaffected by composition,
  a second terminal op after the first, `distinct()`/`limit()` state not
  leaking across separate `Stream`/`ParallelStream` instances or across
  separate compositions of one instance, and parallel `distinct()`/`limit()`
  staying globally correct (no cross-branch duplicates, no over-`limit()`)
  across racing branches.
- Simplified `Stream.of()` (`stream.py`) from a four-way branch on dict vs.
  list vs. multiple positional args vs. kwargs down to two cases: a single
  positional arg passes straight through to `Stream()`'s existing source
  normalization, multiple args wrap into a list (one element each). The
  dict/list `isinstance` special-casing turned out to be dead complexity —
  tracing all 15 existing `test_of.py` cases showed it always produced the
  same call as the generic path, since `_normalize()` already re-spreads
  lists/dicts on its own. Also fixed `_normalize()` (`base_stream.py`) to
  treat `str`/`bytes` as scalar values, matching how Java's `Stream.of(T...)`
  treats `String`/`byte[]` atomically (byte arrays can't decompose via
  varargs since `T` can't bind to a primitive type), instead of the previous
  silent char-by-char/byte-by-byte spreading. Both changes are **BREAKING**
  and tracked in README's migration log per `CLAUDE.md`: `**kwargs` support
  is removed from `Stream.of()` entirely (no Java equivalent, undiscoverable,
  no real use case over `Stream.of(*some_dict.items())`), and
  `Stream.of("abc")`/`Stream.of(b"ab")` now yield one element instead of
  spreading.
- Added property-based tests with `hypothesis` for `map`, `filter`, `reduce`,
  `sorted`, `distinct` against a plain-Python reference oracle, covering
  edge cases hand-written tests miss (empty/single-element streams,
  duplicate keys, async callables).
- Added a `check_comparator_result_type()` runtime guard (`sort.py`) that
  raises `TypeError` if a user-supplied `Comparator` returns `bool` instead
  of `int`, used by `Stream._min_max()` (backing `min()`/`max()`) and both
  branches of `Stream.sorted()` (sync `cmp_to_key` path and the async
  `merge_sort`/`_merge` path). Closes a gap the earlier `Comparator`
  contract fix (below) didn't cover: Python's `bool` is a subclass of `int`,
  so a bool-returning comparator like `lambda x, y: x > y` type-checks fine
  under `ty`/mypy/pyright and previously degraded silently instead of
  erroring — for `min()` it could never signal "orders before" (always
  returning the first element), while `max()`'s behavior happened to be
  correct by coincidence. No static-typing trick can close this gap since
  it's structural to Python, not a `type.py` alias choice. Also fixed 18
  pre-existing tests across `tests/test_min.py`/`tests/test_max.py` that
  were passing bool comparators and only passed today via first-element
  luck (`min()`) or coincidence (`max()`); added regression tests asserting
  the `TypeError` for `min()`/`max()`/`sorted()`, sync and async. Tracked as
  **BREAKING** in README's migration log per `CLAUDE.md`.
- Fixed the `Comparator` type alias mismatch (`type.py:16`): kept a single
  Java-style 3-way *int* `Comparator` (matching `sorted()`'s existing usage
  and Java's own `Stream.min/max(Comparator)`), rather than splitting into
  two aliases, and fixed `Stream.min()`/`max()`/`_min_max()` (`stream.py`)
  to interpret the comparator's sign directly instead of treating it as a
  bool. This also fixed the tie-break bug for free: both `min()` and `max()`
  now keep the first of equal elements. Tracked as **BREAKING** in README's
  migration log per `CLAUDE.md` since bool-returning comparators passed to
  `min()`/`max()` now behave differently.
- Added an `install_smoke_test` CI job (`.github/workflows/check.yml`) that,
  for each of Python 3.10–3.14, creates a clean venv (`uv venv`, not
  `uv sync`), runs `pip install .` against the built package, and imports
  `snakestream` from outside the repo checkout — catching packaging
  mistakes that the source-tree `pytest` job wouldn't.
- Added static type checking to CI using `ty`, Astral's newer Rust-based
  type checker — chosen over `mypy`/`pyright` since it fit the existing
  `uv`/`ruff` toolchain and handled the codebase's `Awaitable`-union type
  aliases without issue. Fixed the 6 genuine type errors it surfaced
  (`BaseStream.on_close`'s return type, `ParallelStream`'s task-list
  typing, `StreamBuilder`'s unbound `TypeVar`, `Stream.collect`'s generic
  return type, and `Stream._min_max`'s sentinel-return typing), plus one
  scoped `ty: ignore` for a case the checker can't narrow via the
  runtime `iscoroutinefunction()` check in `Stream.sorted`. Gated to the
  3.14 matrix leg only, matching the coverage-gate precedent.
- Verified `--cov-fail-under=98` already enforces combined line+branch
  coverage, not line coverage alone: `[tool.coverage.run] branch = true`
  folds branch-arc misses into the same "percent covered" figure the gate
  reads, confirmed by observing a deliberately partial branch drop the
  reported percentage. No code change needed; added a comment in
  `pyproject.toml` recording the finding so it doesn't need re-deriving.
- `min()`/`max()` used to silently skip falsy candidate values (`0`, `""`,
  `False`) because of a truthiness check in `Stream._min_max`. Fixed by
  replacing the `None`-as-sentinel logic with a proper `_UNSET` sentinel.
- `parallel()` pipelines left orphaned `asyncio` tasks (and "Task exception
  was never retrieved" warnings) when one branch raised mid-stream. Fixed in
  `ParallelStream._parallel` by cancelling and draining remaining tasks in a
  `finally` block.
- Test infra was silently dropping tests on a clean install: `pytest-mock`
  was missing from `setup.cfg`'s `testing` extra, and the `async_int_to_letter`
  fixture in `conftest.py` wasn't decorated for strict-mode `pytest-asyncio`.
  Both fixed; added regression tests for the two bugs above
  (`test_min.py`, `test_max.py`, `test_exception.py`).
- `Stream.of()` had a dead branch, `if args and len(args) == 0: pass`
  (`stream.py:40-41`), which could never be true and just duplicated the
  no-op fallthrough of the `else` branch. Removed.
- The `TYPE_CHECKING`-only import in `stream.py:17` used an unqualified
  `from stream_builder import StreamBuilder`, which would fail if ever
  actually evaluated. Fixed to `from snakestream.stream_builder import
  StreamBuilder`.
- Added tests covering the async-predicate short-circuit branches of
  `all_match`, `none_match`, and `any_match` (`stream.py:255,267,283`) that
  were previously only exercised by synchronous predicates.
- Added a `--cov-fail-under=98` gate so a coverage regression now fails CI
  instead of silently passing. Enforced only on the newest Python version
  in `check.yml`'s matrix (not via `setup.cfg`'s `addopts`), since
  `coverage.py`'s branch-arc measurement for `async for` loops differs
  across CPython versions and produced spurious failures on 3.8/3.9.
- Fixed `deliver.yml` to target `master` instead of `main`, since the repo's
  default branch is `master` and the workflow was never triggering.
- Pinned GitHub Actions to commit SHAs and added concurrency guards to CI
  workflows.
- Added `pip-audit` dependency-vulnerability scanning and `ruff format`
  enforcement to CI.

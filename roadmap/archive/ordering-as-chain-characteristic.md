+++
id = "ordering-as-chain-characteristic"
title = "Ordering became a chain characteristic instead of an instance flag"
filed = 2026-08-26
closed = 2026-08-26
outcome = "shipped"
+++

**Ordering became a chain characteristic instead of an instance flag**
(2026-08-26). `unordered()` set `self._ordered = False`, so it applied to the
whole pipeline no matter where it was written — `parallel()`'s rule, copied
onto the one method Java deliberately gives the opposite rule. Java's
`parallel()` sets a field on the *source stage* precisely so as to be
position-independent; its `unordered()` is a `StatelessOp` contributing
`NOT_ORDERED`, folded downstream only by `combineOpFlags()`, and its
`sorted()` contributes `IS_ORDERED` back. See
`openspec/changes/make-ordering-a-chain-characteristic`.

**The drift produced a wrong answer, not just an inelegance.** Because a
field cannot be re-set by a later stage, `sorted()` could not restore
ordering, and the flag's only consumer — `find_first()`, which degraded to
`find_any()` when unordered — then returned a branch-local minimum of a
sorted pipeline. Measured over an async source of `range(200, 0, -1)` under
`.parallel()`, ten runs each:

```
.parallel().sorted(asc).find_first()              ->  1 1 1 1 1 1   (correct)
.parallel().unordered().sorted(asc).find_first()  ->  2 4 4 2 3 4   before
.parallel().sorted(asc).unordered().find_first()  ->  2 4 4 3       before (identical: global)
.parallel().unordered().sorted(asc).find_first()  ->  1 1 1 1 1 1   after
```

Java returns the minimum in all of them. The last line is pinned by
`test_find_first_after_unordered_and_sorted_returns_the_smallest`, run ten
times because the wrong answer was nondeterministic.

**`Ordering` (`sink.py`) is a three-member enum — `PRESERVE`/`CLEAR`/`SET` —
on `Op` as a `ClassVar`, defaulting to `PRESERVE`.** Only `_SortedOp` (`SET`)
and the new `_UnorderedOp` (`CLEAR`) state it; the other seven take the
default, which is also what Java says about them. A `ClassVar` because
ordering is a property of the *operation*, not of the arguments: every sort
sets it, whatever comparator it was given. **Java's semantics were ported,
its encoding was not** — `StreamOpFlag` packs two bits per flag in an int
because it carries five characteristics through a fold that runs on every
stage, and we carry one.

**`_UnorderedOp` is the one op with no sink.** `link()` returns the
downstream untouched, exactly as Java's `opWrapSink(flags, sink) { return
sink; }` does, so it cannot observe, transform, reorder, drop or duplicate
anything and never enters the sink chain at all. Measured: `count()` over
20k elements, 9.32 ms without it and 9.29 ms with it queued (**-0.3%**, i.e.
noise). It exists only to occupy a position and declare a characteristic
there — which is the whole of what makes ordering positional.

**`is_ordered()` folds the chain and stores nothing.** 311 ns over a
five-op chain, called at most once per terminal. **The O(1) alternative was
measured and rejected, and should not be re-proposed**: updating a cached
`_ordered` incrementally in `_extend()` (`_derive(op)` since 2026-08-26) from
the op being appended is exactly
equivalent (the chain only ever grows by append) and saves those 311 ns, but
reinstates a denormalised copy of a chain property that every future derive
path must remember to maintain — which is the precise failure mode this
change exists to remove. `_ordered` is gone from `__init__` and from
`_derive()`'s copy list.

**Two breaking changes, both in README's migration log.** `unordered()`
returns a new instance and consumes the receiver, joining the enumerated
intermediate ops in `pipeline-immutability` rather than sitting as a
footnote against it — the exemption existed only because it had no chain
element to append. And `find_first()` dropped its `is_ordered()`
short-circuit and always drives `SEQUENTIAL`: **Java does not relax
`findFirst()` on an unordered stream either.** `FindOp.mustFindFirst` is
fixed when the op is constructed and `FindTask` does its leftmost scan
whenever it is set, never consulting upstream `ORDERED` — the javadoc
permits returning any element there, the implementation declines to.
`find_any()` is where a caller who wants the race goes.

**`for_each_ordered()` gained the relaxation `find_first()` lost**, and is
now the flag's consumer: on an unordered pipeline it runs under the stream's
own executor instead of forcing `SEQUENTIAL`, matching
`ForEachOps.OfRef.evaluateParallel()`'s choice between `ForEachOrderedTask`
and `ForEachTask`. This closes the note left in this roadmap's
`add-stream-foreach-ordered` entry, which said the flag was not consumed
there because `unordered()` "doesn't currently model" streams with no
defined encounter order. It does now.

582 tests green, up from 567 — three of which this change turned around
rather than added to: `test_unordered_returns_self_for_chaining`,
`test_unordered_parallel_find_first_races` and
`test_find_first_on_unordered_parallel_stream_races` all asserted the
behaviour being removed. Coverage 98.06%, `ruff`, `ruff format --check` and
`ty check src` clean. Four spec deltas — `stream-ordering`
(+3 requirements, ~1, -2), `stream-find-first` (+1, -1),
`stream-foreach-ordered` (+1, ~1), `pipeline-immutability` (~2). Left open
deliberately, and **written up in Now**: `limit`/`skip`/`distinct` still
ignore the characteristic under `RACING`, and `sorted()` under `RACING` does
not sort at all. This change's own design doc framed the first three as a
missed optimisation — Java exploiting unorderedness to run cheaper — and that
was backwards. All three already behave as if unordered unconditionally, so
what is missing is the *ordered* path, and they are wrong answers on an
ordered stream rather than slow ones. Confirmed by measurement after the
change landed; the figures are in **Now**. What this change contributes is
that the branch is now expressible: `is_ordered()` gives a reliable
positional answer where the old instance flag did not.

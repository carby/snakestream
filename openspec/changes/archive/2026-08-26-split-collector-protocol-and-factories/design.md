## Context

See `proposal.md` — Why. Two constraints shape the approach:

1. **`snakestream.collector` is a public import path, not an internal one.**
   README's quickstart opens with `from snakestream.collector import
   to_generator`, and 46 files under `tests/` import factories from it. The
   roadmap row that proposed this split described it as "private-surface
   only apart from one new public exception base"; that is wrong, and the
   breaking import-path change is the largest single thing here.
2. **The two halves have disjoint dependencies.** The protocol half is the
   only reason `collector.py` imports `_maybe_aclosing` from `execution.py`
   (it exists solely for `_stream`); the factory half is the only reason it
   imports `is_new_extremum` from `comparator.py` and most of `type.py`'s
   aliases. The split therefore cleans up the import graph rather than
   duplicating it.

## Goals / Non-Goals

**Goals:**

- One module per thing: `collector.py` = the protocol, `collectors.py` = the
  factories, matching Java's `Collector` / `Collectors` pair.
- A one-way import edge, `collectors.py -> collector.py`, visible as an
  import rather than implicit in file ordering — the same shape the
  `sort.py`/`comparator.py` split settled on.
- A tripwire the change either passes or fails visibly: the suite passes with
  no test file edited *except its import lines*.

**Non-Goals:**

- No behaviour change to any collector, to `collect()`, or to the sink
  protocol. Bodies move verbatim.
- No compatibility shim. A re-export from `collector.py` was considered and
  rejected (see Decisions).
- No renaming of `StreamBuildException` or `IllegalStateException`, and no
  third exception type. The base is added and the story stops there.
- No `ExceptionGroup` work in `Stream.close()` — parked in the roadmap's
  **Now** notes pending an explicit call, and untouched here.
- No `ruff --select` widening. That is the next story, deliberately sequenced
  after this one so the new rules judge the module layout this change settles
  on.

## Decisions

### Split at the protocol/factory seam, factories to `collectors.py`

`collector.py` keeps `Collector`, `_CollectorSink`, `StreamingCollector`,
`_stream` and `to_generator` — roughly lines 30-117 today, ~90 lines.
`collectors.py` takes everything from `to_list` onward: the ~22 public
factories, `SummaryStatistics`, and the private helpers and container
dataclasses only they use (`_SumBox`, `_AvgBox`, `_SummaryBox`,
`_ExtremumBox`, `_ReduceBox`, `_ToMapBox`, `_GroupBox`, `_MappingBox`,
`_CollectAndThenBox`, `_summing`, `_averaging`, `_summarizing`, `_extremum`,
`_group_into`, `_finish_groups`, `_check_downstream`,
`_finish_collecting_and_then`).

*Alternative rejected — invert the split*, leaving factories in
`collector.py` and moving the protocol to a new module. Zero public break,
but it leaves the module named `collector` holding `Collectors`, and the new
module needs an invented name — the opposite of the Java naming the split is
reaching for.

### `to_generator` stays in `collector.py`

It is a `StreamingCollector` value, not a factory, and the
`collector-protocol` spec already singles it out as "the one non-`Collector`
collector". Keeping it beside the type it is an instance of is the
consistent read, and it happens to leave README's quickstart import
untouched. The cost is that a caller passing both `to_generator` and a
factory to `collect()` imports from two modules; that is the honest shape,
since the two are genuinely different kinds of thing.

*Alternative rejected — move `to_generator` to `collectors.py`* so every
`collect()` argument comes from one module. It reads well at the call site
but puts a `StreamingCollector` instance in a module whose stated rule is
"factories returning `Collector`", re-creating in `collectors.py` exactly the
two-things-in-one-module problem this change is fixing.

### No re-export shim; break the import path loudly

`collector.py` will not re-export the factory names. A shim would leave two
live import paths for the same ~22 names indefinitely, and this project's
migration log shows the established posture: pre-1.0 breaks are taken
cleanly and documented, not softened (`to_list` becoming a factory,
`Stream.concat` dropping `async`, `to_map`'s exception type). The break is
loud — `ImportError` at import time, before any stream is built — which is
the best failure mode available.

*Alternative rejected — deprecation shim with a warning.* The library has no
deprecation machinery today and adding it for one release, pre-1.0, on a
rename that fails at import time, is more surface than the break costs.

### `StreamException` derives from `Exception` only

Inserting a base above two existing classes is source-compatible by
construction: every existing `except StreamBuildException` still matches.
The one temptation to refuse is giving `StreamException` a second base such
as `ValueError` to soften past breaks — refused for the reason the previous
batch already recorded for `IllegalStateException`: the same hierarchy covers
stream-reuse errors, and a stream-reuse error is not a `ValueError`.

Java has no common base for its stream exceptions to copy, so the
Java-parity rule does not decide the name; `StreamException` was the user's
call over `SnakestreamException`.

### `_derive_executor()` is the home for the duplicated mode-switch docstring

`sequential()` and `parallel()` carry the same twelve-line docstring
verbatim, and the explanation is about the *mechanism* both share — a new
stream over the same source and chain, deliberately not composing — not about
either mode. Extract `Stream._derive_executor(executor)` holding that
docstring and the `_derive(self._chain, executor)` call; each public method
becomes a one-line docstring naming its mode and delegating.

This is not an invented seam: `CLAUDE.md`'s "Sequential vs. parallel
execution" section already states that "`.parallel()` / `.sequential()` go
through `_derive_executor()`". The docs describe a method the code never
grew. This change makes the code match the documentation rather than the
other way round.

*Alternative rejected — `parallel.__doc__ = sequential.__doc__`.* Removes the
duplication in the source but leaves two identical rendered docstrings and
makes `parallel`'s help text depend on a line far from it.

### `TerminalSink`'s awaitable contract is documented, not enforced

`begin()` routes `_create_container()` and `end()` routes `_finish()` through
`_maybe_await`, and three sites depend on it: `_CollectorSink._create_container`
returns a possibly-async supplier's result un-awaited, and `grouping_by`'s and
`partitioning_by`'s `_finish` are *sync* functions returning the un-awaited
coroutine of `_finish_groups`. Each reads like a missing `await` until the
base class is traced. The fix is one paragraph in `TerminalSink`'s docstring.
Adding defensive `await`s at the three sites is explicitly out of scope — it
would make two sync functions async for no behavioural gain.

### `Box` becomes `@dataclass(slots=True)`

The last hand-written `__slots__`-plus-`__init__` container. `slots=True`
emits the same descriptors, and `Box` is constructed once per collection
(`counting()`) or once per composition (`ops.py`'s two `make_shared_state()`
bodies) — never per element. Its single field has a default of `None`, which
a dataclass field expresses directly. Attribute access inside accumulators is
unchanged.

## Risks / Trade-offs

- **[46 test files must be edited, which weakens the "no test edits"
  tripwire.]** → Constrain the edit mechanically: the only permitted change in
  `tests/` is `snakestream.collector` -> `snakestream.collectors` on import
  lines, verifiable with `git diff -U0 -- tests/` showing nothing but import
  lines. Any other test edit is the signal the change went wider than the
  split. `tests/test_collector.py` is the one file that legitimately imports
  from both modules afterwards, since it exercises `to_generator` and the
  factories.
- **[A circular import between the two new modules.]** → The edge is one-way
  by construction: `collectors.py` imports `Collector` from `collector.py`,
  never the reverse. `collector.py` must not gain a factory import. Verify
  with a clean-interpreter `import snakestream`, as the previous batch's
  story 6 did for `collector.py`'s new `exception` import.
- **[Coverage percentage moves without any test being lost.]** → The previous
  batch recorded this: a change that only relocates statements leaves the
  uncovered set identical, but the total denominator can shift. Compare
  missed statements/branches, not the percentage, before treating a drop as a
  regression.
- **[`ty` may resolve the moved private generics differently across two
  modules.]** → `ty check src` is part of the gate; run it before and after
  and diff the output rather than only checking the exit code.
- **[The split invites reorganising the factories while moving them.]** →
  Bodies move verbatim, in their current order, with no reordering, renaming
  or reformatting. A `git diff` of the move should be reviewable as a
  deletion plus an identical insertion.

## Migration Plan

1. Land `StreamException` first — it is additive, touches one 6-line file,
   and the spec delta for it is independent of the split.
2. Split the module, then update `stream.py`'s import (`Collector`,
   `StreamingCollector`, `_CollectorSink` from `collector`; `to_list` from
   `collectors`).
3. Update `tests/` imports mechanically, then run the suite.
4. Update README's collector table, README's Migration section, and
   `CLAUDE.md`'s Collectors section.
5. The remaining three items (`_derive_executor`, the `TerminalSink`
   docstring, `Box`) are independent of the split and of each other, and can
   land in any order after it.

**Rollback:** every step is a source-only change with no data or state
involved; reverting the commit is sufficient.

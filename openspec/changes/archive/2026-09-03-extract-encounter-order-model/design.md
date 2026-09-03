## Context

See proposal.md — Why. The state that shapes the approach, and nothing else:

**The dependency graph today.** `ordering`'s four symbols sit at two points in
it:

```
type.py       (no intra-package imports)
callable_dispatch.py
sink.py       -> callable_dispatch, type          Ordering, is_ordered
ops.py        -> callable_dispatch, sink, sort, type
execution.py  -> sink, type                       OrderDemand, _split_point
collector.py  -> execution, callable_dispatch, sink, type
collectors.py -> collector, ...
stream.py     -> everything above
```

`sink.py` is the deepest module both `execution.py` and `stream.py` can reach,
which is why the fold landed there; `execution.py` is `_split_point()`'s only
caller, which is why the demand landed there.

**What the four symbols actually touch.** `Ordering` and `OrderDemand` are bare
`Enum`s with no dependencies at all. `is_ordered()` and `_split_point()` are
pure synchronous functions over `(list[Op], ...)` that read exactly two
attributes off each op — `op.ordering` and `op.order_sensitive` — and neither
constructs, links, drives, nor awaits anything. Nothing in the group imports
`asyncio`, a sink, or a stream.

**Where they are read.** `Ordering`: `sink.py` (`Op.ordering` default),
`ops.py` (`_SortedOp`, `_UnorderedOp`), `_split_point()`. `is_ordered()`:
`_split_point()`, `_run_ordered_tail()`, `Stream._is_ordered()`. `OrderDemand`:
every terminal call site in `stream.py`, the `Executor` protocol,
`_split_point()`. `_split_point()`: `race_through()` alone, once per
composition.

**The gate that does not apply.** Every symbol here is read either at import
time (the enum members), once per composition (`_split_point()`), or a
single-digit number of times per terminal (`is_ordered()`, folding a chain that
is single digits long). None is on a per-element path, so the `+10% ns/element`
threshold from `collapse-terminal-collector-duplication` has nothing to
measure — see decision 5.

## Goals / Non-Goals

**Goals:**

- One module a reader can open to find the whole encounter-order model, so
  that CLAUDE.md's "The ordering barrier" section describes one file.
- Module docstrings that are true of their contents: `sink.py`'s push protocol,
  `execution.py`'s primitives and executors.
- Placement decided by concern rather than by import topology, so the next
  symbol in this family has an obvious home.
- Zero behaviour delta, provable by inspection rather than by test: the same
  objects, the same `is` comparisons, the same call sites.

**Non-Goals:**

- Changing what any of the four symbols means, or its signature.
- Re-homing anything else that sits in `sink.py` for import-topology reasons
  (`_UNSET`, `_unseeded()`, `Box`). Same diagnosis, separate change — bundling
  them would make one diff carry two independent judgement calls.
- Reorganising the test suite. Test modules are named for capabilities
  (`test_unordered.py`, `test_op_protocol.py`), not for `src/` modules, so a
  module move implies no test move.
- Introducing an `ordering` concept to the public API. Nothing here is exported
  from `__init__.py` before or after.

## Decisions

### Decision 1: A third module, not a consolidation into either existing one

**Chosen:** a new `src/snakestream/ordering.py` holding all four symbols.

The two consolidations are the obvious alternatives and both were considered
concretely:

- **Everything into `sink.py`** (move `OrderDemand` and `_split_point()` down).
  It has the smaller diff and creates no new import edge. Rejected because it
  makes the stated problem worse in the direction that matters: `sink.py`'s
  docstring already describes a push protocol it only partly contains, and this
  would add a *terminal-operation policy* enum to a module whose subject is
  `begin`/`accept`/`end`. `OrderDemand` is declared at a `Stream` terminal call
  site, not by a sink — `_FindSink` backs both `find_first()` (`ALWAYS`) and
  `find_any()` (`NONE`), and `_ForEachSink` backs both `for_each()` (`NONE`) and
  `for_each_ordered()` (`IF_ORDERED`) — so the demand provably is not a property
  of the sink class, and putting it in the sink module would suggest it is.
- **Everything into `execution.py`** (move `Ordering` and `is_ordered()` up).
  Rejected on the graph: `ops.py` and `sink.py` both need `Ordering` and neither
  may import `execution.py` — `execution.py` imports `sink.py`. This one is not
  a preference, it is a cycle.

A third module is what remains, and it is also what the concern argues for
independently of the graph: four symbols, one subject, no other subject.

**Name: `ordering.py`.** The repository names modules for their contents —
`sink.py`, `collector.py`, `comparator.py`, `execution.py`, `sort.py` — and
`ordering` is the word this project already uses for the concept in the spec
that governs it (`openspec/specs/stream-ordering/`), in `Ordering` itself, and
throughout CLAUDE.md. Considered and rejected: `encounter_order.py` (accurate
but not the noun any existing artifact uses), `characteristics.py` (Java's
`StreamOpFlag` carries five characteristics; we carry one, and `Characteristics`
is already taken by the collector enum), `stream_op_flag.py` (Java-parity naming
is the house preference for the *public API surface*; this is an internal module
holding a port of the *meaning* of that flag and not its encoding, as
`Ordering`'s own docstring says).

### Decision 2: `ordering.py` depends on `Op` under `TYPE_CHECKING` only

`is_ordered()` and `_split_point()` are annotated `chain: list[Op]`, and `Op`
lives in `sink.py`, which will import `Ordering` at runtime. The import edge
therefore runs both ways on paper.

**Chosen:** `ordering.py` imports `Op` inside `if TYPE_CHECKING:`, exactly as
`type.py` already imports `Stream`. Both files carry `from __future__ import
annotations`, so the annotation never evaluates at runtime and there is one
real edge (`sink -> ordering`), not a cycle. The two functions read `op.ordering`
and `op.order_sensitive` structurally and construct nothing, so no runtime name
is needed.

**Alternatives considered:**

- **A structural `Protocol` in `ordering.py`** (say `_OrderDeclaring`, with the
  two ClassVars) so it names no `sink` symbol at all. Cleanest on paper, and
  rejected as a second abstraction bought to avoid a `TYPE_CHECKING` line the
  codebase already uses elsewhere. It would also give the two attributes a
  second declaration site that can drift from `Op`'s.
- **Moving `Op` into `ordering.py`.** Inverts the problem: `Op` is the factory
  half of the Op/Sink pair — `link()`, `make_shared_state()`, `_sink_cls` — and
  belongs with `Sink`. Its two ordering ClassVars are declarations *about* the
  model, not the model.
- **Passing `(ordering, order_sensitive)` pairs instead of ops**, removing the
  type entirely. Rejected: it moves work to every call site to buy a cleaner
  import, and `_split_point()` returns an *index into the chain*, so it needs
  the chain.

### Decision 3: `Op.ordering` and `Op.order_sensitive` stay on `Op`

The declaration stays with the declarer; only the vocabulary and the fold move.
`Op.ordering: ClassVar[Ordering] = Ordering.PRESERVE` still lives in `sink.py`,
and `_SortedOp`/`_UnorderedOp`/`_DistinctOp`/`_LimitOp`/`_SkipOp` still declare
theirs in `ops.py`. This is the same division CLAUDE.md already describes for
`OrderDemand`: the terminal declares its demand at its own call site, and
`_split_point()` reads it. Moving the declarations would put five ops' policy in
a module that knows nothing about ops.

### Decision 4: `_split_point()` moves; `_Window`, `_guarded()` and `_release_in_order()` do not

The line is model versus mechanism. `_split_point()` answers *where* order has
to be restored — a pure question about a chain and a demand, with no `asyncio`
in it. `_Window`, `_guarded()`, `_release_in_order()` and `_run_ordered_tail()`
are *how* it is then restored: locks, tasks, buffers, branches. They stay in
`execution.py`, which is the module for how a chain runs.

The test for the line, applied to the one genuinely arguable case: `_Window`
holds `released`, a reorder cursor, which sounds like ordering. It is an
`asyncio.Event` plus three counters coordinating branches, and it would be the
only thing in `ordering.py` that could deadlock. It stays.

### Decision 5: No benchmark, and that is a positive claim

`collapse-unseeded-accumulation-rule`'s decision 5 is the precedent and applies
a fortiori. Here nothing is even called differently: the enum members are the
same singletons, compared with `is` as before; `is_ordered()` and
`_split_point()` are the same function objects reached by the same names from
the same call sites; module-level `from x import y` resolves once at import.
There is no per-element path, no new call, no new allocation and no new
attribute hop — the three charges that carried every rejection in the roadmap's
**Done**.

Producing a ns/element figure would therefore measure harness noise, and
banking one would imply a gate this change is subject to, which it is not. If a
reviewer asks for a number, the answer is this decision.

### Decision 6: The moved prose moves verbatim

Every docstring in the group is moved unedited except where it makes a claim
that the move falsifies. Exactly three edits are owed, and they are the
change's whole prose delta:

1. `is_ordered()`'s *"Lives here rather than on `Stream` because `execution.py`
   needs it and may not import `stream.py` … `Op` and `Ordering` both live here
   already"* — the second clause becomes false the moment `Ordering` moves. It
   is restated as why the fold is a free function over a chain rather than a
   `Stream` method, which is the part that survives.
2. `sink.py`'s module docstring drops the ordering characteristic from its list
   of contents.
3. `execution.py`'s module docstring keeps naming `_split_point()` — it is
   still the thing `race_through()` consults — and names its module.

The duplicated `op / terminal` table in `OrderDemand`'s and `_split_point()`'s
docstrings is left duplicated. Both are now in one file where a reader sees
both, and collapsing it is a prose judgement that belongs to whoever next edits
either — not to a move.

## Risks / Trade-offs

- **A later runtime need for `Op` inside `ordering.py` turns decision 2's
  paper cycle into a real one** → the module docstring states the constraint
  ("reads ops structurally; imports `Op` for typing only"), so the next reader
  meets it before writing the import rather than after. The fallback if it ever
  happens is decision 2's rejected `Protocol`, recorded there.
- **`ty` may resolve the `TYPE_CHECKING` edge differently from `ruff`** → task
  6 runs both gates; the pattern is already in use in `type.py`, so a failure
  would be a surprise about `ty`, not about this change.
- **Three test files change** → not a risk in itself: a test import following a
  moved module is in scope and expected, and the surrounding changes in **Done**
  claimed "no test file touched" only because none of them moved a module. The
  claim here is the checkable one: `git diff tests/` shows *import lines only*,
  and the test count is identical (997 collected today). Task 5.2 checks both.
  What would be a real risk is an import edit that quietly turns into a test
  edit, which is why the check is on the diff rather than on the suite passing.
- **Coverage moves between files** → `sink.py` and `execution.py` each lose
  statements and `ordering.py` gains them; the total and the 98% gate are
  unaffected because no statement is added or removed. The per-file figures are
  expected to move and are not a regression.
- **Git history for the moved prose becomes a rename-plus-delete** → mitigated
  by decision 6: the text moves verbatim, so `git log --follow` and
  `git blame -C` both track it. Making prose edits in the same commit is what
  would break that, which is why the three owed edits are enumerated rather
  than made freehand.
- **Someone reads this as licence to re-home other symbols** → proposal.md names
  `_UNSET`/`_unseeded()`/`Box` as out of scope and as the natural follow-on;
  the diagnosis transfers, the decision does not.

## Migration Plan

None applicable. Nothing is published, deployed or versioned by this change:
all four symbols are absent from `__init__.py`, no public name is added,
renamed or removed, and no data or on-disk format exists to migrate. Rollback
is `git revert` of a single commit that touches four `src/` files, three test
import lines and `CLAUDE.md`.

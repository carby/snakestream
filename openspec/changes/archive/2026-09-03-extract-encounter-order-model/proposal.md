## Why

One concept — **the encounter-order model** — is split across two modules,
and neither module is about it. Each half lives where it was first needed
rather than where it belongs:

| Symbol | Lives in | What that module is for |
|---|---|---|
| `Ordering` (PRESERVE/CLEAR/SET) | `sink.py` | "The Op/Sink pair … one push protocol" |
| `is_ordered(chain, upto, initial)` | `sink.py` | as above |
| `OrderDemand` (NONE/IF_ORDERED/ALWAYS) | `execution.py` | "How a composed chain actually runs" |
| `_split_point(chain, demand, ordered_in)` | `execution.py` | as above |

The four are one mechanism, and the code already says so in prose rather than
in structure. `OrderDemand`'s docstring: *"the pair is the whole input to
`_split_point()`, and the two enums are deliberately the same shape read from
opposite ends"*, and it prints a table pairing its own members against
`Ordering`'s — a table it can only write about a type it has to import from
another module. `_split_point()` prints the **same** table again. `Ordering`'s
docstring explains a Java flag fold; `is_ordered()`'s explains the fold itself;
neither has anything to do with `begin`/`accept`/`end`.

Both placements are justified in-source *by import topology, not by concern*,
which is the tell. `is_ordered()`: *"Lives here rather than on `Stream` because
`execution.py` needs it and may not import `stream.py`; the fold is a property
of a list of `Op`s, and `Op` and `Ordering` both live here already."* That
reasoning correctly rules out `stream.py` and then stops one step early — it
never asks whether the fold and the enum should be *anywhere* in the push
protocol's module. `sink.py` is where they landed because it was the module
both other modules could already import.

The cost is legibility, and it is paid by exactly the reader CLAUDE.md's
longest section is written for. "The ordering barrier" is 40 lines explaining
one mechanism; the mechanism's four pieces are in two files, so a reader
following it opens `sink.py` for two of them and `execution.py` for the other
two, and finds each surrounded by machinery that has nothing to do with what
they came for.

**Why now, and why this one.** It is a **module-level move and nothing else**:
the same objects, the same identity comparisons (`op.ordering is Ordering.SET`,
`demand is OrderDemand.ALWAYS`), the same call sites, resolved at import time.
No per-element path is touched, so the `+10% ns/element` threshold governing
that neighbourhood — five consecutive measured rejections in the roadmap's
**Done** — does not apply, the same exemption `collapse-sort-decorate-lanes`
and `collapse-unseeded-accumulation-rule` claimed. Checked against **Done**: it
re-proposes nothing in the rejection log, which contains no module-boundary
item at all. It is also not the roadmap's queued `_guarded()` flag-argument
item, `comparator.py`'s segment-sign 2x2, or `collectors.py`'s per-box dispatch
state; all three stay queued on their own gates, untouched.

## What Changes

- **New module `src/snakestream/ordering.py`**, holding the whole encounter-order
  model and nothing else: `Ordering`, `OrderDemand`, `is_ordered()` and
  `_split_point()`, with a module docstring stating the pairing the two enum
  docstrings currently state twice.
- **`sink.py` loses `Ordering` and `is_ordered()`** and imports `Ordering` back
  for `Op.ordering`'s `ClassVar` default. Its docstring — already an accurate
  description of the push protocol — stops being contradicted by its contents.
- **`execution.py` loses `OrderDemand` and `_split_point()`** and imports both.
  Its module docstring keeps pointing at `_split_point()`, now by module.
- **`ops.py`, `stream.py`, `execution.py`** update imports only. No call site,
  argument, or comparison changes.
- **Three test modules update imports only** — `tests/test_op_protocol.py`
  (`Ordering`, `is_ordered`), `tests/test_unordered.py` (`OrderDemand`,
  `_split_point`), `tests/test_racing_encounter_order.py` (`OrderDemand`).
  A test import following a moved module is expected and in scope; the claim
  this change makes is the narrower one, that the tests change by import line
  and nothing else.
- **`CLAUDE.md`'s "The ordering barrier" section** gains the module pointer and
  drops the two now-wrong location claims: `_is_ordered()`'s fold and
  `_split_point()` are named there without a home today.
- **Circular-import shape, stated up front** because it is the one real
  objection: `ordering.py` needs `Op` for typing only (it reads `op.ordering`
  and `op.order_sensitive` duck-typed), so it imports `Op` under
  `TYPE_CHECKING`; `sink.py` imports `Ordering` at runtime. One direction is
  real, the other is annotations-only under the `from __future__ import
  annotations` both files already carry. Design decision 2 prices the
  alternatives.

Explicitly **not** in scope: `_UNSET`/`_unseeded()`/`Box`, which sit in
`sink.py` on the same import-topology reasoning and are the natural follow-on;
moving `Stream._is_ordered()`; anything on the per-element path; and any
change to what the four symbols mean. Behaviour is identical by construction.

## Capabilities

### New Capabilities

None. No new behaviour is introduced.

### Modified Capabilities

None. Every requirement about encounter order — `stream-ordering`,
`racing-encounter-order`, `stream-execution-model`, `stream-find-first`,
`stream-foreach-ordered`, `sink-protocol` — is written about observable
behaviour and about op/terminal declarations, and none of them names a module
path for `Ordering`, `OrderDemand`, `is_ordered()` or `_split_point()`
(verified: no spec under `openspec/specs/` mentions `sink.py` or
`execution.py`). Nothing a caller can observe changes, so no spec changes
either.

This change therefore sets **`skip_specs: true`** in its `.openspec.yaml`.

## Impact

- **Code:** `src/snakestream/ordering.py` (new, ~120 lines, all of it moved
  prose and four moved definitions); `sink.py`, `execution.py`, `ops.py`,
  `stream.py` (imports, plus the two module docstrings that describe contents
  that changed).
- **Tests:** three import lines. No test body, name or assertion changes; the
  988-test suite must stay green with an unchanged count.
- **Public API:** none. All four symbols are internal — `Ordering`,
  `is_ordered` and `OrderDemand` carry no underscore but are absent from
  `__init__.py`, which exports `Stream` and `PROCESSES` only. No README parity
  row and no Migration-log entry is owed, and that absence is a claim: nothing
  a caller can observe changed.
- **Docs:** `CLAUDE.md` only. README is untouched.
- **Performance:** none, by construction. No benchmark is owed (design
  decision 5).

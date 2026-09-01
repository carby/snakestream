## Why

`_READ_AHEAD` no longer bounds read-ahead. It bounds three things — memory held
by the reorder buffer, latency behind a straggler, and, since
`collapse-find-first-onto-barrier`, how many times a chain callable runs under a
short-circuiting terminal — and only one of them is read-ahead in any useful
sense. The name has been wrong since 2026-08-28 and misleading since 2026-08-31.

Roadmap **Next** item 3 asks for a rename *and* an export, on the argument that
the third thing is visible from user code and therefore public. **This change
takes the rename and declines the export.** Observable is not the same as
public: `find_any()`'s choice of element is observable and spec'd, and nothing
about it is exported. The obligation the item was opened to discharge — that a
caller-visible effect be stated in a spec — is already discharged, by
`stream-find-first`'s "find_first() may invoke a chain's callables more than
once", which `collapse-find-first-onto-barrier` wrote and which already carries
both regimes. What is left is a bad name and an unexplained constant, neither of
which needs a public symbol to fix. Declining the export is not a no-op: it is
written down as a requirement, which is what makes retuning the value free
rather than a compatibility question.

The constant is also unexplained in a way the measurements do not support. Its
comment records that the tuning curve knees **at the worker count** and that
`16 = 4 * PROCESSES`, then hardcodes 16 anyway. So the quantity that governs is
a ratio over the worker count, and a caller who raises `PROCESSES` today gets a
window that does not scale with it.

## What Changes

- Rename `_READ_AHEAD` to a derived pair: `_IN_FLIGHT_PER_WORKER: int = 4` and
  `_in_flight(workers)`, the single site the derivation lives at. The effective
  bound at the default worker count is unchanged (4 * 4 = 16), so no behaviour
  changes for any pipeline that does not alter `PROCESSES`.
- The bound scales with the worker count instead of being a bare number. A race
  across more branches gets a proportionally larger window rather than a
  narrower one per branch.
- `_Window` takes its size as a constructor argument rather than reading a
  module global on every pull. The value is fixed at pipeline start; a rebind
  mid-pipeline no longer takes effect part-way through a race.
- The constant stays **private**. The spec states the bound's existence, its
  scaling and its non-public status; it does not name the number.
- Re-express `_IN_FLIGHT_PER_WORKER`'s measurement table in multiples of the
  worker count, which is the axis the knee actually sits on.
- No public symbol is added, renamed or removed, and no behaviour a caller can
  observe changes. **No migration-log entry** — this is deliberate, not an
  omission.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `racing-encounter-order`: the existing read-ahead requirement keeps its name
  and gains two clauses — the window SHALL scale with the number of branches,
  and its size SHALL be fixed for the duration of a run — plus a scenario for
  the first. A new requirement states that the bound is **not** part of the
  public surface, that `unordered()`/`sequential()` are the levers offered
  instead, and that the value may therefore be retuned without a breaking
  change. That last clause is what this change buys: it makes retuning free
  rather than a question every time.

**`stream-find-first` needs no delta**, which is the finding that shaped this
proposal. Its "find_first() may invoke a chain's callables more than once"
requirement already bounds speculative invocation *and* already states both
regimes — the worker count under uniform latency, the window otherwise. The
roadmap item assumed that obligation was outstanding; it was met by
`collapse-find-first-onto-barrier` in the same change that created it.

**The spec keeps the word "read-ahead" while the code drops it**, deliberately.
The requirement is about *elements pulled but not released*, which is read-ahead
in plain English and accurate. What is inaccurate is naming a **constant**
`_READ_AHEAD` when it governs memory, latency and speculative invocation at
once. The misnomer is internal, so the fix is internal.

## Impact

- `src/snakestream/execution.py` — the constant, `_Window`, `_guarded()`'s
  docstring, and the single `_Window()` construction site inside
  `race_through()`.
- `tests/test_racing_encounter_order.py`, `tests/test_racing_delivery_order.py`,
  `tests/test_find_first.py` — four assertions import the constant to express
  the bound, and one test monkeypatches it to a single slot. All move to
  `_in_flight`.
- `CLAUDE.md` — the ordering-barrier section's read-ahead sentence.
- `roadmap.md` — item 3 closes into **Done**, recording that its answer flipped
  back to "keep it private", and a follow-up is queued (see design.md's
  follow-up section).
- No public API, no README surface, no migration entry.

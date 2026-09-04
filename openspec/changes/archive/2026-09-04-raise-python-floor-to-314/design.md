## Context

See `proposal.md` — Why, and the three archived predecessors for the sequence.

This is the terminal step and, by instruction, the bump alone: it arrives at a
3.14-only floor and spends none of what that unlocks. The design work is
therefore about three things — the mechanical unquoting, what the collapse to a
single matrix leg does to `check.yml`, and drawing the scope line at the point
where free-threading work would begin.

State that shapes it:

- 17 quoted annotations remain. Thirteen are in `comparator.py`, which is the
  only module in `src/snakestream` **without** `from __future__ import
  annotations`; the quotes are the workaround it carries in place of it. They
  reference `KeyComparator` (defined later in the same file) and the aliases
  imported from `type.py`. The other four are in tests.
- Nine `src/` modules and one test *do* carry the future import.
- `check.yml` has three steps gated on `if: matrix.python-version == '3.14'`
  (`ty`, `pip-audit`, the coverage threshold), each with a comment explaining
  why the work is not repeated across interpreters.
- `.readthedocs.yml` pins `python: version: "3.13"` and references a `docs/`
  directory that does not exist.

## Goals / Non-Goals

**Goals:**

- Reach a 3.14-only floor with the tree clean under `target-version = "py314"`.
- Leave `check.yml` honest: no condition that is always true, and no comment
  explaining a restriction that no longer restricts.
- Leave the *next* plan a clean starting point, and say plainly in the specs
  that the matrix shape is what a free-threaded leg will hang off.

**Non-Goals — this is the boundary the instruction draws, and it is worth being
explicit about what falls outside it:**

- `spliterator()`, free-threading, any `3.14t` matrix leg, any change to
  `execution.py` or the racing executor. The floor is the deliverable.
- Removing `from __future__ import annotations` (decision 3).
- Reviving or deleting `.readthedocs.yml` (decision 4).

## Decisions

**1. Unquote via `ruff --fix --select=UP037`, then read the diff.**

Seventeen single-token edits, each removing quotes PEP 649 makes unnecessary.
Scoped to the one rule so the diff is auditable, exactly as the 3.13 step scoped
`UP043`.

There is one thing to check that the fixer cannot: `comparator.py` has no future
import, so its unquoted annotations now rely on PEP 649's deferred evaluation
rather than on PEP 563's stringification. The annotations reference
`KeyComparator`, defined *later in the file* than several of its uses. Under
PEP 649 that resolves lazily and is fine; under an interpreter without it, it
would be a `NameError` at class-body execution. The floor guarantees PEP 649, so
the guarantee is `requires-python` doing its job — but the module must still be
imported and exercised, not merely type-checked, which task 2.2 does.

**2. Remove the three `if:` conditionals, keep the matrix.**

With one leg the conditionals are always true. Worse than redundant, their
comments now assert something false — "only run it once on the newest matrix
version instead of redundantly on every job" describes a matrix that no longer
has other jobs to be redundant across. A reader would spend time working out
which interpreter is being excluded. The steps stay, unconditional; the
conditions and those comments go.

The **matrix itself stays**, at one element. A one-entry matrix looks like
ceremony, and the argument for deleting it is real. It is kept because the very
next plan is expected to add a leg — a free-threaded 3.14 build — and a matrix
is how that arrives without restructuring both jobs. This is stated in the
`install-smoke-test` spec rather than only here, so the shape is a documented
choice and the next change does not have to re-argue it.

*What the next plan inherits, recorded so it is not rediscovered:* a `3.14t` leg
re-raises the question these conditionals answered, since `ty`, `pip-audit` and
coverage would then have two legs to choose between. The answer will probably be
to gate them on the non-free-threaded leg — but that is a decision for the change
that adds the leg, made with the leg in front of it, not guessed at here.

**3. `from __future__ import annotations` stays in all ten files.**

It is tempting to treat it as obsoleted by PEP 649 and sweep it. Two reasons not
to, in this change:

- **Ruff does not ask.** Verified: zero findings at `py314`. Every other edit in
  the four-step sequence has been either a lint finding or a version string, and
  this would be the first that is neither.
- **It is not equivalent, so removing it is a behaviour change.** PEP 563 makes
  annotations *strings*; PEP 649 makes them *lazily evaluated objects*. Removing
  the import changes what `__annotations__` and `typing.get_type_hints()` return
  for those modules. That is a runtime-introspection break of exactly the kind
  the 3.12 step took deliberately for `type.py`'s aliases, with a Migration
  entry and a measured before/after. It deserves the same treatment, which means
  its own change — not a line in a bump.

**4. Raise the `.readthedocs.yml` pin; report the file, do not fix it.**

The pin is below the floor after this change, which is a contradiction inside the
repository, so it is corrected — one line, and consistent with the file's history
of being kept in step with version bumps (`6dc3a22` did exactly this).

The file is also, on inspection, **dead**: it configures a Sphinx build at
`docs/conf.py` and installs `docs/requirements.txt`, and no `docs/` directory
exists. Fixing that means either writing the documentation build or deleting the
config, and both are decisions with consequences outside a version bump. Raising
the pin costs nothing and leaves the repo self-consistent; the deadness is
surfaced in `proposal.md`'s Impact so it becomes a decision rather than a thing
nobody noticed. Deliberately not resolved here.

## Risks / Trade-offs

- **Unquoting breaks `comparator.py` at import time.** → The one real risk in
  this change, since that module relies on PEP 649 rather than a future import.
  Caught by importing and exercising the module, not by `ty`: task 2.2 runs the
  comparator test files specifically, and the full suite covers it again.

- **Dropping the conditionals silently disables a step.** → The failure mode is
  a step that stops running rather than one that fails. Verified by reading the
  workflow after the edit and confirming five steps run unconditionally, and by
  checking the next CI run's step list rather than assuming.

- **A one-leg matrix reads as leftover scaffolding to the next reader.** →
  Mitigated by putting the reason in the `install-smoke-test` spec, where it is
  a stated property of the job, rather than only in this archive.

- **Arriving at a 3.14-only floor commits the project to free-threading before
  it has been demonstrated.** → It does not, and this is worth stating at the
  end of the sequence rather than only at its start. Every step paid for itself
  in deletions — a version fork, a `PERF203` suppression, PEP 695 aliases,
  PEP 696 defaults, and now 17 quotes — and the substrate question is still open
  and still belongs to its own exploration. If free-threading turns out to be
  the wrong answer, the floor is not the thing that was wasted.

## Migration Plan

Single commit; rollback is reverting it. The interpreter break is enforced by
metadata and is loud at install time.

Validate exactly what CI validates: `ruff check .`, `ruff format --check .`,
`pytest`, `ty check src`, `pytest --cov-fail-under=98`. From this change onward
the local interpreter and the entire CI matrix are the same version, so a local
pass is the whole of the evidence for the first time in the sequence — there is
no leg left that only CI can exercise.

## Context

See proposal.md - Why. `_SupportsAdd` and `_C` currently live at the bottom
of `collector.py` (`collector.py:655-659`), directly above the one function
that uses them, `to_collection`. `type.py` already holds every other shared
callable/composite type alias (`Predicate`, `Mapper`, `Supplier`, `Finisher`,
`Combiner`, ...) as the project's established convention for this.

## Goals / Non-Goals

**Goals:**
- `_SupportsAdd` and `_C` live in `type.py`.
- `to_collection`'s signature, behavior, and the identity of the two names
  are unchanged — only their defining module moves.

**Non-Goals:**
- Renaming `_C` or `_SupportsAdd`, or making either public. They stay
  private (leading underscore); `type.py` already carries private
  supporting names alongside its public aliases (none currently, but there's
  no convention against it).
- Widening `to_collection`'s accumulator type to `Any`, the way the other 18
  factories were widened on 2026-08-21. Proposal.md - Why explains why that
  was correctly rejected for this one factory.

## Decisions

**Move both `_SupportsAdd` and `_C` together, as a pair, not just the
TypeVar.** `_C`'s bound is `_SupportsAdd`; leaving the `Protocol` behind in
`collector.py` while moving only the `TypeVar` would split one type
declaration across two files for no reason. `type.py` gains one `Protocol`
import (`from typing import Protocol`) alongside its existing `typing`
import.

**Keep both names private (leading underscore) and unexported.** They are
not part of the public API — callers of `to_collection` never write `_C` or
`_SupportsAdd` themselves, the checker infers `_C` from the argument. Moving
a private name to `type.py` does not change that; `type.py` itself is not
re-exported from `snakestream/__init__.py`.

**Alternative considered: leave `_C`/`_SupportsAdd` in `collector.py`.**
Rejected — this is precisely the case the roadmap item flagged: the last
public collector signature naming a type that lives outside the project's
established convention for shared type aliases.

## Risks / Trade-offs

[A future reader expects every `type.py` name to be public/exported, since
today all of its contents are] → Not a real risk here: Python has no
module-level export list enforcement beyond `__all__` (which `type.py` does
not define), and the leading underscore is the existing convention this
project uses elsewhere for privacy (e.g., private sink and op classes across
`sink.py`/`ops.py`). No new convention is introduced.

[Circular import between `type.py` and `collector.py`] → Not applicable:
`type.py` has no imports from `collector.py` today and gains none: `_C` and
`_SupportsAdd` depend only on `typing`/`collections.abc`, which `type.py`
already imports from.

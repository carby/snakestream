## Why

`_derive()` builds every next stage with `type(self)(self._source, self._close_handlers)`, which re-enters the user's `__init__`. Measured: `MyStream(src).map(f).filter(g).parallel().sorted()` runs the subclass constructor **five times**, and `s.resource is` the original is `False`. CLAUDE.md documents subclassing `Stream` to wrap an I/O-like resource, so the documented use case acquires one resource per pipeline stage and keeps only the last.

Two consequences, one of them not previously recorded:

- **Resource churn, and a conditional leak.** A four-stage pipeline opens five connections and uses one. Whether the four orphans are also *leaked* depends on the subclass's shape: with `on_close()` registered inside `__init__` nothing leaks, because `_close_handlers` is shared by reference and all five handlers land in the same list — the shared list accidentally masks it. A subclass that overrides `close()` instead leaks for real (measured: 3 opened, 1 closed, 2 orphans).
- **The signature contract, which nothing documents.** Passing `(source, close_handlers)` positionally requires every subclass to accept exactly that shape, with an already-normalized `AsyncGenerator` as its first argument. The natural way to write the documented use case — `DsnStream(dsn)` acquiring a connection and calling `super().__init__(conn.rows())` — raises `TypeError: __init__() takes 2 positional arguments but 3 were given` on the first intermediate operation. The documented feature is close to unwritable today.

Java does not have this problem because its derived stages are an *internal* type (`ReferencePipeline.StatelessOp`) holding no resource, and `Stream` is an interface nobody subclasses. snakestream deliberately went the other way — `type(self)` exists to preserve subclass identity across derivation, and `test_a_user_subclass_survives_a_mode_switch` pins that. Having committed to identity preservation, shallow-copying is the only way to keep identity without paying re-construction.

Roadmap **Now** open question 7, found 2026-08-27 while writing `unify-derive-signature` and noted there as out of scope.

## What Changes

- `_derive()` derives via `copy.copy(self)` instead of `type(self)(...)`. Verified: it does not re-enter `__init__`, and it shares `_source`, `_chain`, `_close_handlers` and subclass attributes by reference while copying `_consumed` as `False` — exactly the four assignments `_derive()` makes today, minus a wasted `_accept()` re-normalization of an already-normalized generator.
- **BREAKING (observable, for subclasses only):** a subclass's `__init__` runs **once per pipeline**, not once per stage. Subclass attributes are now shared across all stages by identity rather than re-created per stage. For the documented `on_close()`-in-`__init__` shape this changes 5 acquisitions / 5 releases into 1 / 1.
- A subclass MAY define any `__init__` signature. This is the point of the change as much as the leak is, and is stated and tested rather than left as a side effect.
- `Stream` declares whether it defines `__copy__`. Once `_derive()` depends on `copy.copy`, a subclass overriding `__copy__` becomes load-bearing rather than inert, so the contract must say which it is.
- `test_a_user_subclass_survives_a_mode_switch` asserts `seq.resource == "db-handle"` against a string literal, pinning that the attribute survives rather than that it is the same object. Changing that assertion to `is` turns the test into a reproduction.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pipeline-immutability`: its "Mode switches return a new instance" requirement already says the new instance "SHALL carry the receiver's source, its queued chain, its close handlers and its concrete type" — it never says *by construction*, so this change adds requirements rather than reversing one. Adds: derivation SHALL NOT re-enter `__init__`; a subclass MAY define any `__init__` signature; subclass state is shared per-pipeline rather than per-stage.

## Impact

- `src/snakestream/stream.py` — `_derive()`, one line plus an import.
- `tests/test_execution_model.py` — `test_a_user_subclass_survives_a_mode_switch` tightens to identity.
- Interacts with `stream-close-handling`: with one shared resource per pipeline, the already-shared `_close_handlers` list means one `close()` releases it once, which is the coherent reading. No requirement there changes.
- Does **not** touch `Stream.concat()`, which constructs a base `Stream` and drops subclass identity for reasons of its own — see `concat-carries-characteristics`.

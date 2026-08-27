## Why

`Stream._derive()`'s docstring says it derives a new stream "under the same
executor". Two of its ten callers immediately falsify that. `sequential()` and
`parallel()` cannot say what they mean through the signature they are given, so
they say it afterwards, by hand:

```python
derived = self._derive()
derived._executor = SEQUENTIAL
return derived
```

`_derive()` claims to hold the chain-extension rule "here and nowhere else",
and it does — but the executor rule it leaves on the floor for its callers to
pick up. The result is the only place in `stream.py` where a method writes a
private attribute of an object it does not own, and the only two call sites
that need three statements to do what the other eight do in one.

The fix is one parameter. Both derivation rules then live in the one method
that already advertises itself as their home.

## What Changes

- `_derive()` grows a second optional argument: `_derive(op=None,
  executor=None)`. Both defaults mean *unchanged* — no op yields a plain copy,
  which is what a mode switch derives from; no executor keeps the receiver's.
  The body's one new line is `new_stream._executor = executor or
  self._executor`.
- `sequential()` and `parallel()` collapse to `return
  self._derive(executor=SEQUENTIAL)` / `return self._derive(executor=RACING)`.
  Neither touches a derived stream's fields any more.
- Docstrings redistribute along the same seam. `_derive()` takes on the
  mode-switch mechanics (what an omitted argument means, and that the chain
  passes through by identity rather than being copied). `sequential()` keeps
  the *why* it already carries and that nothing else records: that a mode
  switch must not compose, because composing is what made `.parallel()`
  position-dependent; and that it must not flip in place and return `self`,
  because pipeline-immutability requires the receiver be invalidated.
- The eight intermediate call sites are untouched.

No behaviour changes. `_derive()` is private, no caller passes both arguments,
and the two mode switches produce exactly the streams they produce today.

Explicitly **not** in scope, both raised while exploring this and both
independent of it:

- Splitting `_derive()` into `_extend(op)` / `_switch(executor)` over a shared
  `_copy()`. Considered and declined: it buys an honest `Stream[T]` return on
  the mode-switch path where the unified method must return `Stream[Any]`, at
  the cost of a third method whose docstring has to explain that it decides
  nothing.
- Widening `Stream.__init__` to accept `chain` and `executor` so a derived
  stream is fully formed at construction. Declined: `_derive()` builds through
  `type(self)(...)`, so every parameter on `__init__` becomes an obligation on
  user subclasses, which silently lose their chain if they fail to forward it.
- That `type(self)(...)` re-enters a subclass's `__init__` on *every*
  derivation — five times for a three-op pipeline plus one mode switch. For the
  resource-wrapping subclass CLAUDE.md documents, that acquires five resources
  and keeps one. Real, and worth its own change; it is a behavioural fix with
  its own spec scenarios, not a signature cleanup.

## Why this is not a revert

This is the fourth pass over this cluster, and the roadmap requires each one to
say what it is not undoing. The 2026-08-26 `collapse-derive-wrappers` entry
landed today's shape and recorded two things this change must answer to.

**It named the double assignment and accepted it knowingly:** "`_executor` is no
longer assigned exactly once per instance — the copier sets it and the mode
method overwrites it. Unobservable today (no `await` between the two
statements, the instance has not escaped), and recorded so that adding an
`await` to `_derive()` is recognised as breaking it." This change does not
dispute that reasoning; it removes the condition the reasoning was needed for.
`executor or self._executor` assigns once, so the tripwire about a future
`await` in `_derive()` stops guarding anything and can retire with it. That is a
debt being paid, not a judgement being reversed.

**It sited the full docstring on `sequential()` for a reason that this change
dissolves:** the entry explains the warning against an in-place flip moved
there "because the new body is a working template for the move
`pipeline-immutability` forbids: delete one line and `derived._executor =
RACING` becomes `self._executor = RACING; return self`." After this change
`sequential()` is `return self._derive(executor=SEQUENTIAL)` — there is no local
to reassign and no line to delete, so the template is gone. The warning stays on
`sequential()` regardless: the temptation it describes is a property of what a
mode switch *is*, not of how its body happens to be spelled, and the next person
to rewrite these two methods needs it as much as the last one did.

**What must survive, from the same entry:** the `Op`-taking ergonomics at the
eight op call sites (`return self._derive(_MapOp(mapper))`), which this change
does not touch; `op is not None` rather than `if op`, for the `_UnorderedOp`
truthiness trap; and `_derive()` remaining a method on `Stream` rather than
moving beside `execution.py`'s helpers, since it is the one member of that
family that needs an instance and it enforces the `pipeline-immutability`
invariant from inside the class.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a pure refactor of a private method's signature: the
`pipeline-immutability` requirements governing what `sequential()` and
`parallel()` do — that they return a distinct object, that the queued chain
survives, that the receiver is invalidated — all continue to hold unchanged,
and no spec names `_derive()`. `.openspec.yaml` therefore sets
`skip_specs: true`.

## Impact

- `src/snakestream/stream.py` only: `_derive()`, `sequential()`, `parallel()`.
  Roughly a net −4 lines of code and a redistribution of two docstrings.
- No public surface change; no README parity-table entry to update.
- Existing tests should pass untouched. `tests/test_execution_model.py` already
  covers what must not regress: that a mode switch returns a distinct object,
  carries the queued chain without composing it, preserves subclass identity,
  and is position-independent.

## Context

See `proposal.md` — Why. Four independent findings; three of them are
one-line edits whose only design question is "is it really behaviour-neutral?",
and one — `_extend` — touches all eight intermediate operations at once and has
a typing decision inside it.

Two constraints shape everything below.

**The tripwire.** The full suite must pass with **no test file edited**. That is
this change's entire verification story: there is no new behaviour to assert, so
the only evidence the refactor is correct is that 546 existing tests still pass
untouched. Any edit that makes a test need changing is out of scope by
definition, not a judgement call.

**The sequencing debt.** Stories 1 and 2 of this batch just landed in
`stream.py`. Story 3 was placed last of the three precisely because `_extend`
rewrites eight adjacent one-liners there — the widest diff in the file. It is
taken now that those edits are in, so the diff is against settled code.

## Goals / Non-Goals

**Goals:**

- One home for the chain-extension rule, so `self._chain + [op]` and
  "carry the executor forward" are written once rather than eight times.
- Each intermediate operation reads as the one thing it is about: the `Op` it
  queues.
- `stream.py` fully annotated, so nothing in it depends on `ty`'s inference.
- Remove the two lines that assert nothing (`_ForEachSink._finish`) and the two
  that use the less-precise `asyncio` spelling.

**Non-Goals:**

- No change to `_derive()` itself, to `_check_not_consumed()`, or to the
  consumed-on-extend semantics. `_extend` is a caller of `_derive`, not a
  replacement for it.
- No touching `_derive_executor()` (`parallel()` / `sequential()`). Those
  deliberately pass `self._chain` **unchanged** with a different executor, which
  is the opposite of what `_extend` does. Folding both into one helper would
  re-couple the two things story-batch history separated.
- No widening `_extend` into anything that also builds the `Op`. The `Op`
  constructors have eight different signatures.
- No benchmark harness run. See Decision 4.

## Decisions

### 1. `_extend(op)` takes a built `Op`, not the pieces to build one

`_extend(self, op: Op) -> Stream[Any]` returning
`self._derive(self._chain + [op], self._executor)`.

The alternative considered was `_extend(op_cls, *args)`, constructing the `Op`
inside the helper. Rejected: the eight `Op` constructors take between zero and
two arguments of unrelated types (`_DistinctOp()` takes none, `_SortedOp` takes
a comparator and a flag), so the helper's signature would degrade to
`*args: Any` and lose exactly the type information the call site has. Passing a
constructed `Op` keeps each call site's arguments checked against its own `Op`.

`_extend` also does not run `_check_not_consumed()` itself — `_derive()` already
does it as its first statement, and duplicating the guard one frame up would
make it ambiguous which one is load-bearing.

### 2. The eight `cast()` wrappers go away, and that is the point

Today each op is
`cast("Stream[R]", self._derive(self._chain + [_MapOp(mapper)], self._executor))`.
The `cast` is there because `_derive` returns `Stream[Any]` — it cannot know
that `map` produces a `Stream[R]`.

That does not change with `_extend`, but the `cast` was never necessary: `Any`
is assignable to any declared return type, so `def map(...) -> Stream[R]:
return self._extend(_MapOp(mapper))` typechecks with no cast at all. Confirmed
against `ty` (the version CI runs on the 3.14 leg) on a reduced model of the
`Generic[T]` / `_derive -> Stream[Any]` shape before committing to it.

Alternative considered: keep the casts for documentation value. Rejected —
`cast` on an `Any` is a no-op that reads like a real narrowing, and the return
annotation already states the type. Dropping them takes each method to one
short line, which is most of the legibility win. The `cast` **import** stays;
`sequential()`, `parallel()` and `iterate()` still use it.

The verification here is `ty check src` passing, not the test suite — `cast` is
erased at runtime, so no test can distinguish the two forms.

### 3. `_ForEachSink._finish` is removable because the container is provably `None`

`TerminalSink._finish` is `return container`. `_ForEachSink._create_container`
is `return None`, and `_ForEachSink` never assigns `self._container` anywhere
else, so `end()` calls `_finish(None)` and stores `None` either way. The
override returns `None` for the one input on which the base already returns
`None`; deleting it is an identity, not a behaviour change.

This is worth writing down because the override *looks* load-bearing: a reader
who assumes `for_each` must discard a result will read it as the thing doing
the discarding. It is not — `result()` returning `None` for `for_each` comes
from the container being `None`, which `_create_container` decides.

Alternative considered: delete `_create_container` instead and keep `_finish`.
Rejected: `_create_container` is `@abstractmethod` on `TerminalSink`, so it has
to stay.

### 4. `create_task` is a substitution, not a rewrite — and that keeps it off the gate

Both sites pass `branch.__anext__()`, where `branch` is a
`stream_through(...)` async generator. `__anext__()` on an async generator is
always a coroutine, so `ensure_future`'s `isfuture` / `iscoroutine` /
`isawaitable` ladder always lands on the coroutine arm and calls
`ensure_future`'s internal `loop.create_task`. `asyncio.create_task` is the same
call without the ladder, and is what the stdlib documents as preferred for a
coroutine.

This is the only per-element site in the change — it runs once per element per
racing branch. It is exempt from the benchmark gate because the object graph is
byte-for-byte identical: same task, same loop, same generator; the only
difference is a few type checks not performed. **The exemption is conditional on
the diff staying a one-word substitution at each of the two sites.** If either
site needs anything else — a name binding, a different await point, an
`asyncio.TaskGroup` — the exemption lapses and the harness has to run. That is a
tripwire, not a preference.

Alternative considered: also converting the `in_flight` dict to a `TaskGroup`
or `asyncio.wait`. Rejected — out of scope, and `race_through`'s comment already
records why the task-keyed dict is the shape it is (O(1) completion-to-branch
mapping, nothing rescanned per element).

### 5. Four commits, one per finding

Each finding is independent and lands separately, matching how story 2 was
taken. A bisect then lands on one finding rather than on "story 3". The
`_extend` commit is the only one with a diff worth reading; the other three are
one- and two-line commits whose message carries the reasoning above.

## Risks / Trade-offs

- **`_extend` is applied to `flat_map` mechanically, dropping its pre-call
  guard** → `flat_map` is the one intermediate op with a body before the
  return (`iscoroutinefunction(flat_mapper)` raising `StreamBuildException`).
  `_extend` replaces its return expression only. The existing
  `flat_map`-rejects-a-coroutine-function test is the guard, and it must pass
  unedited.

- **A `cast` removal silently widens a return type** → the eight declared return
  types (`Stream[T]` vs. `Stream[R]`) are not all the same and must be
  preserved verbatim per method; only the expression inside changes.
  `ty check src` is the gate, and it runs in CI on the 3.14 leg.

- **`_ForEachSink._finish`'s deletion is misread later as a lost feature** →
  Decision 3's reasoning goes in the commit message, so `git log -S_finish`
  answers the question without re-deriving it.

- **The `create_task` swap turns out to matter under load** → the two sites are
  reverted independently of the rest; they are the last commit and touch one
  file no other finding touches.

- **Widest-diff-in-the-file risk** → mitigated by sequencing (stories 1 and 2
  are landed) and by the tripwire: eight mechanical replacements that change no
  behaviour cannot need a test edit, so an edited test means stop.

## Migration Plan

None. No public name, signature, or behaviour changes; nothing is deprecated
and there is nothing to roll forward. Rollback is a revert of any individual
commit, since the four are independent.

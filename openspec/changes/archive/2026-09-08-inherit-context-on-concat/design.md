## Context

See `proposal.md` — Why, and `roadmap/items/concat-inheriting-context.md` for the
full argument. What matters for the approach:

- There are exactly two ways a stream comes into being, and they match Java's two
  `AbstractPipeline` constructors: from a source (`Stream(source)`, public here
  where Java's is not), and from another stream (`_derive()`, which copies where
  Java links stages). Java keeps the close action and the parallel flag on the
  *source stage*, shared downstream; `copy()` gets the same sharing without a
  stage graph, which is why `_derive()` assigns only what differs and needs
  nothing handed to it.
- `concat()` fits neither. It is a third shape: **from a source, with context
  inherited from streams that are not its parent.** It cannot copy an operand —
  the result is a plain `Stream` even when both operands share a subclass, since
  `type(a)` and `type(b)` have no principled tie-break (`stream-concat`) — and it
  cannot construct plainly, because it owes the operands their handlers and mode.
- Pipeline state is read only inside `stream.py`. The chain reaches
  `execution.py` by value, once per terminal, never per element.

## Goals / Non-Goals

**Goals:**

- `Stream(source)` one parameter wide, matching what README already documents.
- One named operation where `concat()` currently uses three mechanisms.
- The concatenation's handler list independent of its operands' in both
  directions, stated and tested.

**Non-Goals:**

- Changing what `concat()` produces. Every observable guarantee is unchanged.
- Touching `_derive()`. It already solves same-lineage derivation.

## Decisions

### 1. The constructor takes a source and nothing else

The rule to land, which is already 80% true:

> The constructor takes a source. Every other piece of stream state is set by the
> code that knows it — `_derive()` by copying, `concat()` by inheriting,
> `on_close()` by appending.

Both internal paths are construct-then-mutate, and that is not the problem.
`_derive()` reads as principled because the mutation sits inside a named
operation whose docstring states the rules; `concat()` does the same kind of
mutation in the open. The fix is a name, not a different mechanism.

**Alternative rejected:** keyword-only (`Stream(source, *, close_handlers=None)`).
A half-measure — the parameter stays in a signature README now documents, and the
three-mechanism asymmetry inside `concat()` is untouched, which is the actual
defect.

### 2. `_concatenate(a, b)` is binary, not variadic

The roadmap item sketched `_inheriting(*operands)`. Binary is the better call and
this change corrects that sketch. `concat()` is the only caller and is itself
binary, matching Java's `Stream.concat(a, b)`; `__add__` delegates to it. A
variadic signature would be generality nobody asked for, in a change whose whole
point is removing a parameter nobody uses, and it forces comprehensions where two
named operands read plainly:

    def _concatenate(self, a: Stream[Any], b: Stream[Any]) -> Stream[T]:
        self._close_handlers = a._close_handlers + b._close_handlers
        self._executor = FORK_JOIN if a.is_parallel() or b.is_parallel() else SEQUENTIAL
        return self if (a._is_ordered() and b._is_ordered()) else self.unordered()

The bodies of the three lines are the three statements `concat()` has today,
unchanged — this moves them behind a name rather than rewriting them.

### 3. It returns a stream rather than mutating in place

Two of the three inherited things are assignments; the third is not. Ordering is
positional and has to occupy a position in the chain, so it arrives as a
`.unordered()` derive — `concat()`'s existing docstring already explains why, and
that reasoning is unchanged. A derive returns a new stream and consumes the
receiver, so `_concatenate()` cannot be a pure mutator.

Consuming the receiver is safe here and only here: the stream `_concatenate()` is
called on was constructed inside `concat()` and has never been handed to a
caller, so `pipeline-immutability` has nothing to say about it. That is worth
stating in the docstring, because the rule it appears to break is one this
codebase enforces everywhere else.

### 4. Assignment order is load-bearing

`_executor` must be set **before** the ordering derive, not after. `_derive()`
copies `_executor` by value, so an executor assigned to the receiver after
`.unordered()` has already derived would be set on the consumed stream and
silently lost. `_close_handlers` happens to survive either way, being shared by
reference — which makes the bug worse, not better: half the state would carry and
half would not, and the failing half is mode, which no close-handler test would
notice.

### 5. The reverse aliasing direction gets a scenario

`stream-concat` specifies today that registering on an operand after `concat()`
does not reach the concatenation. The reverse — registering on the concatenation
does not reach the operands — is unspecified and untested, and it is exactly what
a plausible implementation of this change loses: assigning `a._close_handlers`
instead of building a new list from both satisfies every existing scenario while
aliasing the two. The `+` is load-bearing and nothing currently says so.

### 6. `_Stage` is rejected on cruft, not performance

Recorded here as well as in the roadmap item because the reason it was *not*
rejected is the part a later reader would otherwise redo. Pipeline state is read
only in `stream.py` and the chain crosses to `execution.py` by value once per
terminal, so a state object's extra allocation lands once per `_derive()` call —
per stage, not per element. Every regression this repo has measured and acted on
was per-element (+125% on `count()` from composing then draining; ~3% on the
segment-sign twins). This is not in that class.

It is rejected for buying nothing over `copy()`, which already carries shared
context forward including subclass attributes it knows nothing about, and which
never has to answer the question a `_Stage` would force: which attributes are
pipeline state. `_consumed` is per-reference, `_size_hint` belongs to the raw
source, and subclass attributes belong to nobody in particular. It becomes the
right answer when a second parentless construction site exists; today there is
one.

## Risks / Trade-offs

- **A loud break on a public constructor.** `Stream(source, [handler])` raises
  `TypeError`. → In the safe direction: it cannot be missed, and `on_close()` is a
  one-for-one replacement that already exists and is already documented. A README
  Migration entry states it.
- **Assignment order (Decision 4) fails silently if got wrong** — mode is lost, no
  handler test notices. → An explicit test that a concatenation of two parallel,
  unordered operands is still parallel, so the two interact in one assertion.
- **Deleting a test can look like losing coverage.**
  `test_construct_with_initial_close_handlers` tests a parameter that will not
  exist; keeping it in any form would mean keeping the parameter. → Replaced by
  the `TypeError` scenario in the delta, which guards that the argument is
  rejected rather than silently ignored.
- **A subclass may have been passing handlers up.** `derive-without-reinit`
  documented that a subclass need not accept `(source, close_handlers)`; it never
  forbade it. → That freedom is unnarrowed — any `__init__` signature still works;
  what goes is the base class accepting the second argument. The subclass calls
  `super().__init__(source)` and `on_close()`.

## Migration Plan

One commit. Source, tests, both spec deltas, the `stream-close-handling`
`## Purpose` edit, README, and the roadmap item's closure into `decisions.md`.

The `## Purpose` edit is easy to miss: it names "an explicit `close_handlers`
argument" and is not reachable through a delta, so it is edited directly in
`openspec/specs/stream-close-handling/spec.md` and is its own task.

Rollback is a revert; no persisted state is involved.

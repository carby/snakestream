## Context

See proposal.md — Why. The state that shapes the approach: `sort.py` is 124 lines
holding two unrelated concerns with a dispatcher between them, and it has exactly
three importers inside `src/` and none outside it.

```
sort.py today                       imported by
  check_comparator_result_type  ->  terminals.py (indirectly), collector.py (indirectly), sort.py itself
  is_new_extremum               ->  terminals.py:9, collector.py:11
  _checked                      ->  sort.py only
  sort                          ->  ops.py:15
  merge_sort / _merge           ->  sort.py only
```

The dependency runs one way already: the sorting functions call the semantics
functions (`_checked` and `_merge` both call `check_comparator_result_type`);
nothing in the semantics half calls anything in the sorting half. That is what
makes the split a move rather than a redesign — there is no cycle to break and no
shared mutable state to thread.

Two constraints bound the work. `ty` runs on the 3.14 leg and the module is mostly
unannotated, so anything added must type-check. And the `branch-coverage-gate` sits
at 98%: it is what caught story 4's unreachable ladder, so it is the instrument that
will confirm a pure move added no unreached line.

## Goals / Non-Goals

**Goals:**

- Each of the two modules names exactly what is in it, so a reader following
  `terminals.py:9` lands somewhere that claims to be about comparators.
- The move is byte-for-byte where it can be: same names, same signatures, same
  bodies, same order within each module.
- `ty` sees no unannotated function in `src/snakestream/` when this lands.

**Non-Goals:**

- Renaming, resignaturing or reimplementing any moved function. `is_new_extremum`
  keeps its name even though `comparator.py` would allow a shorter one — a rename
  would put a second reviewable thing in a change whose whole value is being
  obviously equivalent.
- Touching `ops.py`'s call site or `_SortedSink.end()`. Its import (`from
  snakestream.sort import sort`) and its comment (which points at `sort.py`) are
  both still correct after the split, which is itself evidence `sort()` landed on
  the right side.
- Any performance work. Nothing here is on a per-element path, and the
  2026-08-25 batch's benchmark gate is spent (roadmap: "Do not spend a harness run
  on the two that remain").
- Re-exporting either module from `__init__.py`. Both stay private.

## Decisions

### 1. Two modules, not one

**Decided by the user, 2026-08-25.** The alternative was folding everything into a
single `comparator.py` — the literal reading of the roadmap row, and defensible on
the grounds that `comparator-contract` governs all five functions.

Two modules wins because it fixes the reported defect rather than renaming around
it. The complaint is that `terminals.py` and `collector.py` import comparator
semantics from a module named `sort`; one big `comparator.py` would leave `ops.py`
importing a sort dispatcher from a module named `comparator`, which is the same
misdirection pointed the other way. Split, each importer gets a module whose name
is accurate for what it takes from it, and the one-way dependency above becomes
visible as an import edge instead of being implicit in one file's ordering.

The cost is a ~35-line module. That is acceptable here because `comparator.py` is
not a fragment of a larger thing — it is the complete implementation of a named
spec (`comparator-contract`), which is the same standard `exception.py` and
`type.py` already meet at comparable size.

### 2. `sort()` lands in `sort.py`

This is the question the roadmap row left open. `sort()` is the seam: it is a sort
entry point, but its whole job is deciding what a *comparator* allows, and it calls
`check_comparator_result_type` directly.

It goes with the sorting half, on the rule that **the seam belongs with the caller,
not the definer.** `sort()` consumes comparator semantics the same way `_checked`
and `_merge` do; putting it in `comparator.py` would mean `comparator.py` imports
nothing but still owns a function whose only caller is `ops.py`, and `sort.py`
would then be `_checked` plus `merge_sort` with no entry point — a module no one
imports directly.

The confirming test is `ops.py:15`: `from snakestream.sort import sort` reads
correctly today and reads correctly after the split, unchanged. A decision that
requires no edit at the only external call site is the one that matched what was
already there.

### 3. Module order: semantics first, then the split

`comparator.py` gets the two functions in their current relative order
(`check_comparator_result_type`, then `is_new_extremum`, which calls it).
`sort.py` keeps `_checked`, `sort`, `merge_sort`, `_merge` in their current
relative order. Nothing is reordered, so `git`'s rename detection and a reviewer's
eye both see a move.

`is_new_extremum`'s docstring references `check_comparator_result_type` and
`_checked`'s references `is_new_extremum` ("the same trick is_new_extremum uses
above"). After the split "above" is false in `_checked` — it is now in another
module. That one phrase is corrected; every other docstring is moved verbatim.

### 4. Annotations: `merge_sort` and `_merge`, via a new `AsyncComparator` alias

**Amended during apply, user-approved. As first written this decision was wrong
on a checkable fact and has been rewritten.**

The original text said to annotate both with `Comparator`, on the reasoning that
the union is a safe supertype: the honest annotation would narrow to the awaitable
arm, but adding a split alias to `type.py` was a different story, so the union
"is accurate as a supertype, passes `ty`, and does not pretend to a precision the
codebase does not yet express."

It does not pass `ty`. `Comparator` is `Callable[[T, T], int | Awaitable[int]]`
and `_merge` awaits it unconditionally, so annotating the parameter turns the
await into an error:

```
error[invalid-await]: `int | Awaitable[int]` is not awaitable
  --> src/snakestream/sort.py:87:22
```

The union is not a safe supertype *here*, because the body does something only the
narrow arm supports. While the function was bare `ty` inferred nothing and stayed
silent; annotating is what surfaced it. Nothing else in the codebase hit this
because every other comparator await goes through `_maybe_await`/`AsyncDispatch`,
which return `Any` — `_merge` is the only site awaiting a `Comparator` directly.

`type.py` therefore gains one line beside `Comparator`:

```python
AsyncComparator = Callable[[T, T], Awaitable[int]]
```

`merge_sort` and `_merge` take `AsyncComparator`, and `sort()`'s two reroutes pass
`cast("AsyncComparator", comparator)`. The casts sit exactly where the narrowing is
proved at runtime — immediately after `is_async_callable` returns true, or after the
trial comparison returns an awaitable — so they record a real fact rather than
silencing the checker. That placement is the reason this is preferable to a
`cast("Awaitable[int]", ...)` inside `_merge`'s inner loop, which was the
alternative considered: it would state the narrowing at the least informative point
and put a cast on the per-comparison path.

This makes `type.py` a fourth touched file, which the original design excluded.
Accepted deliberately: the alias is a composite callable type, and `type.py` is
where those live rather than inline in a consumer.

## Risks / Trade-offs

- **A missed import leaves a stale `snakestream.sort` reference** → `ruff` catches
  an unused import and `ty` catches an unresolved one, but neither catches an
  import that still resolves because `sort.py` still exists. Mitigation: after the
  move, `grep -rn "from snakestream.sort import" src/` must return exactly one
  line, `ops.py:15`, and that string is the task's own check rather than a review
  hope.

- **The move is not actually byte-for-byte and no test notices** → the suite is the
  weak instrument here (it passed through story 4's dead ladder); the coverage gate
  is the strong one. Mitigation: `uv run pytest --cov-fail-under=98` must hold at
  the same 98.05% it sits at now. A pure move cannot move coverage; a number that
  drifts means something other than a move happened.

- **The story's tripwire fires** — the roadmap states story 5 must touch no test at
  all → if a test edit turns out to be needed, that is the signal the change went
  wider than the story, and it stops for a decision rather than being absorbed.
  Same handling story 4 gave its one added test: flagged and approved, not folded in.

- **Two modules where one would do** → accepted per Decision 1. If `comparator.py`
  never grows past its two functions, the split still pays for itself at every
  import site, which is where the confusion was.

## Migration Plan

Not applicable. Both modules are private and unexported; nothing outside `src/`
imports either name, so there is no deprecation window and no compatibility shim.
Rollback is `git revert` of a single commit.

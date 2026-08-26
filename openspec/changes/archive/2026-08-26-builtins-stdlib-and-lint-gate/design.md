## Context

See `proposal.md` — Why. Two constraints shape the approach.

**The floor is 3.10.** `anext()`, like `aiter()`, arrived in 3.10, so part (a)
needs no version fork. Anything that would need one (the parked
`ExceptionGroup` question in the roadmap's notes) is out of scope here.

**Only part (f) has judgement in it.** Parts (a)-(e) are each a single
mechanical rewrite whose correctness is visible in the diff. Part (f) is a
config change whose cost lands on *future* diffs, so the reasoning for each
family, and for each of the two suppressions, has to be recorded rather than
inferred from a `--select` line. The trial run behind it (2026-08-25, over
`src/`) found nine items total; the six families' worth of cleanup is parts
(b)-(e) of this same change, which is why the two halves ship together.

`ty` runs over `src` in CI and must stay clean — that is the check that part
(d)'s narrowing of `Mapper` actually holds.

## Goals / Non-Goals

**Goals:**
- Land (a)-(e) as behaviour-preserving rewrites with **no test file edited**.
- Turn (f) on with every finding either fixed by (b)-(e) or suppressed with its
  reason at the site.
- Leave the widened selection passing clean, so the next diff inherits a green
  gate rather than a backlog.

**Non-Goals:**
- **`tests/` is excluded.** The same trial over `tests/` found 61, dominated by
  style (22 `SIM300`, 11 `B011`/`PT015`). That is a separate story if it is
  wanted at all. The one part worth revisiting on its own merits — `PT011`'s
  three `pytest.raises(Exception)` sites, now that `StreamException` exists —
  is deliberately left for a later change rather than smuggled in here.
- **No behaviour change.** ~~Every site touched runs once per import, per
  stream construction, per composition, or per collection.~~ **Wrong, corrected
  during apply:** part (a)'s three sites are per-element, and `_finish_groups`
  runs at `end()`. Part (a) was therefore measured (Decision 1: ~13% faster);
  everything else in the change is genuinely once-per-import/construction/
  composition/collection and needs no harness run.
- Not re-opening the three measured rejections in the roadmap's **Done** log
  (the `CallSite` dispatch wrapper, collapsing the terminals onto collectors,
  the bridge-buffer flush dedup), nor the parked `ExceptionGroup` question.

## Decisions

### 1. `anext()` at all three sites, not just the two beside `aiter()`

`race_through` already calls `aiter(source)` once, deliberately, with a comment
explaining why it cannot be inside `_guarded()`. The two `branch.__anext__()`
calls sit within twenty lines of it; `_guarded`'s `source.__anext__()` is the
same construct one function away. Converting two of three would leave the
inconsistency worse than it is now, so all three go. The `aiter()` comment
stays exactly as it is: it explains *arity* (one iterator shared), which the
builtin swap does not touch.

*Alternative considered:* leave `_guarded` alone since it is not in the trial
run's findings (no rule flags `__anext__()`). Rejected — the whole point of the
story is that these are the same construct.

*Correction, made during apply:* all three of these sites **are** per-element,
contrary to the roadmap's claim (repeated in Non-Goals below) that
`_finish_groups` is the only per-element neighbourhood the story touches. That
made the swap worth measuring rather than asserting. Measured 2026-08-26 over
300k elements, five reps, both orderings: `anext(it)` **69ms** best / 70ms
median against `it.__anext__()` **79ms** best / 81ms median — roughly 13%
faster, about 35ns per element. The builtin's type-level lookup beats the
instance attribute lookup. So the per-element hunk stands as a small
improvement, not a regression.

### 2. `Mapper` loses `None` rather than reordering it

`RUF036` only asks that `None` move to the tail of the union. For `Consumer`
and `BiConsumer` that is the whole fix: `None` is genuinely their return type.
For `Mapper` the reorder would preserve a widening nobody can justify —
`Callable[[T], R | None | Awaitable[R | None]]` makes every `.map()` result
optional, when a mapper that returns `None` is already expressible as `R = None`.
Confirmed with the user; the delta spec on `generic-stream-typing` records it,
since `map()`'s typed result is externally visible.

*Alternative considered:* reorder and add a comment explaining the optional.
Rejected — there is no explanation to write; the arm is redundant, not subtle.

*Risk:* `ty check src` is the only thing that will tell us whether any internal
call site was leaning on the optional. See Risks.

### 3. `_TO_LIST` as a module-level default, not a `noqa`

`B008` fires on `grouping_by`/`partitioning_by`'s `downstream: Collector = to_list()`.
It is not the classic mutable-default bug — `Collector` holds four callables
and no per-collection state, and its docstring says so — but that argument
lives in a different class in a different part of the file, and a reader has to
go find it to rule the bug out. A module-level `_TO_LIST = to_list()` states it
where the default is written and costs one line. Confirmed with the user.

*Alternative considered:* `noqa: B008` with the reason inline. Rejected as the
weaker of two acceptable answers; what matters is that neither answer is
"drop the rule".

### 4. The two false positives are suppressed at the site, with the reason

- **`B004` at `callable_dispatch.py:14`** wants `callable(fn)` in place of
  `getattr(type(fn), "__call__", None)`. The line is not asking whether `fn` is
  callable — it is reaching for the *class-level* `__call__` to ask whether
  **that** is a coroutine function, which is the only way `is_async_callable`
  classifies an object with an `async def __call__` correctly. Verified on
  3.14.5: `inspect.iscoroutinefunction` already handles `functools.partial` and
  `inspect.markcoroutinefunction`, but returns `False` for an async-`__call__`
  instance. Taking the rule's advice would be a silent correctness regression.
- **`PERF203` at `stream.py:192`** is the close-handler loop, whose entire
  contract is to catch per handler and keep going so that every handler runs.
  The rule objects to `try`/`except` inside a loop; here that *is* the feature,
  pinned by the `stream-close-handling` spec and by
  `test_close_with_multiple_raising_handlers_runs_all_and_raises_first`.

Both get a rule-scoped `noqa` carrying the reason, per the new
`lint-rule-selection` requirement. A blanket per-file ignore would hide future
genuine findings in the same file.

### 5. `RUF023` is taken as the auto-fix it is

`Collector.__slots__` at `collector.py:42` is unsorted. Cosmetic, auto-fixable,
and the tuple's order carries no meaning (it is not a `dataclass` field order).
Sort it and move on.

### 6. Family selection: the trial run's list, unchanged

`ASYNC,B,SIM,RUF,PERF,C4,RET,PIE,FURB,PLR,PLW` is exactly the set that was
trialled and produced nine findings. Adding a family not in that trial would
mean turning on a rule whose cleanup cost has not been measured, which is the
thing this change is set up to avoid. `mccabe.max-complexity = 10` stays.

*Note on `PLR`:* it carries the magic-value and argument-count rules that are
noisy in many codebases; the trial produced none of them here, so it goes in as
trialled. If a future diff hits one, the answer is that diff's problem to argue,
which is the intended cost model for (f).

### 7. `_finish_groups`: comprehension **and** hoisted invariant

The rewrite is a two-part fix that has to land together. `finisher is not None`
is loop-invariant — `downstream.finisher` is read once before the loop today,
and the branch cannot change per key. Hoisting it out and picking the
comprehension on the outside of that branch keeps the `await` per key and drops
the per-key test:

```
if finisher is None:
    return dict(groups)
return {key: await _maybe_await(finisher, sub) async-for-equivalent ...}
```

The exact shape (async dict comprehension over `groups.items()`) is settled in
tasks.md; what the design pins is that the invariant leaves the loop rather than
the comprehension merely wrapping the existing branch.

## Risks / Trade-offs

- **Dropping `None` from `Mapper` breaks an internal call site** → `uv run ty
  check src` catches it before the suite does. If a site genuinely needs the
  optional, that site declares `R` as optional itself; the alias does not carry
  it for everyone.
- **`snakestream.dist_name` is a real, if accidental, removal** → it is
  importable today (verified 2026-08-26) and referenced nowhere in `src/`,
  `tests/`, or `README.md`. It was never documented or exported deliberately.
  Recorded in the proposal's Impact so it is not a surprise at archive time.
- **The widened selection is a tax on future diffs** → that is the point, and
  the trial run bounds it: nine findings across twelve modules. The mitigation
  is that the cost is paid *now*, in this change, rather than discovered by
  whoever next touches `collectors.py`.
- **A `noqa` rots** → both carry their reason inline, so a future reader can
  re-evaluate them against the code rather than deleting them blind. Neither is
  a file-level ignore.
- **`PERF203`/`B004` suppression hides a future real finding on those lines** →
  accepted; both are rule-scoped to a single line, and both lines are small and
  spec-pinned.

## Migration Plan

Not applicable — no data, no persisted state, no deprecation window. The one
removed name (`snakestream.dist_name`) is undocumented and unused.

## Open Questions

None. The two that existed — `Mapper`'s `None` arm, and `B008`'s fix shape —
were put to the user before the specs were written and are recorded as
Decisions 2 and 3. The `ExceptionGroup` question in the roadmap's notes is
deliberately *not* an open question of this change: it is parked there awaiting
its own explicit call.

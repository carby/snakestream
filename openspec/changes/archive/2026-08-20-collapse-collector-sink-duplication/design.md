## Context

See proposal.md — Why. Four independent collapses, all behavior-neutral, all
private-name-only. What shapes the design is less the duplication itself than
three constraints the code already carries:

- **The per-element path is benchmarked and defended.** `add-callsite-dispatch`
  (archived, rejected) measured +32-75% for putting a *call* on `accept()`.
  Anything here that would add one is out.
- **`callable_dispatch.py` already documents a canonical dispatch shape** in a
  module-level comment, describing the exact five-branch pattern the 26 call
  sites hand-copy. That comment is currently unenforceable prose.
- **`collector.py:65-69` defends the six summing/averaging names**, on the
  grounds that Java distinguishes by primitive and Python's numeric tower does
  not. That argument is sound and survives this change; it has only been
  misread as also defending six bodies.

Part (c) partly overlaps roadmap item 2 (the `Collector` redesign), which will
change `downstream`'s signature. The extracted helper survives that change, so
doing it here is not throwaway work.

## Goals / Non-Goals

**Goals:**
- One body per distinct behavior in `collector.py`, with the six public
  summing/averaging names and the two public grouping names unchanged.
- One statement of the dispatch-classification triple, shared by the eight
  sinks that hand-copy it.
- `StatefulOp` expressed as what it is — `StatelessOp` with a different
  `link()`.
- Byte-identical externally observable behavior. The existing 457 tests pass
  unmodified, with no new tests required by the change itself.

**Non-Goals:**
- Any change to the per-element dispatch *shape*. Re-litigating whether
  `accept()` should call a helper is explicitly out — that was measured and
  rejected.
- Touching the other 18 hand-copied dispatch sites outside these eight sinks
  (`collector.py`'s closures, `_FlatMapSink`, `_SortedSink`). The collector
  closures are item 2's surface; the two ops don't fit the triple.
- Collapsing the six public collector names into fewer names, or changing any
  signature or return type.
- Anything from roadmap items 2 or 3.

## Decisions

### 1. `_summing(seed, coerce)` and `_averaging()` as private factories

`summing_int`/`summing_long` delegate to `_summing(0, None)`; `summing_double`
to `_summing(0.0, float)`. The three `averaging_*` delegate to `_averaging()`
with no parameters at all — they are byte-identical, so there is nothing to
parameterize. Return annotations stay per-wrapper (`int` for the int/long
pair, `float` for double and all three averaging), which is where the
Java-primitive distinction is actually expressed to a type checker.

`coerce` is `Callable | None` rather than always-applied `int`/`float`: the
int/long path must not coerce at all, since `total += cast(Any, r)` currently
preserves whatever numeric type the mapper returns (a `Decimal`, a `Fraction`),
and wrapping it in `int()` would be a real behavior change. `None` means "add
as-is", checked once outside the loop, not per element.

*Alternative considered:* one `_summing(seed, coerce)` with `coerce=lambda x: x`
for the int/long path. Rejected — that puts a call on the per-element path for
the two most common collectors, exactly the cost the benchmark ruled out.

**Reversed during implementation: the test is *not* hoisted.** This decision
originally required hoisting `coerce is None` outside the `async for`, which
means writing the loop twice. Implementation found two things. Measured
(interleaved, 41 reps, 200k elements): the hoisted form matches the pre-change
code, and the single-loop form costs a reproducible ~2% on `summing_int`/
`summing_long`. But `uv run ruff check` then fails with `C901 _summing is too
complex (11 > 10)` — the duplicated loop trips the project's own mccabe gate,
which the design had not accounted for. Suppressing that gate on a function
whose complexity comes entirely from duplication, inside a change whose purpose
is removing duplication, is the wrong trade. The shipped form is one loop with
a per-element `coerce is None` test: no call is added to the per-element path,
only a branch, and ~2% is two orders below the +32-75% that got
`add-callsite-dispatch` rejected. Decided with the user.

### 2. The dispatch mixin lives in `callable_dispatch.py` and unifies on `_fn`

`AsyncDispatch` (name to be finalized at implementation; must not read as a
sink) exposes one method, `_init_dispatch(fn)`, setting `self._fn`,
`self._is_async` and `self._checked`. The eight sinks mix it in and call it
from `__init__`.

Home is `callable_dispatch.py`, not `sink.py`: the mixin is about dispatch
state, not the sink protocol, and that module is already named for exactly this
concept and already imported by both `ops.py` and `terminals.py`. Putting it in
`sink.py` would push dispatch knowledge into the protocol module.

Unifying the stored name on `_fn` (over keeping `_predicate`/`_mapper`/
`_consumer`/`_accumulator`/`_comparator`) means the eight `accept()` bodies
become structurally identical — which is what turns the canonical-shape comment
in `callable_dispatch.py` from prose into something a reader can verify by
diffing two sinks. The constructor parameters keep their descriptive names and
their `Predicate`/`Mapper`/`Comparator` annotations, so the type-level
distinction is not lost. The cost is one mechanical rename inside each
`accept()`, resolving to the same single attribute lookup on the same object.

*Why a mixin and not a base class:* the eight sinks already have two different
bases (`IntermediateSink`, `TerminalSink`) with different `__init__`
signatures. A mixin with a plain method — not an `__init__` — sidesteps MRO
cooperation entirely and keeps each sink's `super().__init__(...)` call exactly
as it is.

*Alternative considered:* a mixin `__init__` participating in the MRO. Rejected
— `_MinMaxSink`, `_MatchSink` and `_MutableReductionSink` take extra
positional arguments, so an MRO-cooperative `__init__` would need `*args`
forwarding for no gain over a one-line call.

`_MatchSink` keeps its own `self._cancelled = False`; that is
short-circuit state, not dispatch state, and belongs to the sink.

### 3. `_group_into(composition, key_fn, initial)` backs both grouping collectors

The helper takes the composed generator, the callable producing a key, and the
initial `dict` (empty for `grouping_by`, `{True: [], False: []}` for
`partitioning_by`). It runs the five-branch dispatch once and returns the
populated `dict[Any, list]`. Each public collector keeps its own closure, which
calls the helper and then maps `downstream` over the values — the
`downstream`-mapping line stays at the two call sites rather than moving into
the helper, because item 2 changes `downstream`'s signature and that is the
line it changes.

`partitioning_by`'s `bool(...)` coercion is passed as a separate optional
`coerce_key` argument applied to the *awaited* key, preserving today's
behavior that a truthy non-`bool` predicate result lands in the `True` bucket.
`grouping_by` passes no `coerce_key`, preserving arbitrary-key behavior.

**Corrected during implementation.** This decision originally said
`partitioning_by` would pass "a `key_fn` that wraps its predicate" in
`bool(...)`. That is unimplementable: the dispatch classifies `key_fn` and
awaits its *result*, so a sync `bool()`-wrapper receives an unawaited
coroutine for an async predicate — always truthy — and would sort every
element into the `True` bucket. `tests/test_partitioning_by.py:37` catches it.
Hence the separate post-await `coerce_key` parameter, tested per element with
`if coerce_key is not None`. Unlike decision 1, this branch is not hoisted:
the loop body here already does a `setdefault` and an `append`, so the branch
is proportionally far cheaper than in `_summing`'s much tighter loop, and
hoisting would mean writing the only shared code this part extracts twice —
which would leave part (c) with almost no value.

*Alternative considered:* fold the `downstream` mapping into the helper.
Rejected — it is the one line item 2 rewrites, and burying it makes that item
harder, not easier.

### 4. `StatefulOp(StatelessOp)`, overriding `link()` only

`StatefulOp` inherits `__init__` and the `_sink_cls` ClassVar declaration and
defines only `link()`, which inserts `self` before the stored args. Both
docstrings stay: the hierarchy now says "a StatefulOp is a StatelessOp with a
different link()", which is true of the mechanics but false of the concept, so
the docstrings carry the shared-state distinction the classes no longer draw.

`isinstance` is not used to distinguish the two anywhere (verified before
implementation as an explicit task) — `parallel_stream.py` keys on a non-`None`
`make_shared_state()` result, not on type. If that turns out false anywhere,
including in tests, this part is dropped rather than worked around.

*Alternative considered:* a shared private base both subclass. Rejected — it
adds a third name to express a two-line difference.

## Risks / Trade-offs

- **A hidden `isinstance(op, StatelessOp)` check would change meaning under
  decision 4** (every `StatefulOp` starts passing it) → a grep across `src/`
  and `tests/` is the first task of that part, and the part is dropped if the
  grep hits.
- **Test doubles may subclass the sinks or assert on their attributes.**
  `tests/test_sink.py` and `tests/test_op_protocol.py` hold protocol doubles,
  and the last change had to touch them for a similar reason → grep the suite
  for `_predicate`/`_mapper`/`_consumer`/`_accumulator`/`_comparator` before
  the rename; mechanical test edits are acceptable, but they must be
  attribute-name edits only, never assertion changes.
- **Coverage could dip below the 98% gate.** Removing lines that were covered
  while leaving the branches concentrated in one helper usually raises the
  ratio, but `_summing`'s `coerce is None` branch is new → run
  `uv run pytest --cov-fail-under=98` as an explicit verification step, not
  just `uv run pytest`.
- **Scope drift into the per-element path.** The whole reason part (b) is
  allowed is that it stops at `__init__` → the tasks state this as a check, and
  any per-element restructuring found during implementation gets reported, not
  applied.
- **Part (c) collides with item 2 if item 2 starts first** → the roadmap
  already resolves this: whichever starts first owns (c). Nothing to do unless
  the order changes.

## Migration Plan

None — no public API, no persisted state, no dependency change. The four parts
are independent and can land as four commits in any order; rollback is a revert
of the part that regressed.

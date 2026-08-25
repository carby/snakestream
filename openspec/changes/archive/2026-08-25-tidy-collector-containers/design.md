## Context

See `proposal.md` — Why. The constraints that shape the approach:

- **Python floor is 3.10.** `@dataclass(slots=True)` landed in 3.10, so it is
  available on every interpreter CI runs (3.10–3.14). No `if sys.version_info`
  guard, no conditional import.
- **The nine containers are per-collection, not per-element.** Each is
  constructed once by its collector's `_supply()` and then mutated in place by
  an `async def _accumulate()` that runs once per element. `slots=True` emits
  the same `__slots__` descriptors the hand-written classes declare, so
  attribute reads and writes inside `_accumulate` are byte-for-byte identical.
  This is what separates it from the `CallSite` proposal the roadmap's **Done**
  section records as rejected: that one wrapped a *per-element* callable.
- **Three of the nine are constructed with an argument** — `_SumBox(seed)`,
  `_SummaryBox(seed)`, `_ReduceBox(identity)`, `_GroupBox(initial)`,
  `_MappingBox(container)`, `_CollectAndThenBox(container)` — and the rest are
  zero-arg. A dataclass reproduces both shapes: a field without a default is a
  required positional parameter, one with a default is optional. Positional
  order is preserved by declaring the argument-taking field first.
- **Two of the nine hold a mutable default.** `_ToMapBox.result` is `{}` and
  `_GroupBox.groups` is handed a `{}` by its caller.
- **`Counter` has three construction sites in `src/` and five in tests.**
  `ops.py` twice (`_LimitOp` / `_SkipOp` `make_shared_state()`), `collector.py`
  once — where the class object itself is the supplier, `Collector(Counter,
  ...)`, relying on its zero-arg default.

## Goals / Non-Goals

**Goals:**

- Delete the duplicated field lists in `collector.py` without changing a single
  field name, default, construction site, or attribute access.
- Leave `sink.py` with one container type instead of two, and no name that
  shadows a stdlib one.
- Bring `to_map`'s duplicate-key error type to Java parity, documented as a
  breaking change.

**Non-Goals:**

- **`Box` itself stays a hand-written class.** It is `sink.py`'s base
  container, not one of the nine `collector.py` containers the story names, and
  it is one field with one default — a dataclass would save two lines and churn
  a type that `ops.py`, `collector.py` and `test_sink.py` all name. Out of
  scope; if it is worth doing it is worth doing as its own row.
- **No benchmark run.** The roadmap's benchmark gate is spent, and this story
  has no per-element site. See Decisions.
- **No change to `_UNSET`, to the `Collector` quadruple, or to any
  accumulator's dispatch logic.** The `is_async`/`checked` field pairs stay
  exactly as they are; they are fields on these containers and move with them.

## Decisions

### Use `@dataclass(slots=True)`, not `NamedTuple` or `attrs`

`NamedTuple` is immutable, and every one of these containers exists precisely
to be mutated in place by an accumulator that cannot rebind its caller's local
— that is `Box`'s docstring, and it applies to all nine. `attrs` would be a new
runtime dependency for something the stdlib does. `@dataclass` without
`slots=True` would silently add a `__dict__` to nine classes that deliberately
do not have one, so `slots=True` is not optional here — it is the thing that
makes the replacement equivalent.

### Keep the generated `__eq__` and `__repr__` at their defaults

`@dataclass` generates both. Neither is called on any code path in this
library, so neither costs anything at run time, and `__repr__` is a small win
when one of these turns up in a traceback. Passing `eq=False` to suppress a
method nobody calls is noise. Alternative considered and rejected.

### Mutable defaults use `field(default_factory=...)`

`_ToMapBox.result` becomes `field(default_factory=dict)` — a bare `= {}` is a
`ValueError` at class-definition time, which is the dataclass machinery
catching the bug the hand-written `__init__` avoided by construction.
`_GroupBox.groups` is *passed* its dict by both of `grouping_by`'s suppliers
(`_GroupBox({})` and `_GroupBox(groups)`), so it stays a required field with no
default and no factory.

### `_ExtremumBox.found` keeps `_UNSET` as a plain default

`_UNSET` is a module-level `object()` — not a `list`/`dict`/`set`, so
`@dataclass` accepts it as a default without a factory, and a single shared
sentinel instance is exactly what the `is` comparison against it wants.

### Delete `Counter`; `counting()`'s supplier becomes a lambda

Confirmed with the user. `Counter` adds one thing to `Box` — a default of `0` —
and shadows `collections.Counter`, a name any reader of `sink.py` has met. The
two `ops.py` `make_shared_state()` bodies return `Box(0)` and their return
annotation becomes `Box`. `collector.py`'s `counting()` currently passes the
class object as the supplier (`Collector(Counter, ...)`); with the default gone
that becomes `Collector(lambda: Box(0), ...)`. A `partial(Box, 0)` was
considered and rejected — it imports `functools` for one call site and reads no
better than the lambda. `counting()`'s supplier runs once per collection, so
the lambda is not on any hot path.

`terminals.py`'s `_CountSink` docstring names `Counter` twice, explaining why
that sink uses a plain `int` instead. Both mentions become `Box`; the reasoning
it states is about the box, not about the zero default, so it survives the
rename intact.

### `IllegalStateException` stays a direct `Exception` subclass

Confirmed with the user. Making it derive from `ValueError` would keep existing
`except ValueError` call sites working, but `IllegalStateException` is also
what `pipeline-immutability` raises for reusing a consumed stream — and a
stream-reuse error is not a `ValueError` under any reading. Softening the break
here would mis-type it there. Clean break, loud for `except ValueError`,
recorded in the migration log.

### The historical migration-log entry that mentions `ValueError` is left alone

README's `redesign-collector-shape` entry illustrates interleaved downstream
side effects with "e.g. `to_map`'s duplicate-key `ValueError`". That entry
describes what was true at that release. Editing it would falsify the log,
which exists to be read chronologically. The new entry states the current type;
the old one keeps its own.

### No benchmark run

The roadmap says so explicitly, and the mechanism backs it: every site touched
here runs once per collection (`_supply`), once per composition
(`make_shared_state`), or once at class-definition time (the `@dataclass`
decorator itself). The one thing that *could* have been per-element —
attribute access inside `_accumulate` — is unchanged, because `slots=True`
produces the same descriptors. Spending a harness run to measure an unchanged
instruction sequence is the thing the gate was spent on avoiding.

## Risks / Trade-offs

- **`slots=True` rebuilds the class object, so identity captured before
  decoration would break** → Nothing in this codebase captures these classes
  before decoration; they are module-level and referenced only by the
  functions below them. Non-issue here, worth knowing if one ever gains a
  decorator above `@dataclass`.
- **A dataclass field's declared type is enforced by nobody at run time, so a
  wrong annotation would only surface under `ty`** → `ty check src` is in the
  gate and runs on 3.14. The hand-written `__init__`s carry the same
  annotations today; they are copied across, not re-derived.
- **`test_sink.py::test_counter_starts_at_zero_and_instances_are_independent`
  is a test *about* the deleted default** → It is rewritten for `Box`
  (independence of instances, and that `Box(7).value == 7`), not deleted; the
  zero-default assertion goes because the thing it asserted is gone. This edit
  is at line 336, one of the sites the roadmap named, so it is inside the
  tripwire rather than a widening of it.
- **The `to_map` break is loud for `except ValueError` but silent for a bare
  `except`** → Same shape as several entries already in the migration log. The
  new entry says so explicitly.

## Migration Plan

Single commit; no staged rollout. The library is pre-1.0 and the migration log
is the rollout mechanism. Rollback is `git revert` — nothing here writes state,
touches a file format, or changes a wire protocol.

## Open Questions

None. The two that would have changed the specs or the task breakdown —
whether `Counter` is deleted or renamed, and whether `IllegalStateException`
softens the break by deriving from `ValueError` — were put to the user before
these artifacts were written and are recorded under Decisions.

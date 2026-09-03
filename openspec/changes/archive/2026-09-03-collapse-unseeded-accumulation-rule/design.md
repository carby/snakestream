## Context

See proposal.md — Why. The constraints that shape the approach, and nothing else:

- **`_UNSET` is already in `sink.py`**, and its comment says why: "Lives here
  rather than in `terminals.py` or `collector.py` because both need it and
  neither may import the other." The rule that reads it has no such home yet.
  The import edge is `terminals -> sink` and `collectors -> sink`, never back.
- **Three of the five sites are `TerminalSink` subclasses; two are closures
  inside collector factories.** No single mechanism reaches both halves —
  a base class cannot reach a closure, and `collectors.py`'s boxes are
  dataclasses, not sinks. This is the whole of the design problem.
- **Two of the three sinks mix in `AsyncDispatch`**, which deliberately
  supplies no `__init__` so as to stay out of the MRO's constructor chain.
- **The per-element gate does not apply.** `_finish` runs once per collection.

## Goals / Non-Goals

**Goals:**

- One statement of the rule, reachable from both `terminals.py` and
  `collectors.py`.
- Collapse the *second* shared hook too — `_create_container() -> _UNSET` — so
  the family is named by its shape rather than by one expression it happens to
  share.
- Leave the `+10%`-gated neighbourhood entirely untouched, so that no
  measurement is owed before starting.

**Non-Goals:**

- Unifying `_ReduceSink.accept()` with `reducing()`'s accumulator, or
  `_MinMaxSink` with `_extremum()`. Both are measured rejections (+70%, +26%)
  and both stay.
- Changing what any terminal returns for any input. If a behaviour changes,
  the change is wrong.
- Touching `_CollectorSink`, `_CountSink`, `_ForEachSink`, `_MatchSink` or
  `GeneratorBridgeSink`. None can produce an unseeded container; see Decision 1.

## Decisions

### Decision 1: A `_UnseededSink` base, not a default on `TerminalSink._finish`

The roadmap entry left exactly one design question open: *"check first whether
`TerminalSink._finish`'s default can carry it."* It **can**, and it still
should not.

Enumerating every `TerminalSink` subclass and the container it can hold:

```
  subclass              container            can be _UNSET?
  --------------------------------------------------------
  _CountSink            int                  no
  _ForEachSink          None                 no
  _MatchSink            bool                 no
  GeneratorBridgeSink   list                 no    (result unused; buffer read directly)
  _CollectorSink        supplier's           overrides _finish anyway
  --------------------------------------------------------
  _ReduceSink           identity | _UNSET    yes
  _MinMaxSink           _UNSET | element     yes
  _FindSink             _UNSET | element     yes
```

So moving the rule onto the universal default is *safe* — a no-op for all five
above the line. It is rejected on honesty, not on risk: it would make the base
of every terminal assert something about containers that most of its subclasses
cannot produce, and a reader of `_CountSink` would have to rule out a rule that
never applied to it. `Ordering`'s `PRESERVE` default is the counter-example that
sets the bar — it is the default *because* it is true of almost every op, which
is the opposite of the situation here.

An intermediate base states the rule exactly where it holds. It also collapses
the second hook, which the universal default cannot touch: `_MinMaxSink` and
`_FindSink` have byte-identical `_create_container()` bodies, and a class that
names "a terminal starting with no value" owns both halves of that shape.

```
                    TerminalSink            _finish = identity, as today
                         |                  _create_container abstract
                    _UnseededSink           _create_container -> _UNSET
                         |                  _finish -> _unseeded(container)
             +-----------+-----------+
             |           |           |
        _MinMaxSink  _FindSink   _ReduceSink
        (both gone)  (both gone)  (_finish gone; keeps its own
                                   _create_container -> identity)
```

*Alternative considered: a `_UnseededFinish` mixin.* Rejected — it would carry
only `_finish`, leaving `_create_container` duplicated in two of the three, and
it would add a third base to sinks that already mix in `AsyncDispatch`. A mixin
earns its shape when the trait is orthogonal to the hierarchy; here it is the
hierarchy.

### Decision 2: `_ReduceSink` derives from it despite overriding `_create_container`

It inherits `_finish` and overrides the container, which reads as a partial fit.
It is the right fit: `_ReduceSink`'s container genuinely *is* `_UNSET` in the
no-identity overload — that is what `reduce(accumulator)` passes — so it is a
member of the family that happens to be seedable from outside. The override says
"seeded by the caller when the caller supplied one", which is the accurate
statement.

### Decision 3: `_unseeded()` as a free function beside `_UNSET`, despite the recorded preference against thin helpers

This cuts against a preference the repository has already stated — a lone
one-liner should be inlined, and what gets centralized is a *message* or a
*type*, not a check. `_checked()` in `sort.py` and
`ComparatorContractException` are that preference applied.

It is taken anyway, for one reason: **no other mechanism reaches all five
sites.** `collectors.py`'s two are closures over dataclass boxes, not sinks, so
`_UnseededSink` cannot reach them; without the function they restate the rule
twice more and the change would collapse three sites out of five, leaving the
worse half of the problem — a rule stated in two modules — exactly as it was.

The preference's own logic supports the exception. What it objects to is a
helper that wraps a check *already legible at its site*; what it prescribes is
centralizing the thing that can drift. Here the thing that can drift is the
rule itself — five independent statements of "unseeded finishes as `None`", any
one of which could be changed without the others — and it drifts across a
module boundary that no base class spans. The function is the rule's name, and
`sink.py` is its home for precisely the reason `_UNSET` is already there.

*Alternative considered: `_UnseededSink._finish` inlines the expression and
`collectors.py` keeps its two.* Rejected: that is the three-of-five collapse
above, and it leaves the sentinel with a rule stated beside it in one module and
twice more in another.

### Decision 4: `collectors.py` calls `_unseeded()` on the field, not on the box

`_extremum()`'s box holds `found`; `reducing()`'s holds `acc`. Both become
`_unseeded(container.found)` / `_unseeded(container.acc)` rather than the
function learning about boxes. Keeping it a plain value-in/value-out function is
what lets the sinks and the collectors share it at all — the two halves agree on
the sentinel and on nothing else.

### Decision 5: No benchmark gates this change, and the claim is structural

Every other duplication left in `src/` owes a measurement because it sits on the
per-element path, which is where all five rejections in **Done** happened. This
one does not, and the argument is not "it is probably cheap" but "it runs once
per collection": `_finish` is called from `TerminalSink.end()`, which
`_copy_into()` awaits once after the last `accept()`. A terminal over 20,000
elements calls it once.

The cost added is one attribute lookup and one Python call per collection, plus
one `is` comparison for the four sinks that inherit the base but can never be
unseeded — which is zero, since they do not inherit it (Decision 1 keeps them on
`TerminalSink`). This is the same exemption `collapse-sort-decorate-lanes`
claimed and used.

Stated so that a later reader does not re-open it: **do not benchmark this
change.** A ns/element figure would measure noise, and banking one would imply a
gate that does not exist.

## Risks / Trade-offs

- **A user value could be `_UNSET` and get silently converted to `None`.** →
  Not reachable, and no more reachable than today: `_UNSET` is a module-private
  `object()` with no public export, so a caller cannot name it, and the five
  sites already have exactly this exposure. The change moves the comparison, it
  does not widen what is compared.

- **MRO breakage on the two sinks that mix in `AsyncDispatch`.** →
  `_MinMaxSink(AsyncDispatch, TerminalSink[T])` becomes
  `_UnseededSink` in the second position. `AsyncDispatch` deliberately supplies
  no `__init__` — its docstring says so, and says why — so `super().__init__()`
  walks past it to `_UnseededSink` (no `__init__` either) and lands on
  `TerminalSink.__init__` exactly as it does today. To be asserted in a task,
  not assumed.

- **`_create_container` is `@abstractmethod` on `TerminalSink`.** →
  `_UnseededSink` implements it, so `_MinMaxSink` and `_FindSink` become
  concrete without one. That is the intended effect; the task list checks that
  neither becomes accidentally instantiable in a way that matters (they are
  private and constructed only by terminals).

- **The base is one level of indirection a reader must follow to learn what
  `_MinMaxSink` finishes as.** → Accepted, and it is the trade the change is
  for: one hop to a named rule beats five copies with no name. The class
  docstring carries the rule in words so the hop is usually unnecessary.

- **Someone later adds a sixth site and does not find `_unseeded()`.** →
  Mitigated by placement rather than by process: it sits immediately beside
  `_UNSET` in `sink.py`, so anyone reaching for the sentinel sees the rule that
  reads it in the same screen.

## Migration Plan

None. Nothing crosses a process, storage or API boundary; every changed name is
underscore-private and unexported. Rollback is `git revert` of a single commit.

## Open Questions

None. The one question the roadmap left open — base default versus a dedicated
base — is answered in Decision 1.

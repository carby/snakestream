## Context

See proposal.md — Why. Two facts about the current code shape the approach and
are not obvious from reading either function once.

**The positional paths already dissolve the conflation by hand.** Both arity
branches write the seed sentinel explicitly:

```
identity, accumulator = UNSET, identity                    # stream.py:594
identity, mapper, binary_operator = UNSET, None, identity  # collectors.py:466
```

So on every positional call the default never survives to reach a container,
and the split costs those lines nothing.

**The keyword paths are where the two roles genuinely meet, and where the bugs
are.** Each dispatcher tests only its *leading* unfilled slot, which is a valid
proxy for arity under positional calls and wrong under keyword ones:

| call | today |
|---|---|
| `reduce(accumulator=f)` | correct — but only because the sentinels are one object |
| `reducing(binary_operator=op)` | `TypeError: 'object' object is not callable` |
| `reducing(identity=0, binary_operator=op)` | `TypeError: 'int' object is not callable` |
| `reducing(0, binary_operator=op)` | `TypeError: 'int' object is not callable` |
| `grouping_by(f, downstream=to_set())` | `TypeError: 'object' object is not callable` |

All five verified against the current tree.

## Goals / Non-Goals

**Goals:**

- One name per role, with the single crossing point written down.
- Dispatch that is correct under any spelling of a documented overload.
- No change to any positional call's behaviour, and no change to `sink.py`'s
  contents.

**Non-Goals:**

- Where `UNSET`, `unseeded()` and `UnseededSink` live — that is
  `sink-sentinel-placement`.
- Collapsing the deliberate duplication between `ReduceSink` and `reducing()`,
  which is measured and rejected (`collapse-terminal-collector-duplication`).
- Any new overload. The three sets per function are exactly Java's.

## Decisions

### 1. `_MISSING` is private and defined twice, not shared

`stream.py` and `collectors.py` each define their own
`_MISSING = object()`.

*Why.* Every `is _MISSING` test compares against a default the **same module**
wrote in the **same function**. The marker's identity never crosses a module
boundary, so two distinct objects are not merely tolerable — they are the
accurate model. Contrast `UNSET`, which `stream.py` writes into `ReduceSink`
for `terminals.py` to read: that one *is* a cross-module value contract and
must stay a single object with a single home.

This also lands the naming rule correctly. A name no other module imports takes
the underscore, so `_MISSING` is underscored in both places — whereas a shared
`MISSING` would have to be bare and would need a home no existing module is a
natural fit for. That is precisely the trap `sink.py` fell into, and repeating
it for the arity role would be repeating the mistake this change exists to
undo.

*Alternatives.* A shared name in `type.py` (holds aliases, not values); a new
leaf module for one symbol (the thin-helper shape already declined twice on
this item's sibling); defining it in `collectors.py` and importing into
`stream.py` (the edge exists already, via `to_list`, but the import line reads
as a false claim about what the two modules share).

*Cost.* One duplicated line, which a reader may take for an oversight. A
comment at each definition states the reason, and reviewers should treat
"deduplicate these" as answered here.

### 2. Dispatch tests which slots are unsupplied, in overload order

Each dispatcher first shifts positionally-supplied arguments into their true
slots — testing the *trailing* slot rather than the leading one, so that a
keyword call, which fills trailing slots directly, never triggers a shift — and
then normalizes whatever remains unsupplied. `Stream.reduce()` is the smallest
instance:

```
if accumulator is _MISSING:            # reduce(op): shift one left-to-right
    identity, accumulator = _MISSING, identity
if identity is _MISSING:               # THE one crossing point
    identity = UNSET
combiner = None if combiner is _MISSING else combiner
```

`reducing()` shifts by two positions or one, chosen by whether `mapper` was
supplied, then normalizes `mapper` to `None` and `identity` to `UNSET`.
`grouping_by()` shifts `map_factory` into `downstream`, then defaults
`downstream` to the list-building collector and `map_factory` to `dict` —
noting that `supplied_factory`, which drives whether the collector inherits its
downstream's characteristics, must be read **after** the shift and means
"`map_factory` survived as supplied", not "three arguments were passed".

*Why trailing-first.* It is the only ordering under which the positional and
keyword spellings converge without counting arguments, and Python gives no way
to count them behind defaults short of `*args`/`**kwargs`, which would forfeit
the typed signature the `@overload` block and `ty` both depend on.

### 3. The two sentinels meet in exactly one line per function

`if identity is _MISSING: identity = UNSET` is the whole of the split's cost,
and it is the change's point rather than its overhead: what was an
undocumented coincidence — the no-identity form working because two unrelated
markers were the same object — becomes a rule a reader can see. The positional
branches keep writing `UNSET` directly; only the keyword path reaches this
line.

### 4. An unsatisfiable supplied-slot set raises `StreamBuildException`

Once dispatch reasons about slot sets, sets matching no overload become
visible, and each currently fails badly:
`reduce(accumulator=f, combiner=g)` would partition an unseeded fold and make
`ReduceSink.merge_from()`'s two `pragma: no cover — unreachable` branches
reachable, quietly widening semantics nobody specified;
`grouping_by(f, map_factory=dict)` reports "downstream must be a Collector"
about an argument the caller never passed; `reduce()` and `reducing()` with no
arguments at all raise `TypeError` from inside the fold.

Raising `StreamBuildException` at construction is consistent with how the
library already rejects a non-`Collector` downstream, and keeps those
`no cover` pragmas honest.

*Alternative considered and rejected:* silently treating a combiner without an
identity as non-partitionable. It answers a caller error with a performance
change they cannot see.

### 5. `sink.py`'s comment is corrected, its contents are not touched

The comment at `sink.py:22-25` is wrong in two ways. It names `collector.py`
where it means `collectors.py` — a one-letter error, so the module pair it
identifies is otherwise right. And "neither may import the other" is false:
`terminals.py` and `collectors.py` have disjoint import closures, so either
edge is acyclic today. The defensible claim is that neither is *downstream* of
the other, so neither is a plausible host. The rewritten comment says that, and
describes the seed role alone, the arity role having left.

Whether the trio then belongs in `sink.py` at all stays open under
`sink-sentinel-placement`, whose remaining question this change narrows to one
thing: `UnseededSink` gives the push protocol a real claim on the vocabulary,
while `collectors.py`'s `_ExtremumBox`/`_ReduceBox` are deliberately not sinks.

## Risks / Trade-offs

- **A reviewer deletes one `_MISSING` as duplication** → Decision 1's rationale
  is stated in a comment at each definition, and in `decisions.md` when the
  roadmap item closes.
- **The shift order is subtly wrong for a spelling not covered by a test** →
  Every documented overload of all three functions gets both a positional and a
  keyword test, plus the mixed spelling for `reducing()`; the invalid slot sets
  get rejection tests. That is the full cross-product of three functions by
  their overloads, which is small enough to enumerate rather than sample.
- **`grouping_by`'s `supplied_factory` is read before the shift** → it feeds
  characteristics derivation, so getting it wrong silently changes whether a
  collector declares `UNORDERED`. Called out in Decision 2 and given its own
  task.
- **Decision 4 turns three currently-erroring calls into different errors** →
  none is a documented overload and all three fail today, so no working caller
  changes behaviour. It is still caller-visible, hence the Migration entry.
- **Coverage** → the new rejection branches need tests to hold the 98% gate.

## Migration Plan

`README.md`'s Migration section gains one entry: keyword-spelled calls to the
documented overloads of `reduce()`, `reducing()` and `grouping_by()` now work
where four of them raised `TypeError`, and argument sets matching no overload
now raise `StreamBuildException` at construction rather than `TypeError` during
collection. No positional call changes. `_MISSING` itself is internal and gets
no entry.

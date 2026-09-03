## Why

`Characteristics.UNORDERED`'s own docstring names the problem without quite
naming it as one:

> `Stream.collect()` reads it, and it is the only reader.

A collector declares a trait about *itself* — that any two orderings of the
same elements collect to an equal result. What that trait *implies for
execution* is a separate fact, and it lives in `stream.py`, one module away
from the datum it reads:

```python
# stream.py:488, the only demand derivation in the library
demand = OrderDemand.NONE if Characteristics.UNORDERED in collector.characteristics else OrderDemand.IF_ORDERED
```

Written once in code, and restated twice in prose because two other call
sites have to reach the same conclusion without being able to call it:

| Site | How it derives the demand |
|---|---|
| `collect()`, 1-arg | the conditional above |
| `collect()`, 3-arg | a four-line comment concluding `IF_ORDERED` |
| `to_array()` | a comment: "`to_list()` declares no characteristics, so this observes encounter order" |

Both restatements are correct today. Both are derivations a reader has to
redo, and neither is checked by anything — they are the degraded-paraphrase
shape the roadmap keeps flagging, one level down from the roadmap's own
subject.

The 3-arg branch is the sharpest case. It already *constructs* a `Collector`
with no characteristics, so it would inherit `IF_ORDERED` by construction
from a shared derivation — its comment exists only because there is no shared
derivation to inherit from.

**Why now.** It is small, it is behaviour-preserving, and it gets smaller the
sooner it happens: every collector factory added between now and then is
another declarer whose implication is derived somewhere other than where it
is declared.

## What Changes

Move the derivation to the datum, and let the three sites share it.

- **`Collector` gains one method**, `demand()`, returning `OrderDemand.NONE`
  where the collector declares `UNORDERED` and `OrderDemand.IF_ORDERED`
  otherwise. It is a pure function of `characteristics` — no new state, and
  a `Collector` stays reusable across concurrent collections exactly as
  `collector-protocol` requires.
- **`collect()`'s 1-arg branch** calls `collector.demand()` in place of the
  inline conditional.
- **`collect()`'s 3-arg branch** calls the same method on the `Collector` it
  already builds, and **its comment is deleted**: with no characteristics
  declared, `IF_ORDERED` now follows by construction rather than by
  assertion.
- **`to_array()`'s comment is trimmed**; the derivation behind it is now one
  hop rather than two.

Not in scope, and deliberately: the twelve `characteristics=` sites in
`collectors.py`. Those *declare* a characteristic, or *derive one from a
downstream* (`mapping()`, `collecting_and_then()`, `grouping_by()`,
`partitioning_by()`). That is a different question — what a collector is —
from the one this change moves — what the executor owes it. They stay where
they are.

### The one judgment call

`Collector` is today a `__slots__` quadruple-plus-frozenset with no behaviour
at all, and its docstring says so ("A `Collector` has no other per-collection
state of its own"). `demand()` makes it the first method, which is a change
in what kind of object this is, however small.

The alternative that preserves the shape exactly — a free function
`demand_of(collector)` in `ordering.py` — was considered and declined: it
would put the edge on `ordering.py`, which is deliberately dependency-free at
runtime (`enum` and nothing else, with `Op` imported under `TYPE_CHECKING`
solely to keep `sink -> ordering` one-directional). Spending that module's
independence to protect `Collector`'s is the worse trade. `demand()` adds no
state and reads one field the object already holds, which is the weakest form
of behaviour an object can gain.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. `OrderDemand` is named in no specification; all 44 capabilities were
checked. What the specs pin is behaviour, not the derivation's location:

```
collector-protocol L105:
  "UNORDERED SHALL be read by collect() to decide whether the pipeline
   must deliver elements to the collector in encounter order."
```

`collect()` there is the operation, not a method body, and every scenario
backing that sentence is behavioural — "the declaring collection engages no
reorder barrier and holds no element back", "no delivery barrier is engaged,
and the collected set is correct". `racing-encounter-order`'s scenarios have
the same shape. After this change `collect()` still reads `UNORDERED` to
decide; it asks rather than inspects.

The existing scenarios in `collector-protocol` and `racing-encounter-order`
are therefore the regression test for this change, unchanged. That is the
argument for `skip_specs: true` rather than a reason to invent a requirement:
behaviour does not change, so no spec should.

## Impact

- `src/snakestream/collector.py` — one import (`snakestream.ordering.OrderDemand`),
  one method on `Collector`.
- `src/snakestream/stream.py` — three edits, all subtractive: two derivations
  become calls, two comments shrink or go.
- **New import edge:** `collector -> ordering`. Acyclic, and the lightest
  edge in the package — `ordering.py` imports only `enum` at runtime.
  `collector.py` already depends on the considerably heavier `execution.py`
  (for `maybe_aclosing`).
- No behaviour change, no public API change, no migration-log entry.
  `Collector.demand()` is reachable by a caller who constructs a `Collector`
  directly, which is a supported shape, so it is bare-named per
  `internal-name-visibility`.
- Per-element cost: none. `collect()` runs once per pipeline; `demand()` runs
  once per `collect()`.

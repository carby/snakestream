## Context

See proposal.md - Why. Two constraints shape the approach.

`sort()` never calls `KeyComparator.__call__`. It unwraps `.segments` and
extracts each key once, which is the decorate-sort-undecorate fast path, and
`sort.py`'s `_segment_column()` decides between a C-compared key column and a
`cmp_to_key`-wrapped one by `isinstance(payload, tuple)`. So the payload shapes
in `.segments` are load-bearing outside this file and cannot be normalised away.
The live consumers of the four sign functions are `min()`/`max()` and
`min_by()`/`max_by()`, at one comparison per element.

The class already states the principle this change extends, in its own
docstring: *"Each segment's extractor is classified sync/async independently,
once here at construction rather than per element or per comparison."*

## Goals / Non-Goals

**Goals:**

- One sign function per dispatch mode, with the key/comparator distinction
  expressed as data rather than as a second copy of the function.
- Pay for the merge out of work already being redone per comparison.

**Non-Goals:**

- Merging the sync and async axis. Closed by `add-callsite-dispatch`,
  re-declined 2026-09-03.
- Changing `.segments`, or anything `sort.py` reads.
- Changing any ordering result, null placement, or exception.

## Decisions

### 1. Normalise per composition, not per comparison — and that is what pays

The merge alone measures as noise (+1.3%/+0.5% on a key segment,
−4.2%/−3.8% on a comparator segment, +4.0%/+2.9% on a chain, across two runs).
Shipping only that means shipping a change whose measured effect is nothing,
which the roadmap's own gate would permit but which buys only tidiness.

Normalising the segment list in `__init__` is what turns it negative, because
two things were being recomputed on every comparison to reconstruct what
`__init__` already knew:

```
  per comparison, before          per comparison, after
  ----------------------          ---------------------
  isinstance(payload, tuple)      (nothing - read from _norm)
  zip(segments, _is_async,        (nothing - is_async is a
      strict=True)  [async]        field of the _norm tuple)
```

The async figure is the one that settles it: −20.3%, 1147.2 -> 913.8
ns/element, with the sample ranges not overlapping (1088-1168 vs 874-936). The
`zip(..., strict=True)` per comparison was a real cost, not a rounding error.

**Alternative considered: merge only, leave `__init__` alone.** Rejected on the
above. It is the smaller diff and it is defensible, but it converts a
duplication into a merged function while leaving the per-comparison rederivation
that made the merge look expensive in the first place.

### 2. The unification is the spec's, not this change's

`comparator-key-comparator` already requires that `comparing(f, cmp)` be
*"equivalent in result to supplying a bare comparator that extracts both keys
itself and compares them."* A key segment is therefore already specified to be a
comparator segment whose comparator is natural ordering; the code just spelled
that out four times instead of once.

This matters for how the change is reviewed. It is not "these four functions
look similar, merge them" — a shape argument, which the repository has rejected
before on measurement. It is "the spec says these are the same operation, and
the code should stop asserting it by parallel maintenance." Four copies of a
guaranteed equivalence can drift; one cannot.

### 3. The type check stays on the supplied-comparator path only

`type(sign) is not int` guards `ComparatorContractException`, and only a
user-supplied comparator can fail it. A naive merge would route natural ordering
through the same check, adding a per-comparison test that can never fire.

The `comparator is None` branch returns `(ea > eb) - (ea < eb)` before reaching
it, so the key path keeps exactly the instruction count it has today and the
comparator path keeps its guard. `comparator-contract`'s requirements are
untouched: the same inputs raise the same exception.

### 4. `_is_async` demotes to a local rather than being kept alongside `_norm`

Its only two uses are computing `_any_async` and the `zip` this change removes.
Folding `is_async` into each `_norm` entry leaves nothing reading the tuple, so
it becomes a local in `__init__`.

Worth stating because the obvious objection to Decision 1 is "now the object
carries two views of the same list." It carries the same number of fields as
before — `segments` + `_norm` + `_any_async` against `segments` + `_is_async` +
`_any_async` — and `_is_async` was already a derived-once view of `segments`. The
change replaces one derived view with a more complete one.

## Risks / Trade-offs

- **Two representations of the segment list can drift** if a future change
  mutates one without the other. -> Both are built in `__init__` from the same
  argument and `KeyComparator` is immutable in practice: `then_comparing()` and
  `reversed()` return new instances rather than mutating. There is no code path
  that writes `.segments` after construction.
- **The sync win is inside the harness's known noise band** (~10% run to run),
  even though it is negative in all six measurements. -> The gate is
  "must not regress past +10%", which is met with room in every run; the sync
  claim made in the proposal is directional, and the async claim is the one with
  non-overlapping ranges behind it. Neither is stated more strongly than the
  data supports.
- **A reviewer may read this as licence to re-open the sync/async merge.** ->
  It is not. That axis is closed and this change narrows a 2x2 to a 1x2
  deliberately; `decisions.md`'s 2026-09-03 entry states the reason, which is
  about state placement rather than about this file.

## Migration Plan

Independent of every other queued change. No caller-visible surface changes —
none of the four functions is exported, and `KeyComparator`'s public shape is
unchanged — so no README Migration entry is owed. Rollback is restoring four
functions and one `__init__`.

## Open Questions

None. The A-versus-B choice is decided above on measurement, and the gate's
own wording is the only loose end: it reads as a ceiling to survive, where the
honest post-measurement bar is "must not regress, and is expected to improve."
That belongs in the roadmap item rather than here.

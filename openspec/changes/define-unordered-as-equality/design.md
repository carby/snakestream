## Context

See `proposal.md` — Why. The short version: `UNORDERED` has a normative
definition (equality) and an unwritten stricter one living in two source
comments, and the stricter one is both false in its premise and fatal to its own
only declarer.

The one constraint that shapes the implementation: `collect()` already reads
`Characteristics.UNORDERED` (`stream.py:323`) and the racing executor already
acts on it. Nothing in `execution.py`, `_split_point()` or the barrier changes.
This change alters only what two factories *report*, plus the prose that says
what reporting it means.

The derivation mechanism also already exists, twice, as a single keyword
argument:

```
    collectors.py:534  mapping()             characteristics=downstream.characteristics
    collectors.py:574  collecting_and_then() characteristics=downstream.characteristics
```

## Goals / Non-Goals

**Goals**

- One definition of `UNORDERED`, stated where a reader will hit it, with the
  iteration-order non-promise explicit rather than inferred from the word
  "equal".
- `grouping_by()` and `partitioning_by()` report truthfully under that
  definition, using the mechanism already in the file.

**Non-Goals** (beyond the proposal's)

- No new abstraction for derivation. Two sites do it with one keyword argument;
  four sites should do it the same way.
- No change to how `collect()` reads the characteristic, or to the barrier.

## Decisions

### Forward the downstream's characteristics wholesale, not just `UNORDERED`

`characteristics=downstream.characteristics`, matching `mapping()` and
`collecting_and_then()` verbatim.

*Alternative considered:* forward only `UNORDERED`, e.g. intersecting with a
set of members known to be derivable. That is the more future-proof shape,
because wholesale forwarding is only accidentally correct: `UNORDERED` is the
sole member, so "every trait of downstream is a trait of the result" cannot yet
be wrong. If `IDENTITY_FINISH` were ever added it *would* be wrong here —
`grouping_by()` always installs a finisher — and it would already be wrong at
the two existing sites, which also always finish.

Rejected because it builds machinery to defend against a member that does not
exist, and because it would make four sites do the same job two different ways.
The latent issue is pre-existing, is identical at all four sites, and is
findable with one grep for `characteristics=downstream`. If a second member ever
lands, all four are revisited together — which is the cheaper invariant to carry
than a filtering rule maintained from now until then.

### Give `partitioning_by()` its own justification, not `grouping_by()`'s

Its comment currently reads "same reasoning as `grouping_by()` above". That
reasoning does not transfer, and the spec deltas say so separately for each.
`partitioning_by()` seeds both partitions in its supplier before any element
arrives, so its key set and key order are fixed for any input; `grouping_by()`'s
are not, and it needs the argument from `dict.__eq__` being key-order-insensitive
to reach the same conclusion. Two capabilities, two reasons, neither pointing at
the other.

*Alternative considered:* one shared comment covering both. Rejected — it is
how the wrong reasoning propagated in the first place.

### No test for the non-promise

The spec states that `UNORDERED` requires nothing about iteration order. That
is not testable in a useful way: a test asserting two results iterate
differently pins runtime behaviour the spec deliberately declines to fix, and a
test asserting they *may* differ is a tautology. The non-promise stays prose in
`Characteristics` and `collector-protocol`.

What *is* tested is its consequence — the derived declarations, and the
equality that justifies them.

### The disproof stays in the change record, not in the source

`collectors.py:52`'s premise is false, and the CPython demonstration
(`{0, 8, 16, 24, 32}` inserted in two orders, equal but iterating differently)
is what disproves it. That demonstration belongs in this proposal and in the
spec's justification, not as a comment in `collectors.py`: the source needs to
say what is true, not carry a standing argument against what used to be written
there.

## Risks / Trade-offs

**A caller relies on key iteration order from `.parallel().collect(grouping_by(f, to_set()))`.**
→ Real, and the reason this is marked BREAKING. Mitigations, in order of
preference: the pipeline was already only accidentally ordered here — Java
promises nothing about `groupingBy`'s map, and `to_set()` in the same position
has always been nondeterministic. A caller who needs encounter-ordered keys has
`sorted()` on the result, or a downstream that is not order-blind, or
`.sequential()`. The README migration-log entry is the discovery path.

**Wholesale forwarding is wrong the day a second characteristic lands.**
→ Accepted knowingly, see Decisions. Grep `characteristics=downstream`; four
sites, one fix, and the `Characteristics` docstring already flags that adding a
member is a deliberate act.

**The corrected `to_set()` prose weakens a requirement in readers' eyes.**
→ It does not change the requirement — `to_set()` declares `UNORDERED` either
way — but it does replace a confident structural claim with a narrower one. The
spec delta says explicitly why the old claim was withdrawn, so the next reader
does not reinstate it. That, not the derivation, is the durable value here: this
is the third pass over the same question.

## Migration Plan

Not a staged migration; the change is atomic and self-contained.

1. The definition (`collector.py` docstring, `collector-protocol` delta) lands
   first — everything else is a consequence of it and reads as unmotivated
   without it.
2. The `to_set()` premise repair — no behaviour change, so it can land with the
   definition.
3. The two derivations plus their inverted tests.
4. README migration-log entry.

**Rollback:** revert. There is no data, no persisted state, and no staged
rollout; the only externally visible effect is delivery order under an ordered
racing pipeline for two collector shapes.

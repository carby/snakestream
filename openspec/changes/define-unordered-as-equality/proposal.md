## Why

`Characteristics.UNORDERED` is defined twice in this repo, and the two
definitions disagree.

The normative text says equality. `collector-protocol/spec.md` states it twice —
"for any two orderings of the same elements, the collected result SHALL be
equal", and "its result is equal for any ordering of the same elements". Two
source comments say something stricter and unwritten: that *nothing observable*
may differ. `collectors.py:52` grounds `to_set()`'s mark in "a set retains no
record of insertion order", and `collectors.py:459` declines derivation on
`grouping_by` because "the dict's insertion order follows encounter order, so
deriving UNORDERED from the inner `to_set()` would be wrong, not merely
conservative".

The strict reading is not a stricter form of the same rule. It is a different
rule, it appears in no spec, and it is untenable on two counts:

- **Its premise is false.** A CPython `set` *does* retain a record of insertion
  order, via collision probe order. Inserting `0, 8, 16, 24, 32` and inserting
  the reverse gives two sets that are `==` but iterate as
  `[0, 32, 8, 16, 24]` and `[32, 0, 8, 16, 24]`. Java is careful here in a way
  the spec is not: `UNORDERED`'s javadoc says a result container may have "no
  *intrinsic* order, such as a `Set`" — not that a `Set` forgets how it was
  built.
- **It has no surviving declarer.** Applied honestly, it disqualifies
  `to_set()` — the one factory Java documents as unordered, and the reference
  declarer this library shipped. A definition under which the characteristic
  has zero valid users is a definition of nothing.

So equality governs, because it is the only reading under which the shipped
`to_set()` mark is sound. That is also Java's own framing: `UNORDERED` means the
collector "does not commit to preserving the encounter order of input elements"
— a statement about what is promised, not about what is detectable.

And it is the reading the runtime already implements. Python answers "are these
two collected results the same" with `==`, and `set.__eq__`/`dict.__eq__` are
order-insensitive by design. The strict rule overrides that answer with a notion
of sameness Python has no operator for, then owes hand-written per-container
rules to apply it — the same "two statements of one fact that can disagree"
objection `Characteristics` already uses to exclude `IDENTITY_FINISH`.

Once equality governs, `grouping_by`'s and `partitioning_by`'s declined
derivation is simply wrong, and the delivery barrier they take under racing is
unearned.

## What Changes

- `Characteristics.UNORDERED` states, in `collector.py` and in
  `collector-protocol`, that the declaration promises `==`-equality of the
  collected result and makes **no promise about iteration order** of that
  result. Java's "does not commit to preserving" is the parity language for it.
  This is the load-bearing change; the rest follows from it.
- `to_set()`'s justification is repaired. The requirement is unchanged — it
  declares `UNORDERED`, matching the documented Java contract — but the
  reason given for it stops being the false structural claim and becomes set
  equality ignoring membership order.
- `grouping_by(classifier, downstream)` derives `UNORDERED` from its
  downstream, by the rule `mapping()` and `collecting_and_then()` already use.
  `dict.__eq__` compares keys order-insensitively and values pairwise, and the
  classifier is a function of the element, so the result is equal under
  reordering exactly when every group's value is — which is the downstream's
  characteristic and nothing else.
- `partitioning_by(predicate, downstream)` derives `UNORDERED` from its
  downstream. It declines today on borrowed reasoning: its comment says "same
  reasoning as `grouping_by()` above", but that reasoning does not transfer.
  Both keys are seeded in the supplier before any element arrives, so the
  returned dict is always two keys in the same order over any input including
  the empty stream. The downstream is the only order-sensitive part left.
- **BREAKING (silent, performance-visible):** on an ordered racing pipeline,
  `collect(grouping_by(f, d))` and `collect(partitioning_by(p, d))` with an
  order-blind `d` no longer engage the delivery barrier. The collected value is
  unchanged under `==`; the returned dict's *key iteration order* becomes
  nondeterministic where it previously followed encounter order. `unordered()`
  was already the lever for this and `to_set()` already had this property, so
  the behaviour is not new to the library — only newly reached by these two
  factories. Recorded in README's migration log.
- The hedge at `collectors.py:67` splits. "Matching Java: OpenJDK gives
  `counting()` and the rest `CH_ID`/`CH_NOID`" conflates two claims. Java's
  javadoc documents characteristics for exactly three factories — `toSet()`,
  `groupingByConcurrent()`, `toConcurrentMap()` — and is **silent** for the
  other fourteen, `groupingBy()` and `partitioningBy()` among them. `CH_ID`/
  `CH_NOID` are private fields in `Collectors.java`, an implementation detail
  and not contract. Deriving here therefore breaks no documented parity; it
  fills a space Java left unspecified.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `collector-protocol`: `UNORDERED`'s definition gains the explicit non-promise
  about iteration order, so the equality reading is stated rather than merely
  implied by the word "equal".
- `collector-to-set`: the requirement's justifying prose is corrected; the
  requirement itself — that `to_set()` declares `UNORDERED` — does not change.
- `collector-grouping-by`: gains a requirement that characteristics derive from
  the downstream. The capability says nothing about characteristics today.
- `collector-partitioning-by`: gains the same requirement, on its own
  reasoning rather than `grouping_by`'s.

## Impact

- `src/snakestream/collector.py` — `Characteristics` docstring.
- `src/snakestream/collectors.py` — `to_set()` comment (`:52`), the
  `counting()` hedge (`:67`), `grouping_by()` (`:459`) and `partitioning_by()`
  derivation and comments.
- `tests/test_grouping_by.py:78` and `tests/test_partitioning_by.py:68` —
  `test_*_does_not_report_unordered_even_with_unordered_downstream` invert.
  The assertion stays the right one to make; only its answer changes.
- `README.md` — migration log entry for the delivery-order break.
- No change to `_split_point()`, the barrier, or any executor: `collect()`
  already reads `Characteristics.UNORDERED`, and this changes only what the two
  factories report to it.

## Non-goals

- **Marking the collectors Java leaves unmarked.** Whether `counting()`,
  `summing_int/long()` and `summarizing_int/long()` should *declare* `UNORDERED`
  is a separate decision — a choice about what to assert, not a correction of
  what is reported — and stays with roadmap question 4. This change only makes
  derivation follow the definition.
- **The permanently-unmarkable set.** `summing_double()`, `averaging_*()`,
  `summarizing_double()` and `to_map(..., merge)` are order-*sensitive* in fact
  — float addition is non-associative, and a user's merge function need not
  commute — so they can never declare `UNORDERED`, for a firmer reason than
  `min_by`/`max_by`'s. Writing that down belongs with the marking decision.
- **`to_map()`'s duplicate-key behaviour under reordering.** With no merge
  function, duplicates raise, and reordering may change which key the message
  names. That is a marking-half question, not a derivation one.

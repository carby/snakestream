## Context

See proposal.md — **Why**. The mechanical fact that shapes everything below:
README's parity tables encode two states in the leftmost column, `x` and
blank-with-strikethrough, and there is no row at all for a Java method nobody
thought to write down. The enumeration this change performs is therefore only
half the work; the other half is giving the table the third state, so the
enumeration is *stored where it is checked* rather than in a roadmap paragraph
that goes stale the moment a method is added.

The audit below is the change's actual product. It is recorded here rather than
only in the diff so that a later reader can see what was compared against what.

### The audit

**`java.util.stream.Stream` + `BaseStream`.** Implemented and rowed: 33.
Deliberately skipped and rowed: `flatMapToDouble/Int/Long`,
`mapToDouble/Int/Long`, `generate`, `toArray(IntFunction)` — 8. Absent with no
row:

| Java 8 | Verdict |
|---|---|
| `reduce(identity, accumulator, combiner)` | **Gap 1** |
| `close()`, `onClose()` | Implemented; row missing (`stream.py:204,210`) |
| `spliterator()` | Skip-for-now; already parked in roadmap **Later**, README silent |
| `Optional` (as the return type of `findFirst`/`findAny`/`min`/`max`/`reduce`) | Skip; four rows currently claim it |
| `IntStream` / `LongStream` / `DoubleStream` / `StreamSupport` | Skip; the per-method no-boxing rationale exists on `mapToInt` et al. but is never stated at class level |

**`java.util.stream.Collectors`** (33 static methods counting overloads).
Implemented: 27. Absent with no row:

| Java 8 | Verdict |
|---|---|
| `toMap(k, v, merge, mapSupplier)` | **Gap 2** |
| `groupingBy(classifier, mapFactory, downstream)` | **Gap 3** |
| `groupingByConcurrent` ×3, `toConcurrentMap` ×3 | Skip; covered by `CONCURRENT` being intentionally unimplemented, which is stated only on the `Characteristics` row |
| `Collector.of(...)` | Skip; the `Collector(...)` constructor is the equivalent, unstated |

**`java.util.Comparator`.** Implemented and rowed: `comparing(f)`,
`thenComparing(f)`, `reversed()`. Skipped and rowed: `naturalOrder`,
`reverseOrder`, `comparing(f, cmp)`, `thenComparing(f, cmp)`. Absent with no
row:

| Java 8 | Verdict |
|---|---|
| `thenComparing(Comparator)` | **Gap 4** |
| `nullsFirst`, `nullsLast` | **Gap 5** |
| `comparingInt/Long/Double`, `thenComparingInt/Long/Double` | Skip; same no-boxing argument as `mapToInt`, never applied here |

## Goals / Non-Goals

**Goals:**

- Make the three tables total over Java 8's surface, so the absence of a row
  becomes a defect rather than an ambiguity.
- Name the five real gaps in `roadmap.md` precisely enough to be picked up
  without re-deriving this audit.
- Leave the repo saying only true things about `reduce()`'s signature and about
  `Optional`.

**Non-Goals:**

- Implementing any of the five. Each is its own change with its own specs.
- Deciding whether each of the five is *worth* implementing. The queue records
  them; a later session judges them. Gap 5 is the one with an argument already
  attached (below) and even that is not a decision taken here.
- Java 9 surface (`takeWhile`, `dropWhile`, `ofNullable`, 3-arg `iterate`).
  Those already have their own **Later** entry, and the point of this change is
  to establish whether that entry's gate is met — not to walk through it.

## Decisions

**1. The third state is an unmarked row, not a new column or a separate list.**

The alternative was a "Not yet implemented" section under each table, which
keeps the tables as they are. Rejected: a reader checking whether `to_map` has
the container overload looks at the `to_map` row, and a separate list is the
same failure mode as the roadmap paragraph — a second place that must be
remembered. An unmarked row sits alphabetically among its siblings and is found
by the search that finds the implemented one. The three states then read:

```
| x |  name(...)   |  → implemented
|   | ~~name(...)~~ |  → deliberately skipped, reason in the summary cell
|   |  name(...)    |  → not yet implemented, gap; roadmap entry in the summary
```

**2. Every skip gets its reason in its own row, even when the reason already
exists elsewhere.**

`groupingByConcurrent` is covered by the `Characteristics` row's statement that
`CONCURRENT` is not implemented; `comparingInt` is covered by `mapToInt`'s
no-boxing rationale. Both are one inference away, and one inference is what a
table is for removing. The rows repeat the reason in a clause and point at the
row that argues it, rather than re-arguing it.

**3. The `IntStream`/`LongStream`/`DoubleStream`/`StreamSupport` absence is
stated as prose above the `Stream` table, not as four rows.**

They are types, not methods, and a row for a type in a method table is the kind
of thing that makes the table stop being checkable. The prose says the tables
cover `Stream` and `BaseStream` and that the primitive specializations are
skipped wholesale for the reason `mapToInt`'s row gives — which also makes the
per-method skip rows read as consequences of one decision instead of six
independent ones.

**4. `Optional` is a skip, and the four rows are corrected rather than left as
aspirational.**

Java's `Optional` earns its keep in a language where the alternative is a
`null` the type system cannot see. Python's `None` plus `is None` covers the
membership question, and the chaining half (`map`, `flatMap`, `ifPresent`,
`orElseGet`) is a second fluent API layered on top of the first — a caller who
wants it can reach for it themselves, and every terminal in this library
already returns something they can test. The four rows saying `Optional[T]` are
almost certainly `typing.Optional` written in Java's vocabulary rather than a
claim anyone made deliberately, which is exactly why they need correcting: they
read as a claim now.

Alternative considered: implement `Optional` and make it gap 6. Rejected here
and recorded rather than dropped — it is a substantially larger change than the
other five (a new public type, and a return-type break on four terminals plus
`reduce`), it is not required by anything, and putting it in the same queue as
four overload-widenings would misrepresent its size. If it is ever wanted it
deserves its own proposal, and the struck-through row will be the first thing
that proposal has to argue against.

**5. The `reduce` combiner correction splits the **Later** entry rather than
deleting it.**

The entry currently bundles `reduce()` and `collect()` as "both accept a
combiner but never invoke it", and the blocker it cites — a real combine step
needs real partitioned execution — is genuinely the blocker for `collect()`'s
inert argument. It is not the blocker for `reduce()`, which does not have the
argument at all: adding a third positional parameter and ignoring it is
possible today, and is precisely what `collect()` already did. So `collect()`'s
half stays in **Later** unchanged, and `reduce()`'s half becomes gap 1 in the
new queue, where its open question is "is signature parity worth a parameter we
must document as inert?" rather than "is real parallelism decided?".

**6. The five are queued as five, not one.**

Gaps 1–3 share a shape ("Java has N overloads, we shipped N−1, the missing one
is the container/merge-strategy argument") and could be one change with three
call sites. Kept separate because the shape is where the similarity ends: gap 1
adds a parameter that can never do anything (decision 5), gaps 2 and 3 add
parameters that genuinely change the result's type, and gap 3's `mapFactory`
interacts with `grouping_by`'s existing `UNORDERED` derivation — a caller-chosen
mapping type may have its own order semantics — which neither of the others
touches. Whoever picks them up may still batch them; the queue should not have
pre-batched them on a resemblance that thin.

**7. Gap 5 is recorded with its non-parity argument attached.**

`nullsFirst`/`nullsLast` are on the list because Java has them, but they are the
only one of the five with a user-facing bug behind them: `sorted()` over a
stream containing `None` raises `TypeError` from Python's comparison, and there
is currently no way to say where the `None`s go. That makes it the member of
this queue most likely to be worth building on its own merits, and the roadmap
entry says so rather than leaving it as one parity item among five.

## Risks / Trade-offs

- **The tables get longer, and length is what stopped anyone auditing them in
  the first place.** → The added rows are mostly one clause each, and every row
  added is a question a reader would otherwise have to answer by reading Java's
  javadoc. The failure mode being traded away — silence that reads as "not
  considered" — is worse than the one being accepted.
- **A total table is only total on the day it is written.** Java 8 does not
  move, so this specific table stays total; what decays is the *claim* that it
  is total. → The claim is stated once, above the tables, next to the statement
  of what the three row states mean, so a reader who finds a Java 8 method with
  no row knows they have found a defect.
- **This change closes roadmap item 5 by producing a queue, and the queue may
  turn out to be five items nobody wants to build.** → That is a legitimate
  outcome and is the answer to the Java 9 gate either way: if none of the five
  is worth building, Java 8 parity is done, which is the thing three roadmap
  entries have been unable to establish.
- **Correcting the `Optional[T]` rows makes the README describe a slightly
  poorer library than it appeared to.** → It describes the library that exists.
  The rows were not a decision anybody defended.

## Migration Plan

Not applicable. Documentation and one docstring; nothing to deploy, nothing to
roll back, no caller affected.

+++
id = "enumerate-java-8-parity-gaps"
title = "README's parity tables become total over Java 8 (`enumerate-java-8-parity-gaps`)"
filed = 2026-08-31
closed = 2026-08-31
outcome = "shipped"
shipped_as = "enumerate-java-8-parity-gaps"
+++

**`enumerate-java-8-parity-gaps`** (2026-08-31) — README's three parity
tables are now **total over Java 8's surface**, and the five methods this
library genuinely lacks are queued by name in **Now**. Closes question 5.

**Overtaken by events 2026-09-05: all five shipped, and the queue this entry
created in the Now bucket is retired.** See "Java 8 parity is closed" at the
top of
**Done** for the ledger and the count. The paragraphs below are left as
written and are accurate as of 2026-08-31; where one asserts something a later
event falsified, the annotation says so in place. Read the closing entry
first — nothing here is a live pointer any more.

**The question's own premise was the finding.** Three places in this file
offered "the Java-8 parity gaps README still tracks as unimplemented" as a
refill source for **Next**, and README tracked no such set. Its tables had two
row states — `x`, and struck-through-with-a-reason — where Java's surface has
three: a method nobody wrote a row for had no row at all, so absence was
invisible rather than deferred. A row existed only because someone wrote one.
That is why the refill source could be pointed at from three places without
any of them naming a member, and why an enumeration alone would have been half
a fix — a list in a roadmap paragraph decays the moment a method lands. The
tables carry a third row state now, declare their own totality, and make a
Java 8 method with no row a defect in the table rather than a silence.

Rows added: `close()`, `on_close()`, the 3-arg `reduce`, `spliterator()`,
`Optional`, the 4-arg `to_map`, the 3-arg `grouping_by`,
`grouping_by_concurrent`, `to_concurrent_map`, `Collector.of`,
`then_comparing(comparator)`, `nulls_first`/`nulls_last`, the six
`comparingInt`-family skips, and `compare`/`equals`. Final counts in rows:
`Stream` + `BaseStream` 35 implemented / 12 skipped / 1 gap, `Collectors`
22 / 3 / 2, `Comparator` 3 / 8 / 2 — per Java method the last is 3 of 17,
which is where the surface is genuinely thinnest.

**Two documents asserted a signature that does not exist**, and both are
corrected. The **Later** entry bundling `reduce()` and `collect()` as "both
accept a `combiner` for Java signature parity but never invoke it", and
`collector.py`'s `Collector` docstring repeating it, were wrong about
`reduce()`: it has two overloads and a third positional argument is a
`TypeError`. Only `collect()` ever grew the parity argument. That split the
**Later** entry — `collect()`'s half keeps the real-parallelism blocker, since
its parameter exists and would have to start doing something; `reduce()`'s
half is gap 1, where the question is whether parity is worth a parameter that
must be documented as inert. **The split was undone on 2026-09-01** and the
two halves are one **Later** row again — not because this correction was
wrong (it was not; the signature really does not exist) but because the
question it posed got answered the other way: the parity argument is not
worth an inert parameter, so both halves wait on the same prerequisite. The
factual correction stands; only the bucketing it implied was reversed.

**Four rows claimed a type this library does not have.** `find_any()`,
`find_first()`, `max()` and `min()` were typed `Optional[T]` and described in
Java's vocabulary ("an Optional describing…", "an empty Optional"); they
return `T | None`, and nothing here has `is_present`/`or_else`/`if_present`.
Almost certainly `typing.Optional` written in Java's idiom rather than a claim
anyone defended — which is exactly why it needed correcting, since it read as
one. `Optional` now has a struck-through row stating the skip: `is None`
answers the membership question, the chaining half is a second fluent layer
over a value the caller already holds, and adopting it would be a new public
type plus a return-type break on four terminals and `reduce()`, so it wants
its own proposal rather than a place in a queue of overload widenings.

**The Java 9 gate is met**, which is the question this item existed to settle.
None of the five gaps is structural — three are overload widenings on existing
machinery, two are self-contained `comparator.py` additions — and the only
genuinely blocked Java 8 items, `spliterator()` and `collect()`'s combiner,
sit behind the real-parallelism decision **Later** says needs explicit buy-in.
They cannot be what Java 9 waits on without waiting forever, so that entry is
no longer sequencing-blocked; it competes with the five on merit.

**Both of its premises expired, and the conclusion survived both.** The two
"genuinely blocked" items are shipped — `spliterator()` and `collect()`'s
combiner, by `fork-join-executor-and-spliterator` and `make-combiners-live`
(2026-09-04) — so the real-parallelism decision this paragraph routes around
no longer exists to route around; and there is nothing left for Java 9 to
compete with on merit, the five having shipped by 2026-09-05. The gate is
therefore met far more plainly than argued here: not "the blockers cannot
count, so the gate opens", but "there is no gap". Java 9 stays in **Later**
regardless, on a different reason than this one — it is undecided rather than
blocked. Its row carries the current reasoning.

Gap 5, `nulls_first`/`nulls_last`, is the one worth building on its own
merits: `sorted()` over a stream containing `None` raises `TypeError` out of
Python's comparison and there is no way to say where the `None`s go. The other
four are parity for parity's sake. The five are filed as five rather than one
batched entry — gaps 1-3 resemble each other only at the surface, and the
batching call belongs to whoever picks them up.

**How the batching call actually went (2026-09-05):** partly batched, and
along a seam this paragraph did not predict. `f6406fe` took the two
container-choosing collector overloads together (`to_map`'s fourth argument
and `grouping_by`'s three-argument form — gaps 2 and 3, which share a shape
after all, both being "let the caller supply the mapping"); `8cdcf31` took
gap 5 alone, as predicted, on its own merits; `31860e6` closed the two
`keyComparator` overloads that were struck-through *skips* here rather than
gaps at all; and gap 1, `reduce`'s combiner, waited five days for a reason
none of this anticipated — not its own difficulty but the executor
underneath it, landing in `make-combiners-live` once fork/join could give a
combiner something to combine.

No behaviour changed: one docstring in `src/`, and `git diff -- tests/` empty
at the end, which was the change's own tripwire.

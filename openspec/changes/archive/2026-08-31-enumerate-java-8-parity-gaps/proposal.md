## Why

Three places in `roadmap.md` offer "the Java-8 parity gaps README still tracks
as unimplemented" as a refill source for **Next**, and none of them says what
they are. **README does not in fact track them.** Its three parity tables have
two states — a row marked `x`, and a row struck through with a reason — and
Java's surface has three. A method absent from Java's side of the table has no
row at all, so absence is not something the table can express, and the "gap
set" it is credited with tracking has never existed as a list. That is why the
refill source can be pointed at from three places without any of them being
able to name a single member.

Enumerating it once turns a vague refill source into a real queue, and settles
whether the Java 9 work **Later** gates on "once Java 8 parity is substantially
done" can start. It cannot be done once and left, though, unless the table's
missing third state is added at the same time: an enumeration that lives only
in a roadmap entry decays into exactly the situation this change is fixing.

Roadmap item 5 (**Now**) is this work. Item 4's closure on 2026-08-31 means the
enumeration no longer has to carry the `counting()` question forward.

## What Changes

- **Every Java 8 method absent from README's `Stream`, `Collectors` and
  `Comparator` tables gets a row.** The tables become total over Java 8's
  surface: after this change, a Java method with no row is a defect in the
  table rather than a silence to interpret. Two forms of new row — struck
  through with a reason, for a method that is deliberately skipped, and an
  unmarked (no `x`) row naming it as a genuine gap.
- **Five methods are named as genuine, not-yet-implemented gaps** and are
  added to `roadmap.md` as queued work. They are:
  1. `Stream.reduce(identity, accumulator, combiner)` — the third of Java's
     three `reduce` overloads.
  2. `Collectors.toMap(k, v, merge, mapSupplier)` — the fourth argument, which
     chooses the result container.
  3. `Collectors.groupingBy(classifier, mapFactory, downstream)` — the third
     of Java's three `groupingBy` overloads, same container-choice argument.
  4. `Comparator.thenComparing(Comparator)` — the bare-comparator overload.
     README skips the `thenComparing(f, keyComparator)` form with a stated
     reason and never mentions this one either way.
  5. `Comparator.nullsFirst` / `nullsLast`.
- **Two documents that assert a signature which does not exist are
  corrected.** `roadmap.md`'s **Later** entry says `reduce(identity,
  accumulator, combiner)` and `collect(supplier, accumulator, combiner)` "both
  accept a `combiner` for Java signature parity but never invoke it", and
  `collector.py`'s `Collector` docstring repeats it ("as `collect(supplier,
  accumulator, combiner)` and `reduce()`'s `combiner` already have").
  `Stream.reduce()` has two overloads and no combiner; a third positional
  argument is a `TypeError`. Only `collect()` ever grew the parity argument.
- **Four rows stop claiming a type this library does not have.**
  `find_any()`, `find_first()`, `max()` and `min()` are typed `Optional[T]` and
  described in Java's vocabulary ("an Optional describing…", "an empty
  Optional"). They return `T | None`. Java's `Optional` — `isPresent`,
  `orElse`, `map`, `ifPresent` — exists nowhere in this library, and the tables
  currently read as though it were implemented. The rows are corrected to
  `T | None` and `Optional` is given its own struck-through row stating the
  skip and why.
- **`close()` and `on_close()` get rows.** Both are implemented
  (`stream.py:204`, `stream.py:210`) and documented in the Auto Close prose,
  but a reader auditing the table against `BaseStream` finds two methods
  missing from it.
- **No behaviour changes and no source file changes** other than the one
  `collector.py` docstring correction above. Implementing any of the five gaps
  is out of scope and is what this change queues.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Nothing this change touches is behaviour: it adds rows to README's
parity tables for methods that do not exist, corrects two prose claims about a
signature, retypes four table cells to the types the code already returns, and
adds roadmap entries. No public name, signature, result or exception changes,
and no test should need editing. `.openspec.yaml` sets `skip_specs: true`.

The five gaps this change names will each need their own specs when they are
built; naming them is not specifying them, and this change deliberately does
not decide whether any of the five is worth building.

## Impact

- `README.md` — the three parity tables (`Stream`, `Collectors`, `Comparator`)
  gain rows; four `Optional[T]` cells are corrected. The **Migration** log is
  untouched: nothing here is a break.
- `roadmap.md` — the five gaps are added as queued work; **Now** item 5 is
  closed with its answer; the **Later** combiner entry is corrected to say that
  only `collect()` has the parity argument, which splits it: the `collect()`
  half stays blocked on real parallelism, the `reduce()` half becomes gap 1 in
  the new queue.
- `src/snakestream/collector.py` — one docstring line. No code.
- No benchmark gate applies; nothing runs per element, or at all.

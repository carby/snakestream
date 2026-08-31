## Context

See proposal.md — Why for the motivation, and the two delta specs for the
requirements. The state that shapes the approach:

- `collect()` reads `Characteristics.UNORDERED` in exactly one place, and that
  read is already pinned by the `grouping_by`/`partitioning_by` recording tests.
  Nothing about the mechanism changes here.
- Every collector shipped today decides its characteristics either as a
  constant of the factory (`to_set()`, `counting()`, `summing_int()`) or by
  copying a downstream's (`mapping()`, `grouping_by()`,
  `collecting_and_then()`). `to_map()` is the first that must decide from its
  own arguments.
- `_ORDER_BLIND` already exists as the named tuple carrying the shared
  reasoning, so this change consumes it rather than restating anything.
- `racing-encounter-order` already ranks its two verification shapes:
  observation of arrival order where the result permits it, the
  declaration/mechanism pair only where it does not.

## Goals / Non-Goals

**Goals**

- Close the last item in the roadmap's **Open questions needing a session**, and
  remove the section, since it exists to carry exactly one question.
- Keep the reasoning for the two forms' opposite answers at the declaration
  site, where the next reader of `to_map()` meets it.
- Verify the no-merge form by observation, which is stronger than the guard the
  integer collectors settle for, and verify the 3-arg form from the other side.

**Non-Goals**

- Any new mechanism. No dispatch, executor, `Collector` or `collect()` change.
- Re-running the benchmark. See the decision below.
- A way for a caller to declare their `merge_function` commutative. That would
  be new public surface with no Java counterpart, and `unordered()` already
  expresses the same freedom one level up.
- Reconsidering `min_by`/`max_by` or the floating-point family, both already
  closed.

## Decisions

**Decide the characteristics from `merge_function`, at the `Collector(...)`
call.** `to_map()` already branches on `merge_function is None` inside its
accumulator; the declaration is the same branch read one level out, so the
implementation is `characteristics=_ORDER_BLIND if merge_function is None else
()`. Alternatives considered — split the factory into `to_map()` and
`to_map_merging()`, which would make each declaration a constant, and was
rejected outright: Java has one `Collectors.toMap` name for both overloads, and
the guiding principle is 1:1 on the public surface. Or declare from a
`Characteristics` argument the caller passes, as `_summing()`'s shared body
does internally; rejected because that is a mechanism for sharing one body
between two *factories*, not a way to expose the decision to users.

**Mark the no-merge form despite the duplicate-key message becoming
nondeterministic.** This is the objection `mark-order-blind-collectors` named
when it declined to fold `to_map()` in, and it does not survive contact with
the contract as written. `UNORDERED` claims that two orderings of the same
elements collect to a result that compares equal — a claim about the collected
value. An exception is not a collected value; the collection did not produce
one. What *is* order-invariant is the part a caller can act on: whether the
collection raises at all, and the exception type. Only the key named in the
message varies, and only when there are two or more distinct collisions, on a
path where the library never promised a particular one — even sequentially it
names whichever collision comes first, which is already an artifact of ordering
rather than a documented choice. Alternative considered — decline the mark to
keep the message deterministic under every executor. That has real value for
debugging, and it is the reason this obstacle was worth raising; it loses
because it prices a failure path's diagnostic text above the throughput of the
success path, on the one collector family where the success path is the common
case, and because `to_set()`'s precedent already settles that an observable
non-value property of the result does not disqualify a declaration about the
value.

**State the 3-arg exclusion as a requirement rather than leaving it silent.**
Following `mark-order-blind-collectors` on `summing_double()`: undeclared and
required-never-to-declare look identical in behaviour today but not to a later
pass. The 3-arg form is order-sensitive *in fact* — `lambda a, b: a` is the
one-line proof — so a written exclusion converts a standing invitation to
re-examine it into a closed question. This matters more here than for the float
family, because the two forms now sit in one function body and the mark is one
conditional away from being applied to both.

**Verify the no-merge form by observation, not by the declaration/mechanism
pair.** A `dict`'s key iteration order follows insertion, so
`list(result.keys()) != SOURCE` is direct evidence that no barrier ran, using
the same `_slow_head` racing source the existing tests use. This is the shape
`racing-encounter-order` already prefers, and it is available here precisely
because a `dict` betrays something a `set` and an `int` do not. The delta spec
adds a sentence saying that a property the declaration does not *promise* is
still admissible as *evidence* — otherwise the availability of this observation
reads as a contradiction of the mark rather than as its strongest guard.
Alternative considered — assert only the declaration, as `to_set()` does;
rejected because the requirement says observation wherever the result permits
it, and here it does.

**Verify the 3-arg form from the other side.** A test that a first-argument-
winning `merge_function` yields the encounter-order value under `.parallel()`
fails if someone later drops the conditional and marks both forms. Without it
the exclusion is spec text with nothing enforcing it, which is the failure mode
the guard rule was written to prevent.

**Rest on the existing figures rather than re-measuring.** The barrier's cost
is a property of `race_through()` — head-of-line blocking behind a straggler
while branches idle — not of the collector behind it, and
`mark-order-blind-collectors` measured it at 1.12–1.27x on tail-latency IO.
Re-running that shape with `to_map()` as the terminal would re-measure the same
mechanism and produce a second set of figures to keep current. Alternative
considered — measure anyway, on the ground that a dict-building accumulator
does more per element than `counting()`; rejected because more per-element work
in the collector makes the barrier's relative cost *smaller*, not larger, so a
fresh measurement could only weaken a case that is being made on semantics.

**Remove the roadmap's Open-questions section rather than leaving it empty.**
It was opened to carry seven questions and this is the last; an empty section
with a heading reads as a place to file the next one, which is what the queue
above it is for.

## Risks / Trade-offs

**A duplicate-key exception under `.parallel()` names a different key than it
did before** → The only observable behaviour change in this proposal. Confined
to streams with two or more *distinct* collisions and to the racing executor;
sequential behaviour is byte-identical. The spec states it as a
non-guarantee at the point where a reader meets the exception, so a caller
asserting on message text learns it from the spec rather than from a flaky
test. `sequential()` restores determinism for anyone who needs it.

**One factory whose declaration varies by argument sets a precedent for
argument-dependent characteristics** → It is a precedent, and a narrow one: it
applies where a factory's optional argument is itself the order-sensitive part.
The design records that the alternative (two factory names) was rejected on
Java parity rather than overlooked, so a future collector in the same position
inherits the reasoning and not just the pattern.

**Marking makes `to_map()` diverge from OpenJDK's `Collectors.toMap`, which
declares nothing** → The same divergence `mark-order-blind-collectors` accepted
and documented at `_ORDER_BLIND`: Java's javadoc documents characteristics for
three factories only and is silent here, and Java's `UNORDERED` governs a
combine strategy this library has no counterpart for. Nothing about the
collected value differs.

**The observation test rests on a `dict` property the mark explicitly does not
promise** → If CPython ever stopped ordering `dict` by insertion the test would
fail loudly rather than pass vacuously, which is the correct failure direction.
The spec is written so that the property's admissibility as evidence is stated,
not assumed.

## Migration Plan

None required. No public signature changes, no behaviour change under
`SEQUENTIAL`, and under `RACING` the no-merge form produces the same `dict`
sooner. Rollback is removing one conditional. A README Migration entry is not
owed: nothing breaks a caller's code.

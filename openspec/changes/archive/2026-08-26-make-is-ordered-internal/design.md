## Context

See `proposal.md` — Why. The mechanics are already settled by
`make-ordering-a-chain-characteristic`: `stream.py` folds `Op.ordering` over the
queued chain, stores nothing, and two terminals branch on the result. Nothing
about that is in question here.

Two facts shape the work. First, the code change is trivial and the pinning is
not: `is_ordered()` is defined once, called **once** internally, and pinned in
nine spec scenarios plus twenty references in `tests/test_unordered.py` — which
is the *only* test file that names it. (`CLAUDE.md` claims a second caller in
`find_first()`; that has been stale since `make-ordering-a-chain-characteristic`
made `find_first()` name `SEQUENTIAL` unconditionally.) Second, the accessor is currently the sole
observable for part of the ordering contract; some of what the spec pins cannot
be restated behaviourally, and pretending otherwise would quietly drop rules
rather than restate them.

## Goals / Non-Goals

**Goals:**
- Match Java's public surface: `unordered()` and `sorted()` in, no ordering
  accessor out.
- Restate the spec so ordering is pinned by what a pipeline *does* wherever a
  behavioural observable exists.
- Land before the three `RACING` ordering items, so their call sites are written
  against `_is_ordered()` from the outset.

**Non-Goals:**
- Changing any ordering semantics. What is ordered, what clears it, what
  restores it, and mode-switch survival are all untouched.
- Changing the fold's implementation, caching strategy, or docstring reasoning.
- A deprecation shim or alias. Pre-1.0, breaks go in the README migration log.
- Adding a public `ordered()`. It does not exist in Java either; see the
  struck-through README row.

## Decisions

**Rename to `_is_ordered()`, do not delete — and do not inline it either.**
Confirmed 2026-08-26 after the single-call-site fact above was raised as an
argument for folding the five-line body straight into `for_each_ordered()`. With
one caller that is the ordinary call, and it was rejected on three grounds, the
first decisive:

1. **The spec would have nothing left to assert on.** Three mode-switch
   scenarios have no behavioural observable (see the decision below) and pin the
   rule through the accessor. Inlining collapses that choice into dropping them,
   which unpins the exact rule whose violation produced the wrong answer
   `make-ordering-a-chain-characteristic` fixed.
2. **The docstring records a decision, not a description.** It explains why the
   fold is deliberately *not* cached onto the instance — a denormalised copy of a
   chain property is what let `unordered()` apply to a whole pipeline regardless
   of position. Inside `for_each_ordered()`, a method about consuming elements,
   nobody looking for that reasoning finds it.
3. **The callers return immediately.** All three `RACING` ordering items
   sequenced behind this one need the same branch, so inlining now means
   re-extracting in the next change.

The defect is the *public name*, not the function.

**No alias, no deprecation period.** `AttributeError` is the loud break the
project already prefers — the `unordered()` return-value change in the same
migration-log section broke the same way on purpose. An alias would leave the
divergent surface in place, which is the entire thing being removed.

**Three mode-switch scenarios keep an accessor assertion; the rest go
behavioural.** This is the one real design question. "The characteristic
survives a `parallel()` switch" has no behavioural observable: every terminal
that consults ordering does so at the end of the pipeline, by which point a
switched stream and a directly-constructed one with the same chain and executor
are indistinguishable — which is precisely the property the requirement asserts.
Alternatives considered and rejected: (a) drop those scenarios — that unpins the
rule whose violation produced the wrong answer this capability exists to prevent;
(b) assert via `for_each_ordered()`'s executor choice — observable only as
interleaving under a racing executor, i.e. a timing-dependent test, and the
repo's ordering tests are deliberately deterministic (the one repeated test in
`test_find_first.py` runs ten times *because* the old wrong answer was
nondeterministic). Asserting on a named-private accessor in three scenarios is
the honest cost, and the spec says so in the requirement text rather than
leaving a reader to wonder.

**Everything else gets a behavioural form.** `find_first()` on a racing sorted
pipeline and `for_each_ordered()`'s ordered path give real observables for the
`sorted()`-restores and `unordered()`-clears rules. Those scenarios are
rewritten, not renamed-and-kept.

**Scenario names are swept after archive, not in the delta.** OpenSpec treats a
scenario name as its identity: renaming one inside a `MODIFIED` block reads as
dropping it, and `openspec validate` refuses. Three scenario names spell
`is_ordered()` (`unordered() flips is_ordered() to False`, `sorted() after
unordered() is ordered again`, `unordered() after sorted() is unordered`). They
are carried through the delta under their existing names, each marked in-line as
retained for continuity, and renamed directly in
`openspec/specs/stream-ordering/spec.md` after archive — the same post-archive
sweep this repo already does for stale `## Purpose` sections. The alternative,
`REMOVED` plus `ADDED` of the whole requirement, loses the delta's readability
for a cosmetic gain.

**The spec's `## Purpose` is edited directly.** A delta's `## Purpose` is ignored
for an existing capability, and the current one names `is_ordered()` twice. It is
a task, done against the main spec.

## Risks / Trade-offs

- **A silent break for anyone calling `is_ordered()` outside this repo.** →
  It is not silent: `AttributeError` fires at the call. Mitigated by a README
  migration-log entry sitting with the two existing `0.3.5 -> next` ordering
  entries, which is the channel this project uses for exactly this.
- **Rewriting tests to assert behaviour can weaken them** — a behavioural test
  passes for reasons unrelated to ordering. → Each rewritten test must fail if
  the ordering rule is reverted; verify by temporarily inverting the fold
  locally, not by assuming. Where a rewrite cannot meet that bar, keep the
  accessor assertion against `_is_ordered()` and say so, matching the spec's
  own exception rather than inventing a second one.
- **Naming a private function in a spec.** → Confined to three scenarios,
  justified in the requirement text, and the requirement itself states the
  public/private split as the rule. It is the smaller evil against unpinning it.
- **Merge friction with the three `RACING` ordering items.** → This is why the
  sequencing is explicit: land this first, then those are written against the
  final name. Reversing the order means touching every new call site twice.

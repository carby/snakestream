## Context

See proposal.md — Why, for the duplication and where it sits.

Two constraints shape the approach, and both are about cost rather than shape.

The merge loop is on the **per-element** racing path: every element a racing
pipeline produces passes through one iteration of the `for task in done:` body.
This repo has priced that path before and does not treat an extra frame there as
free. `Sequential.value()` exists solely to override the generic
`drain(elements(...), terminal)` with `feed_through()`, because composing and
then draining cost **+125% per element** on `count()` — one generator hop.
`race_through()`'s own docstring records the delivery barrier's two halves at
0.71 and 0.68 µs/element against a 7.32 µs baseline. A refactor that adds a hop
here is competing against numbers, not against taste.

The second constraint is that `_release_in_order(branches, window)` is called
directly by `tests/test_racing_encounter_order.py:669`, so its signature is
load-bearing.

## Goals / Non-Goals

**Goals:**

- One statement of the branch-task lifecycle — arm, cancel, gather, close —
  instead of two copies.
- One statement of whether branches get closed, instead of an asymmetry sitting
  silently between two copies of the same loop.
- Zero measurable per-element cost. A refactor here has to be free or it is not
  worth having.

**Non-Goals:**

- Changing what the merge *does*. Same elements, same order, same close counts.
- Removing the remaining duplication in the loop body. See Decision 1 — that
  part differs in payload handling, and buying it costs 4%.
- Touching `_split_point()`, `_guarded()`, `_Window`, `group_through()` or
  `_releasable()`. The split machinery is not what this change is about.

## Decisions

### Decision 1: extract the lifecycle, not the loop — measured, not assumed

Two shapes were built and benchmarked before choosing.

**A — extract the whole merge as an `AsyncGenerator`.** `merge(branches)` yields
whatever the branches produce as they land; `race_through()` becomes
`async for r in merge(branches): yield r` and `_release_in_order()` keeps only
its buffer. Removes all twenty duplicated lines. Adds one async-generator hop
per element.

**B — extract only the arming and the cleanup**, as an `@asynccontextmanager`
yielding the `in_flight` dict. Removes the arm line and both five-line `finally`
blocks — twelve lines. The eight-line `while`/`for` body stays in both callers.
Runs once per composition, so it cannot cost anything per element.

Harness matched to the one `race_through()`'s own figures use: Python 3.14.5,
20,000 elements, `map(x + 1)`, 4 workers, all three variants draining into the
same `_CountSink`. Ten samples per variant, **interleaved round-robin** across
rounds with two warm-up rounds dropped, so ordering and thermal drift hit all
three equally. µs/element:

| variant | order-blind, min / median | vs base | ordered delivery, min / median | vs base |
|---|---|---|---|---|
| baseline (as shipped) | 7.12 / 7.40 | — | 9.42 / 9.62 | — |
| A — `merge()` generator | 7.25 / 7.70 | **+2.0% / +4.1%** | 9.79 / 10.05 | **+3.9% / +4.5%** |
| B — `@asynccontextmanager` | 7.07 / 7.47 | −0.7% / +0.9% | 9.41 / 9.55 | −0.1% / −0.7% |

**B is chosen.** A's cost is real and it is the predicted mechanism and nothing
else: ~4%, consistent across both pipeline shapes and across both statistics,
appearing identically whether the merge feeds `race_through()`'s yield or
`_release_in_order()`'s buffer — which is what a per-element charge looks like
and what a per-composition one does not. It is about a fifth of the reordering
half of the barrier again, so it is not lost in the racing machinery's own
noise. B is indistinguishable from baseline in all four figures, two of them
slightly negative.

The trade is that B buys twelve of the twenty lines. That is the right twelve:
the arm and the cleanup are *identical* between the callers, while the loop body
genuinely differs in what it does with a completed result. After B the two loops
read as two loops doing different things, rather than as one loop copied and
edited.

**An interleaved harness was necessary, not decorative.** A first pass ran the
variants in blocks and reported B at +3.3%, which is impossible for an extraction
that runs once per composition. Interleaving dissolved it. Anyone re-measuring
this path should interleave; block-sequential timings on it drift by more than
the effect being measured.

### Decision 2: `@asynccontextmanager`, not a class

`_maybe_aclosing()` is an `@asynccontextmanager` one screen up in the same file,
and the roadmap's guiding principle names it as an example of preferring
Python's own construct where Java would need a type. The lifecycle here is
exactly acquire/release: build the task dict, hand it over, tear it down on any
exit including an early one. A class would need a method per phase and would put
the `finally` somewhere other than where the pairing is visible.

Alternative considered: a plain helper pair (`_arm(branches)` /
`await _cancel_all(in_flight, branches)`). Rejected — it leaves each caller
responsible for writing its own `try`/`finally` correctly, which is precisely
the part that was already copied wrong once (Decision 3).

### Decision 3: both paths close their branches

Today `_release_in_order()` closes its branches and `race_through()` does not.
The extraction forces one answer, and the answer is to close in both.

`_release_in_order()`'s comment gives a windowed-path reason — "a branch parked
on the window has a finally of its own to run, and cancelling its in-flight
`anext()` alone would leave that to the garbage collector". That reason is
specific to the window, so it does not by itself establish that the unwindowed
path needs the close. But the reverse is not established either, and closing is
the conservative direction: `aclose()` on an exhausted or already-closing async
generator is a no-op, so unifying cannot double-close.

This is **not** a spec change. `racing-encounter-order` already requires the
shared source be "closed exactly as it is without a barrier ... and a delivery
barrier SHALL NOT change it either", with two scenarios asserting the close
counts are equal across the paths. Those scenarios are the regression gate for
this decision, and they exist already.

## Risks / Trade-offs

- **A future reader re-proposes A, not knowing it was priced** → Decision 1
  carries the table, the harness, and the interleaving caveat. Roadmap **Done**
  gets an entry saying A was measured and declined, since that is what **Done**
  is for.
- **The `async with` wraps a `yield` in an async generator** → this is the shape
  `stream_through()` already uses with `_maybe_aclosing()`, so the cleanup runs
  on `aclose()`/`GeneratorExit` exactly as it does there. The existing
  early-exit tests (`find_any`, `any_match`, ordered `limit()` over an unbounded
  source) drive that path.
- **Closing branches in the unwindowed path changes close counts** →
  `racing-encounter-order`'s two equal-close-count scenarios already assert it
  does not, and `stream-execution-model`'s "closeable source is still closed
  under racing" covers the other side. If either moves, the change is wrong, not
  the spec.
- **The remaining eight duplicated lines drift apart later** → accepted. They
  differ in payload handling already, and the alternative costs 4%.

## Migration Plan

Not applicable — one module, no public surface, no observable behaviour change,
so no migration-log entry and nothing to roll forward. Rollback is reverting one
commit.

## Open Questions

None. Decision 3 resolves the only one the exploration surfaced.

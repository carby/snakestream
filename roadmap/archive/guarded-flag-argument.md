+++
id = "guarded-flag-argument"
title = "`_guarded()`'s flag argument: asked, and answered in the affirmative"
filed = 2026-09-02
closed = 2026-09-05
outcome = "shipped"
+++

**`_guarded()`'s flag argument: asked, and answered in the affirmative**
(closed 2026-09-05; filed 2026-09-02 by the
`sort-mixed-lane-by-successive-passes` read, never scaffolded). Moved here
from **Now**, which is a pool of work available to start, and this is not
work any more. It is recorded as **closed rather than moot**, because
"the code was deleted" undersells what happened to it.

**The split it asked for is what the replacement does.** The finding wanted
one thing: `if window is None`, re-asked on every element to guard two
nearly-disjoint loop bodies, should become two generators each showing one
concern. `_fork_join_batches()` (`execution.py`) asks it once per *call* —
`through = _fork_join_ordered_batches if ordered else
_fork_join_unordered_batches` — and the two bodies are separate top-level
generators, one carrying the round protocol and one the sliding window. The
branch did not survive into the per-element path in another form; it moved to
dispatch, which is the outcome the finding argued for.

**Its own gate was applied, and passed.** The item named an honest objection
against itself: splitting duplicates the shared pull and the `finally` close,
and `extract-racing-task-lifecycle` (**Done**, 2026-09-02) is the precedent
saying only the genuinely identical parts belong together. That test was run.
`_fork_join_batches()` keeps exactly the identical scaffolding shared — the
state-map build, and the single `aiter(source)` under `maybe_aclosing()` —
while the two loops stay apart. So the finding's stated decision procedure
reached the opposite of the outcome its own text predicted ("it may well
decide against it"), by way of a change that was not about it at all.

**What is genuinely gone:** `_guarded()` and `race_through()` are deleted
along with the racing executor (`fork-join-executor-and-spliterator`,
2026-09-04). Nine comments in `src/` still name `RACING`, and two name
`_race_through()` — `execution.py:451` and `:483` — a function that exists
nowhere in the repo. Left deliberately: both spell out the reason they invoke
rather than merely pointing at it, so a reader who greps and finds nothing has
still been told what they needed. Filed here as a known, priced residue rather
than as an open item.

The finding follows as originally written, with its **Now**-bucket preamble
kept — "Not claimed", "Ranked as listed" — since that is what it said at
the time; the only edit is the removal of its superseded "Moot as of" header,
which this entry replaces.

One smaller finding from the same pass over `src/`, recorded rather than
scaffolded because the sort item was the one worth taking first. Not claimed.
**Ranked as listed.** Checked against **Done** before being filed here: it is
not a re-proposal of anything in the rejection log.

**The finding, as filed 2026-09-02.** `_guarded()` re-asks a question
decided at composition, once per pull.

`if window is None` is checked on every element, guarding two nearly-disjoint
loop bodies inside one `while True`, with only the `finally` genuinely shared.
The answer never changes for the life of the generator: `race_through()` passes
a window exactly on the split path and never on the other, so the branch is
settled before the first pull. It is the flag-argument shape, and splitting it
into two generators would let each show one concern — the windowed one
carrying the slot protocol and the index assignment, the plain one being
what it was before delivery ordering landed.

*The gate, and the honest objection.* This is a per-element path, so the `+10%`
threshold applies — but in the favourable direction for once, since the
branch is removed rather than added, which puts it in the same family as
`sort-mixed-lane-by-successive-passes` rather than in the family of the
rejections. The objection is real and should be priced before starting: it
*duplicates* the shared-lock pull and the `finally` close, and unifying exactly
that kind of scaffolding is what `extract-racing-task-lifecycle` (**Done**,
2026-09-02) set out to do. That change's own reasoning is the precedent to read
first — it kept arming and teardown shared while leaving the two merge loops
apart, on the grounds that only the identical parts belong together. The same
test applied here is what decides this item, and it may well decide against it.

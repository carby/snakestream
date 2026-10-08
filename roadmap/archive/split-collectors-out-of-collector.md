+++
id = "split-collectors-out-of-collector"
title = "`collectors.py` split out of `collector.py`, and four legibility gaps"
filed = 2026-08-26
closed = 2026-08-26
outcome = "shipped"
+++

**`collectors.py` split out of `collector.py`, and four legibility gaps**
(2026-08-26). Story 1 of the second 2026-08-25 batch, and the one the other
story waited on.

**The roadmap row was wrong about the blast radius, and that was the first
finding.** It called story 1 "private-surface only apart from one new public
exception base." `snakestream.collector` is public: README's quickstart
imports `to_generator` from it and 46 files under `tests/` imported factories
from it. Moving the factories is a **breaking import-path change**, and it
was surfaced and decided before any artifact was written rather than
discovered mid-apply. The user chose the Java-faithful break over a
re-export shim, an inverted split, or moving `to_generator` too.

**The split is `Collector` / `Collectors`, and it cost no invented name.**
`collector.py` keeps the protocol — `Collector`, `_CollectorSink`,
`StreamingCollector`, `_stream`, `to_generator` — at 114 lines.
`collectors.py` takes the ~22 factories plus `SummaryStatistics` and the
private helpers and container dataclasses only they use, at 545. The import
edge runs one way and is now visible as an import rather than implicit in
file ordering, the same shape the `sort.py`/`comparator.py` split settled
on. It also disentangled the `collector.py` -> `execution.py` import of
`_maybe_aclosing`, which existed solely for `_stream` and travelled with the
protocol half; two imports went dead in the process (`_maybe_await` in
`collector.py`, `type.A` in `collectors.py`) and were removed.

**`to_generator` stayed put, and that was the deliberate half of the
decision.** It is a `StreamingCollector` instance, not a factory, so it
belongs beside the type it instantiates — and the `collector-protocol` spec
already singled it out as "the one non-`Collector` collector". Moving it to
sit with the factories would have re-created, inside `collectors.py`,
exactly the two-things-in-one-module problem the split was fixing. It also
means README's quickstart import is unchanged.

**The move is provably verbatim.** Diffing the original
`collector.py:125-633` against `collectors.py` from `to_list` onward:
identical, byte for byte. That is what settles the benchmark question the
row raised — no factory body was reformatted or reordered, so no per-element
path could have been touched, and no harness run was needed. The remaining
`src/` diff is 42 insertions across four files, none inside an `accept()`
body or an accumulator inner function.

**`StreamException`, named by the user over `SnakestreamException`.** Java
has no common base for its stream exceptions, so the Java-parity rule did
not decide this one. Inserted above `StreamBuildException` and
`IllegalStateException`, source-compatible by construction. The temptation
refused was giving it a second base such as `ValueError` to soften the
previous batch's `to_map` break — refused for the reason that batch already
recorded: the same hierarchy covers stream-reuse errors, and a stream-reuse
error is not a `ValueError`. New capability `exception-hierarchy`, five
scenarios, five tests.

**`CLAUDE.md` was already describing a method that did not exist.** Its
"Sequential vs. parallel execution" section states that `.parallel()` /
`.sequential()` "go through `_derive_executor()`" — but the code called
`_derive(self._chain, EXEC)` directly and the two public methods carried the
same twelve-line docstring verbatim, which was the row's finding (b). The
fix made the code match the documentation rather than the other way round:
`_derive_executor()` now exists and owns the shared explanation, and both
public methods are one-liners. **Superseded 2026-08-26 by
`collapse-derive-wrappers`**, which read this entry the other way round: the
duplicated docstring was the real finding, and a wrapper method is not the
only way to hold it. `_derive_executor()` is gone again; `sequential()` owns
the explanation and `parallel()` points at it, so there is still exactly one
copy of it — and `CLAUDE.md` was corrected in the same change, which is the
half of this entry that still stands.

**The `TerminalSink` contract was documented, not changed.** The row was
explicit that the three dependents must not gain defensive `await`s, and
they did not: `_CollectorSink._create_container()` is still `def`, and
`grouping_by`'s and `partitioning_by`'s `_finish` still return the
un-awaited coroutine of `_finish_groups()`. Verified by grep after the edit,
not assumed.

**The tripwire had to be restated before it could hold.** "The suite passes
with no test file edited" is unachievable once 46 import lines move, so it
became mechanical: `git diff -U0 -- tests/` must show import lines only. It
did, across all 45 files that changed — no assertion touched.

**Coverage identity held exactly, which is the check the previous batch
taught.** Missed statements 2 -> 2, branches 288 -> 288, partial branches
26 -> 26; the uncovered set is the same two lines in `_summarizing`, now at
`collectors.py:192-193`. Total went 98.05% -> 98.05%. Compare the counts,
not the percentage.

**One thing the sync surfaced that the plan did not.** `collector-protocol`'s
main-spec `## Purpose` read "every `collector.py` factory returns", which the
requirement directly below it now contradicted. Corrected to `collectors.py`
— a module name this change itself renamed, not a Purpose rewrite — and
flagged rather than done silently.

567 tests green. `ruff`, `ruff format --check`, `ty check src` (output
identical to baseline), `--cov-fail-under=98` at 98.05%, and
`openspec validate --specs` at 37/37 all pass. Spec deltas on
`collector-protocol` (2 MODIFIED) and `exception-hierarchy` (new), plus two
README migration entries. See
`openspec/changes/archive/2026-08-26-split-collector-protocol-and-factories`.

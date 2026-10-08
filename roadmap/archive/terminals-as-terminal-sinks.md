+++
id = "terminals-as-terminal-sinks"
title = "Converted the terminal operations to real `TerminalSink`s"
filed = 2026-08-19
closed = 2026-08-19
outcome = "shipped"
+++

**Converted the terminal operations to real `TerminalSink`s**, closing the
half-conversion the Sink-chain redesign explicitly scoped out. `BaseStream`
gained `_drive_to(terminal)` — link the chain onto a terminal sink, push
source → head → terminal, return `terminal.result()` — and
`_drive_to_sequential(terminal)`, the never-overridden ordered form. The pair
mirrors the existing `_compose()`/`_drive()` split: `_drive_to()` dispatches
(`ParallelStream` overrides it), `_drive_to_sequential()` stays ordered on
either subclass. A new `src/snakestream/terminals.py` (206 lines) holds seven
terminal sinks — `_CountSink`, `_ForEachSink`, `_ReduceSink`, `_MinMaxSink`,
`_MutableReductionSink`, `_FindSink`, `_MatchSink` — plus `_UNSET`, which
moved out of `stream.py` since a sink cannot import it back. Every terminal
method in `stream.py` is now one or two lines; `stream.py` went from 215
statements to 111.

`_drive()`/`GeneratorBridgeSink` were kept for exactly what needs a
generator, as scoped: `iterator()`, `collect(collector)` (so `to_array()` and
every collector are untouched), `_concat`, the `sequential()`/`parallel()`
handoff, and `flat_map`'s inner-stream composition. No terminal reaches the
bridge any more, and the `TerminalSink` seat now has six real occupants that
use `_create_container`/`_finish`/`result()` as intended rather than
overriding them — which is the template the **Next**-bucket `Collector`
redesign needed, and which it is now **unblocked** by.

**Two behavior changes, both intended, neither breaking.** (a) Short-circuiting
terminals now report `cancellation_requested()`, so a settled `any_match` /
`all_match` / `none_match` / `find_first` / `find_any` stops the whole chain
instead of abandoning a generator: `.peek(fn).any_match(p)` calls `fn` once,
not once per element, and `.flat_map(m).find_first()` takes one element from
the first inner stream and closes it rather than draining it. A user relying
on a side-effecting `peek()` or mapper firing past the short-circuit point
would see the difference — it is the same class of fix `limit()` got, so it is
a behavior note rather than a **BREAKING** migration-log entry; no signature
or return value changed. (b) `ParallelStream` terminals gained cancellation at
the outer loop only.

**`ParallelStream` drives the terminal over the racing generator** rather than
sharing one terminal sink across the branches: `_drive_to()` is overridden to
push `_compose()`'s output into the single terminal. Parallel semantics are
therefore identical to before and the bridge's cost stays on that path — the
measured win is sequential-only. Sharing a terminal across branches was
rejected: it would make `begin()`/`end()` refcounted, the accumulator
concurrently mutated, and would need `_ReduceSink`/`_MinMaxSink` to define a
merge across partitions, which is exactly the `combiner` work parked in
**Later** behind real partitioned execution. Consequence, accepted: an
in-flight branch's own `_LimitSink`/`_FlatMapSink` never sees a terminal's
cancellation, since the terminal is not in that branch's chain. `_parallel()`'s
existing `finally:` already cancels and gathers the pending tasks, so teardown
is clean — a missed optimization, not a correctness gap.

**One defect found by the new tests, and one fix beyond the planned scope.**
`_FindSink.accept()` initially overwrote its container on every element, which
is correct only if nothing pushes after cancellation — but `_SortedSink.end()`
flushes its entire buffer downstream in one go with no driving loop in
between, so `.sorted().find_first()` returned the *last* element. Fixed by
guarding both short-circuiting sinks to ignore anything pushed after they
settle. That exposed the real gap one level up: `_SortedSink.end()` did not
check `cancellation_requested()` while flushing, so `peek()` still fired for
every element after the answer was known. Added that check between pushes
(`ops.py`), mirroring `_FlatMapSink`'s existing inner-loop check — two lines,
outside the change's planned task list, but without it the change's headline
benefit has a hole for any chain containing `sorted()`. The terminal-side
guards were kept rather than resting on that invariant and are pinned by
direct sink-level tests.

**Benchmark (2026-08-19, same harness: Python 3.14.5, 20,000 elements, chain
of 8 `.map()` ops, best of 5, three interleaved rounds per condition via
`git stash`; best round per condition shown, round 1 was a cold outlier for
both):**

| Scenario | Before | After | Δ |
|---|---|---|---|
| `collect(to_list)` — unchanged generator path, control | 1974.3 | 2004.7 | ~flat |
| `count()` | 1938.5 | 1644.3 | **−15.2%** |
| `for_each()` | 1982.4 | 1622.9 | **−18.1%** |
| `reduce()` | 1994.1 | 1671.6 | **−16.2%** |

The flat control on the generator path is what rules out machine drift: only
the paths that stopped round-tripping through the bridge moved. This recovers
a good part of what the redesign measured and gave back to the buffer-and-yield
step, as that item predicted.

No public API change — every name added is private and unexported, so README
needed no parity-table or migration-log edit. All 421 pre-existing tests pass
**unmodified**, which was the primary regression signal; 27 new tests were
added (`tests/test_terminal_sinks.py`, plus two protocol-level cases in
`tests/test_sink.py`) covering `reduce()`'s reseeding edge cases, terminal
cancellation reaching `peek`/`limit`/`flat_map`, the ordered drive on a
`ParallelStream`, parallel terminals, and the two short-circuit guards. 448
tests pass at 99% coverage (98.63% branch), `terminals.py` at 100%. New
`terminal-sinks` spec; `sink-protocol` and `pipeline-composition` extended for
terminal-originated cancellation. See
`openspec/changes/convert-terminals-to-sinks`.

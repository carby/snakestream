## Why

Four small blemishes have been sitting in the roadmap's **Now** bucket, each
one deliberately parked behind larger work that has now landed or been
rejected: the collector API reads inconsistently (`collect(to_list)` next to
`collect(to_set())` for two equally stateless collectors), the parallel race
loop allocates and linear-scans once per element, `_maybe_aclosing` is a
hand-rolled class where the stdlib offers a decorator, and private accumulator
box types are named in public return signatures. None of them is blocked any
more, and none depends on the others, so they can be taken as one batch of
independently revertable edits.

## What Changes

- **BREAKING** — (a) `to_list` becomes a factory, `to_list()`, matching
  `to_set()`, `counting()`, `joining()` and every other collector factory the
  library ships, and matching Java's `Collectors.toList()`. Today it is the
  single bare `Collector` instance in the public surface, so the API reads
  inconsistently for two collectors that are equally stateless. The internal
  call sites that use it as a default argument (`grouping_by`,
  `partitioning_by`) and `to_array()`'s implementation move to the called
  form. Follows the project's pre-1.0 convention: hard break plus a
  migration-log line, as `Stream.concat` just did.
- (b) `parallel_stream.py`'s race loop stops allocating a throwaway list per
  iteration (`any([n is not None for n in tasks])`) and stops paying a linear
  `tasks.index(task)` scan per element. Behaviour-neutral.
  **Measured** on the established harness (Python 3.14.5, 20,000 elements,
  no intermediate chain so the race loop is the whole cost, best of 5, three
  independent invocations), driving `_parallel()` directly:

  | Branches | Baseline ns/element | After ns/element | Median delta |
  |---|---|---|---|
  | `processes=4` (the default) | 6666 / 6712 / 6695 | 6405 / 6631 / 6674 | **-1.0%** |
  | `processes=16` | 5057 / 5054 / 5137 | 5020 / 5016 / 4996 | **-0.8%** |

  That is the honest outcome the design named in advance: **no measurable
  win, taken for clarity**, and comfortably clear of the no-regression gate.
  The reason is visible in the absolute numbers — at ~6.7 microseconds per
  element the cost is `asyncio.wait()`'s own per-call set construction and
  task scheduling, which dwarfs a 4- or 16-entry scan by three orders of
  magnitude. The scan was never going to show up; removing it is a clarity
  and complexity win, not a throughput one.
- (d) `_maybe_aclosing` collapses from a 14-line class to an
  `@asynccontextmanager` generator of about five lines. Behaviour-neutral; it
  stays private and keeps its exact semantics, including the no-op close for
  sources with no `aclose()`.
- (e) Private accumulator box types stop appearing in public return
  signatures — `summing_int() -> Collector[Any, _SumBox, int]` and its
  siblings widen their `A` parameter to `Any`, so no caller has to name a
  private type to annotate a variable. The boxes themselves stay private and
  unchanged.

Non-goals: no change to what any collector computes, to racing semantics or
ordering, to close semantics, or to the accumulator boxes' own structure.
Part (c) of the roadmap batch (`_CountSink`'s `Counter` box) is already done
and is not in scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `collector-protocol`: the requirement that `to_list` "SHALL remain usable as
  a bare name — `collect(to_list)`, not `collect(to_list())`" inverts. `to_list`
  becomes a factory returning a fresh `Collector`, like every other factory in
  `collector.py`.
- `stream-to-array`: its requirement text defines `to_array()` by equivalence
  to `collect(to_list)`; that equivalence is restated against `collect(to_list())`.

Six further capabilities quote the bare `collect(to_list)` form inside
requirement or scenario text. Nothing about what they require changes — the
call form they illustrate it with does, and leaving it would have them naming a
call that now raises `StreamBuildException`. Found while grepping for stragglers
after the rename, not anticipated when this proposal was first written:

- `collector-mapping`: `mapping(len, to_list)` in three scenarios.
- `collector-collecting-and-then`: `collecting_and_then(to_list, ...)` in three scenarios.
- `pipeline-immutability`: `collect(to_list)` in three scenarios across three requirements.
- `stream-iterator`: `collect(to_list)` as the comparison terminal in two requirements.
- `terminal-sinks`: `to_array()`'s `collect(to_list)` named as the non-bridge path.
- `generic-stream-typing`: `Stream[int].collect(to_list)` as the typed-return example.

## Impact

- `src/snakestream/collector.py` — `to_list` definition, the `grouping_by` /
  `partitioning_by` default arguments, and the public return annotations of
  `summing_*`, `averaging_*`, `summarizing_*`, `min_by`/`max_by`, `reducing`,
  `to_map`, `grouping_by`, `partitioning_by`, `mapping`,
  `collecting_and_then`, `counting`.
- `src/snakestream/base_stream.py` — `_maybe_aclosing` (private; two call
  sites here, one in `collector.py`, one in `parallel_stream.py`).
- `src/snakestream/parallel_stream.py` — `_parallel()`'s race loop only.
- `src/snakestream/terminals.py` / wherever `to_array()` calls `to_list`.
- Tests: every `collect(to_list)` call site across the suite moves to
  `collect(to_list())`. This is the tripwire in reverse — for (b), (d) and (e)
  the suite must stay green with no test edited at all.
- Docs: `README.md`'s API table row for `to_list` (kind column: instance ->
  factory) plus a new migration-log entry; `CLAUDE.md` mentions of `to_list`;
  the roadmap item moves to **Done**.

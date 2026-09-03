## Why

The leading underscore in `src/snakestream` does not mean what it says. It is
being used as a public-API marker, and the package has no public API to mark:
`__init__.py` exports `Stream` and `PROCESSES`, and everything a caller
actually imports — `to_list()`, `comparing()`, `StreamException`,
`to_generator` — is reached through a module path, bare-named, and untouched
by the convention. What the underscore has come to mark instead is
"implementation detail", which is a claim every module in this package could
make about every name it holds.

The result is 27 names that are underscored **and imported by another
module**, which is a contradiction in terms:

| Defined in | Imported by | Names |
|---|---|---|
| `ops.py` | `stream.py` | `_FilterOp` `_MapOp` `_PeekOp` `_SortedOp` `_UnorderedOp` `_FlatMapOp` `_DistinctOp` `_LimitOp` `_SkipOp` |
| `terminals.py` | `stream.py` | `_CountSink` `_ForEachSink` `_ReduceSink` `_MinMaxSink` `_FindSink` `_MatchSink` |
| `sink.py` | `collectors`, `stream`, `terminals` | `_UNSET` `_UnseededSink` `_unseeded` |
| `callable_dispatch.py` | `collectors`, `sink` | `_maybe_await` `_classify_step` |
| `type.py` | `execution`, `collectors` | `_Aiter` `_C` `_M` |
| `collector.py` | `stream` | `_CollectorSink` |
| `execution.py` | `collector` | `_maybe_aclosing` |
| `ordering.py` | `execution` | `_split_point` |
| `comparator.py` | `sort` | `_ASYNC_COMPARATOR_MESSAGE` |

Fifteen of them are the op and sink classes, whose entire reason to exist is
that `stream.py` imports them. The underscore tells the one module that must
touch them not to.

The tell that the convention has stopped carrying information is
`ordering.py`, extracted three days ago: it holds two module-level folds over
a chain, called by the same module for the same reason, and one is
`is_ordered()` while the other is `_split_point()`. Nothing distinguishes them
except which side of an unwritten rule each landed on. `sink.py` says it
louder — nine bare internal names (`Op`, `Sink`, `Box`, `TerminalSink`, …)
beside four underscored ones, all equally internal, in one file no caller
imports.

**Why now.** Pre-1.0, with little to no usage, a rename sweep costs an
afternoon and a migration-log entry. After 1.0 the same sweep is a semver
event, and the convention will by then have produced another dozen names that
have to be argued about one at a time.

## What Changes

Three stories, one rule between them:

> A module-level name carries a leading underscore **iff** it is used only
> inside the module that defines it. A name imported by another module in
> `src/snakestream`, or reachable by a caller as part of the documented API,
> is bare. `tests/` may import anything; a test reaching into a private name
> is white-box testing, not a violation, and does not make that name public.

- **Story 1 — the 27 renames.** Every name in the table above drops its
  underscore. No behaviour, argument, or call site changes; the diff is the
  definition line, the import lines, and the use sites. Two of them get more
  than a character removed:
  - `_C` -> `C` and `_M` -> `M` are Java's own names for these two type
    parameters (`Collectors.toCollection`'s `<C extends Collection<T>>`,
    `Collectors.toMap`'s `<M extends Map<K,U>>`), so the Java-faithful reading
    and the rule agree. Their bound `_SupportsAdd` stays private — it is used
    only in `type.py`.
  - `_UNSET` -> `UNSET` also stops a private-marked name from appearing as a
    default in a public signature: `reducing(identity=_UNSET, ...)` renders
    that name in `help()` today.

- **Story 2 — the reverse pass.** Eight bare names that are used only in
  their own module and are not caller-facing gain the underscore, so the rule
  reads in both directions and `sink.py`'s mixed state is not simply
  reproduced elsewhere: `execution.py`'s `stream_through`, `group_through`,
  `race_through`, `feed_through`, `drain`, `Sequential`, `Racing`, and
  `sort.py`'s `merge_sort`. `Executor`, `SEQUENTIAL` and `RACING` stay bare —
  `stream.py` imports all three.

- **Story 3 — `PROCESSES` leaves the export surface. BREAKING.** It is
  removed from `snakestream/__init__.py` and from `stream.py`'s
  `from snakestream.execution import PROCESSES as PROCESSES` re-export. It
  stays in `execution.py` under that name, so README's "we're keeping the
  `.parallel()`/`PROCESSES` naming" paragraph stays true.

  The export claims to be a tuning lever and is not one: `execution.py` binds
  `RACING = Racing(PROCESSES)` at import, so assigning
  `snakestream.PROCESSES = 8` changes nothing a pipeline does. README names it
  once, in a paragraph about *why the name is not being changed*, never in a
  code example and never in an import. Java's Stream API exposes no
  counterpart — parallelism width lives in `ForkJoinPool.commonPool()`, not on
  `Stream` — so the guiding 1:1-public-surface principle argues against it
  too. And `test_package_exports.py` already argues at length that
  `_IN_FLIGHT_PER_WORKER` must have no public name because "the levers a
  caller is given for its cost are `unordered()` and `sequential()`, not a
  number"; `PROCESSES` is the same kind of import-time-bound constant and gets
  the opposite treatment in the same file.

Explicitly **not** in scope: `__init__.py` growing into the package's public
surface (considered and declined — see design decision 1); renaming modules to
`_execution.py`-style private paths; moving
`_ASYNC_COMPARATOR_MESSAGE` to `exception.py` beside `_RESULT_TYPE_MESSAGE`
(it is already named once and shared by two modules, which is the whole job a
move would do); any change to class-member privacy, including
`Stream._is_ordered()`, `_chain`, `_derive()` — the rule is about module-level
names, and no `__init__.py` can hide a method; and anything on the per-element
path.

## Capabilities

### New Capabilities

- `internal-name-visibility`: the naming rule above, stated as a requirement
  over `src/snakestream`, plus the check that keeps it from drifting back — a
  test asserting no module under `src/snakestream` imports an
  underscore-prefixed name from another module in the package.

### Modified Capabilities

- `stream-execution-model`: the requirement **"PROCESSES is part of the
  package's public export surface"** is removed, along with its scenario.
  Story 3 makes it false by intent.

## Impact

- **Code:** all ten modules under `src/snakestream` plus `__init__.py`.
  Definition lines, import lines and use sites only; no argument, branch or
  call order changes. One incidental deletion: `Op.__repr__`'s
  `removeprefix("_")` becomes dead once no `Op` subclass is underscored, and
  its docstring's `_FlatMapOp -> flat_map` example goes stale.
- **Tests:** import lines in the modules that reach into renamed names
  (`test_racing_encounter_order`, `test_unordered`, `test_callable_dispatch`,
  `test_terminal_sinks`, `test_execution_model`), plus
  `test_package_exports.py`, whose `PROCESSES` assertions invert and whose
  `_IN_FLIGHT_PER_WORKER` argument then applies to both constants. One new
  test module for the invariant. No test body or assertion changes otherwise.
- **Public API:** one removal, `PROCESSES`, from two import paths. Every other
  renamed name was absent from `__init__.py` and undocumented, so no parity
  row moves.
- **Docs:** README gains one Migration-log entry for `PROCESSES`. `CLAUDE.md`
  updates the five execution verbs in its architecture block, `_split_point`,
  `_CollectorSink` and the `_FlatMapOp` repr example. The rule itself is
  recorded in `CLAUDE.md` so the next contributor does not have to rediscover
  it from the diff.
- **Performance:** none. Every rename resolves at import time.

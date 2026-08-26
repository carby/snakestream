## Why

`collector.py` is 633 lines, 1.7x the next largest module in
`src/snakestream/`, and it holds two unrelated things: the collector
*protocol* (`Collector`, `_CollectorSink`, `StreamingCollector`,
`_stream`/`to_generator`) and the ~20 collector *factories* (`to_list`,
`grouping_by`, `summing_int`, ...). Java already names this pair —
`Collector` is the interface, `Collectors` the factory holder — so the split
lands on this project's Java-parity naming rule without inventing a term, and
follows the precedent it has set twice already (`sink.py`/`ops.py`,
`sort.py`/`comparator.py`). It also disentangles the
`collector.py` -> `execution.py` import of `_maybe_aclosing`, which exists
solely for `_stream`/`to_generator` and travels with the protocol half.

Four smaller legibility gaps ride along, all in or adjacent to the lines that
move: two duplicated docstrings, one undocumented base-class contract, the
last hand-written `__slots__` container, and an exception hierarchy with no
catch-everything root.

## What Changes

- **BREAKING** — The collector factories move from `snakestream.collector` to
  a new `snakestream.collectors` module.
  `from snakestream.collector import to_list` stops working and becomes
  `from snakestream.collectors import to_list`. This breaks loudly
  (`ImportError`). The names that move: `to_list`, `to_set`, `to_collection`,
  `to_map`, `joining`, `counting`, `summing_int`, `summing_long`,
  `summing_double`, `averaging_int`, `averaging_long`, `averaging_double`,
  `summarizing_int`, `summarizing_long`, `summarizing_double`,
  `SummaryStatistics`, `min_by`, `max_by`, `reducing`, `grouping_by`,
  `partitioning_by`, `mapping`, `collecting_and_then` — plus the private
  helpers and container dataclasses only they use.
- `snakestream.collector` keeps the protocol half, unchanged and unmoved:
  `Collector`, `_CollectorSink`, `StreamingCollector`, `_stream` and
  `to_generator`. **`to_generator` stays where it is** — it is a
  `StreamingCollector`, not a factory, so README's quickstart import of it
  does not change.
- **New public `StreamException`** in `snakestream.exception`, inserted as the
  base of both `StreamBuildException` and `IllegalStateException`, so a caller
  can catch anything this library raised. Non-breaking by construction:
  inserting a base above two existing classes leaves every existing
  `except StreamBuildException` / `except IllegalStateException` working.
  Neither leaf is renamed and no third exception is introduced.
- `Stream.sequential()` and `Stream.parallel()` stop carrying the same
  twelve-line docstring verbatim.
- `TerminalSink`'s docstring states the contract its three dependents already
  rely on: `_create_container()` and `_finish()` may return awaitables, since
  `begin()`/`end()` route both through `_maybe_await`. The contract is
  documented, not changed — no defensive `await`s are added at the three
  dependent sites.
- `Box` (`sink.py`) becomes `@dataclass(slots=True)`, joining the nine
  containers the previous batch's story 6 converted.

## Capabilities

### New Capabilities
- `exception-hierarchy`: the public exception types this library raises and
  the common base every one of them derives from.

### Modified Capabilities
- `collector-protocol`: its "every collector is a factory" requirement names
  `collector.py` as where those factories live. That module becomes
  `collectors.py`, and the import path callers write is part of the
  observable public API.

## Impact

- **Code**: `src/snakestream/collector.py` (split), new
  `src/snakestream/collectors.py`, `src/snakestream/exception.py`,
  `src/snakestream/sink.py`, `src/snakestream/stream.py`.
- **Public API**: the import path for the factory names above; one added
  exception base. The behaviour of every collector, and of `collect()`, is
  unchanged.
- **Tests**: 46 test files import from `snakestream.collector` and need the
  path updated. No test's *assertions* change — the suite passing with only
  import lines edited is this change's tripwire.
- **Docs**: README's collector table and a new Migration entry; `CLAUDE.md`'s
  Collectors section names `collector.py` as the factories' home.
- **Not touched**: no per-element path. Every site here runs once per module
  import, once per stream construction, or once per collection, so this change
  does not face the benchmark gate. A diff reaching a per-element path is the
  signal it went wider than the change.

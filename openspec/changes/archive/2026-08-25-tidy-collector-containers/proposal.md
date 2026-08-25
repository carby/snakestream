## Why

`collector.py` hand-writes nine `__slots__`-plus-`__init__` accumulation
containers — roughly ninety lines whose entire content is a field list written
twice. `@dataclass(slots=True)` generates exactly that, and has since Python
3.10, the project's floor. In the same read, two smaller defects surfaced next
to them: `sink.py`'s `Counter` shadows `collections.Counter` while adding one
thing to `Box` — a default of `0` — and `to_map()` raises `ValueError` on a
duplicate key where Java's `Collectors.toMap` throws `IllegalStateException`, a
class this project already defines in `exception.py` and already raises for
pipeline reuse.

This is story 6 of the 2026-08-25 legibility batch, the last one open. It was
always independent of the other five, so nothing sequenced it after them.

## What Changes

- Replace the nine hand-written containers in `collector.py` — `_SumBox`,
  `_AvgBox`, `_SummaryBox`, `_ExtremumBox`, `_ReduceBox`, `_ToMapBox`,
  `_GroupBox`, `_MappingBox`, `_CollectAndThenBox` — with
  `@dataclass(slots=True)` declarations. Field names, types, defaults and
  construction sites stay as they are; only the boilerplate goes.
- **BREAKING (internal):** delete `Counter` from `sink.py`. Its two callers in
  `ops.py` (`make_shared_state()` for limit and skip) and `counting()`'s
  supplier in `collector.py` construct `Box(0)` instead. `Counter` is not
  exported from `snakestream`, but it is imported and constructed by
  `tests/test_sink.py`, so that file moves to `Box`.
- **BREAKING (public):** `to_map(key_mapper, value_mapper)` raises
  `IllegalStateException` instead of `ValueError` when `key_mapper` produces
  the same key for two different elements and no `merge_function` was given.
  `IllegalStateException` stays a direct `Exception` subclass, so this is a
  loud break for `except ValueError` call sites. Needs a README migration-log
  entry alongside the `str`/`bytes` and kwargs entries.

The nine-container part is **not** the rejected `CallSite` proposal. Those
containers are constructed once per collection, never per element; attribute
access after construction is byte-for-byte what it is today, because
`slots=True` produces the same descriptors the hand-written `__slots__` does.
Nothing here can land on the per-element path, which is what the `CallSite`
rejection was about.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `collector-to-map`: the requirement "`to_map` raises on duplicate key with no
  merge function" changes the raised type from `ValueError` to
  `IllegalStateException`, and its scenario changes with it.

## Impact

- `src/snakestream/collector.py` — nine container classes; `counting()`'s
  supplier; `to_map()`'s duplicate-key raise; the `Counter` import.
- `src/snakestream/sink.py` — `Counter` removed.
- `src/snakestream/ops.py` — two `make_shared_state()` bodies and the import.
- `src/snakestream/terminals.py` — two comment lines that name `Counter`.
- `tests/test_sink.py` — `Counter` import and its five construction sites
  (lines 4, 277-278, 304, 326-327, 336) become `Box`.
- `tests/test_to_map.py:47` — `pytest.raises(ValueError)` becomes
  `pytest.raises(IllegalStateException)`.
- `README.md` — collector table entry for `to_map` if it names `ValueError`,
  plus a new migration-log entry.
- No new dependencies. No change to the per-element path, so no benchmark run.

## 1. `mapping()`

- [x] 1.1 Implement `mapping(mapper, downstream)` in `collector.py`, reusing `_check_downstream` and `_maybe_await`/mapper-dispatch (as `_summing`/`_averaging` do) to build a `Collector` that maps then delegates to `downstream`.
- [x] 1.2 Add tests covering: sync mapper, async mapper, empty stream, composing with a non-`to_list` downstream (e.g. `counting()`), and rejecting a non-`Collector` `downstream`.

## 2. `collecting_and_then()`

- [x] 2.1 Implement `collecting_and_then(downstream, finisher)` in `collector.py`: same supplier/accumulator as `downstream`, with a finisher that runs `downstream`'s (possibly already-finished) result through `finisher` (sync or async, via `_maybe_await`).
- [x] 2.2 Add tests covering: sync finisher, async finisher, a downstream that already has its own finisher (`counting()`), empty stream, and rejecting a non-`Collector` `downstream`.

## 3. `summarizing_int()`/`summarizing_long()`/`summarizing_double()`

- [x] 3.1 Add a `SummaryStatistics` `NamedTuple` (`count`, `sum`, `min`, `max`, `average`) near the other collector result types.
- [x] 3.2 Implement a shared `_summarizing(mapper, seed, coerce)` builder mirroring `_summing`'s `is_async`/`checked` dispatch pattern, tracking count/sum/running-min/running-max, and finishing to `SummaryStatistics` (`min=None`/`max=None`, `average=0.0` on zero elements).
- [x] 3.3 Implement `summarizing_int`/`summarizing_long` (`coerce=None`) and `summarizing_double` (`coerce=float`, seed `0.0`) as thin wrappers over `_summarizing`, matching the `summing_int`/`summing_long`/`summing_double` split.
- [x] 3.4 Add tests covering: basic summary values, `summarizing_long` matching `summarizing_int`, `summarizing_double` coercion to `float`, async mapper, and the empty-stream `min=None`/`max=None`/`average=0.0`/`count=0`/`sum=0` case.

## 4. `to_collection()`

- [x] 4.1 Implement `to_collection(collection_supplier)` in `collector.py`: supplier calls `collection_supplier()`, accumulator calls `container.add(element)` unconditionally, no finisher.
- [x] 4.2 Add tests covering: `to_collection(set)`, a custom container class implementing `add`, two `collect()` calls against the same collector instance getting independent containers, and an empty stream.

## 5. Docs and parity tracking

- [x] 5.1 Add `mapping`, `collecting_and_then`, `summarizing_int`/`summarizing_long`/`summarizing_double`, and `to_collection` rows to README's Collectors table.
- [x] 5.2 Update README's Java 8 `Collectors` parity notes so these four no longer read as outstanding.

## 6. Verification

- [x] 6.1 `uv run pytest --cov-fail-under=98`
- [x] 6.2 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 6.3 `uv run ty check src`

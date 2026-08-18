## 1. Dispatch primitive

- [ ] 1.1 Add `is_async_callable(fn) -> bool` to `callable_dispatch.py`:
      returns `True` for a plain `async def` function (`iscoroutinefunction`)
      and for a callable object whose `type(fn).__call__` is `async def`.
- [ ] 1.2 Keep `_maybe_await` as-is for per-composition call sites; do not
      delete it.
- [ ] 1.3 Decide and document the canonical inline shape (a short comment in
      `callable_dispatch.py` next to `is_async_callable`), so the 26
      per-element sites are all written the same way:
      hoisted `is_async` + `checked` locals **inside** the per-composition
      generator body, `if is_async: await` / `elif not checked:` first-result
      `isawaitable` confirmation that may flip `is_async` to `True`.

## 2. stream.py call sites (9 per-element)

- [ ] 2.1 `filter()` predicate (`stream.py:144`).
- [ ] 2.2 `map()` mapper (`stream.py:153`).
- [ ] 2.3 `peek()` consumer (`stream.py:204`).
- [ ] 2.4 `_collect_mutable()` accumulator (`stream.py:243`). Leave the
      `supplier` at line 241 on `_maybe_await` — it is invoked once per
      composition.
- [ ] 2.5 `reduce()` accumulator (`stream.py:267`).
- [ ] 2.6 `for_each()` consumer (`stream.py:273`).
- [ ] 2.7 `for_each_ordered()` consumer (`stream.py:279`).
- [ ] 2.8 `_min_max()` comparator (`stream.py:307`) — hoist above the
      `async for`, keeping the existing `check_comparator_result_type(sign)`
      guard unchanged.
- [ ] 2.9 `_match()` predicate (`stream.py:331`), covering `all_match`,
      `any_match` and `none_match`.

## 3. collector.py call sites (15)

- [ ] 3.1 `summing_int`/`summing_long`/`summing_double` mappers
      (`collector.py:79,91,103`), preserving `summing_double`'s `float()`
      coercion.
- [ ] 3.2 `averaging_int`/`averaging_long`/`averaging_double` mappers
      (`collector.py:116,130,144`).
- [ ] 3.3 `min_by`/`max_by` comparator (`collector.py:153`), keeping the
      `check_comparator_result_type` guard unchanged.
- [ ] 3.4 `reducing` mapper and binary operator (`collector.py:217,221`).
      The mapper site is conditional (`n if mapper is None else ...`) — hoist
      the `mapper is None` test out of the loop alongside the classification.
- [ ] 3.5 `to_map` key mapper, value mapper and merge function
      (`collector.py:235,236,240`). Classify all three; the merge function is
      invoked only on collision, so its first-result confirmation happens on
      the first collision rather than the first element.
- [ ] 3.6 `grouping_by` classifier (`collector.py:269`).
- [ ] 3.7 `partitioning_by` predicate (`collector.py:283`), preserving the
      `bool(...)` coercion.

## 4. sort.py call site (1, invoked per comparison)

- [ ] 4.1 `_merge()` comparator (`sort.py:25`). `_merge` is called repeatedly
      across one `merge_sort` run, so hoist classification to `merge_sort`'s
      entry and thread the result into `_merge` rather than classifying per
      `_merge` call.

## 5. Tests

- [ ] 5.1 Extend `tests/test_callable_dispatch.py` with direct
      `is_async_callable` coverage: plain sync function, `async def` function,
      sync-`__call__` object, async-`__call__` object, and `functools.partial`
      wrapping each.
- [ ] 5.2 Add the sync-`__call__`-returning-a-coroutine regression test — a
      callable whose `__call__` is plain `def` but returns a coroutine — for
      `map`, `filter` and at least one collector, asserting real values rather
      than un-awaited coroutine objects. This is the case build-time
      classification alone gets wrong and the first-result check exists for.
- [ ] 5.3 Add a classification-does-not-leak-across-compositions test:
      compose and consume a chain twice, asserting the second run is correct
      (mirrors the existing `fix-stream-rerun-state` regression pattern).
- [ ] 5.4 Add `ParallelStream` coverage: an async-`__call__` mapper across
      racing branches still produces awaited values.
- [ ] 5.5 Re-run the existing async-callable-object suite unchanged — every
      case in `tests/test_callable_dispatch.py` must still pass without
      modification.
- [ ] 5.6 Verify the coverage gate still passes at `--cov-fail-under=98`. The
      `elif not checked:` branch is taken exactly once per composition, so
      both arcs are naturally exercised; no `pragma: no cover` should be
      needed.

## 6. Verification

- [ ] 6.1 Re-run the benchmark from `design.md` against the implemented
      change and confirm the k=8 figure lands near 2,064 ns/element (from
      5,775). Record the measured before/after in the roadmap Done entry.
- [ ] 6.2 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run ty check src`.

## 7. Docs

- [ ] 7.1 Update README's migration log: the dispatch contract narrows from
      per-result to per-callable-per-composition, tracked as **BREAKING** per
      `CLAUDE.md`'s convention.
- [ ] 7.2 Update roadmap.md: move this item to **Done** with a summary and the
      measured numbers.

## 1. Exception and flag plumbing

- [x] 1.1 Add `class IllegalStateException(Exception): pass` to `src/snakestream/exception.py`
- [x] 1.2 Add `self._consumed: bool = False` to `BaseStream.__init__` (`base_stream.py`)
- [x] 1.3 Add a `BaseStream._derive(new_closure)` helper: raises `IllegalStateException` if `self._consumed`; otherwise builds a new `Stream`/`ParallelStream` (matching `self`'s concrete class) sharing `self._stream` by reference, with `_chain = self._chain + [new_closure]` and `_ordered = self._ordered`, `_close_handlers = self._close_handlers`; sets `self._consumed = True`; returns the new instance
  - Discovered during implementation: `BaseStream.__init__`'s `self._close_handlers = close_handlers or []` treated an *empty* list as falsy, silently discarding the passed-in reference and creating a new list instead. This was invisible before since intermediate ops never re-invoked the constructor; `_derive()` does, on every op, so an empty handler list stopped being shared the moment any op ran before the first `on_close()`. Fixed to `[] if close_handlers is None else close_handlers`.

## 2. Intermediate ops

- [x] 2.1 Convert `map()` (`stream.py`) to build its closure and return `self._derive(fn)`
- [x] 2.2 Convert `filter()` to the same pattern
- [x] 2.3 Convert `flat_map()` to the same pattern
- [x] 2.4 Convert `sorted()` to the same pattern
- [x] 2.5 Convert `distinct()` to the same pattern (closure is `_DistinctOp()`)
- [x] 2.6 Convert `peek()` to the same pattern
- [x] 2.7 Convert `limit()` to the same pattern (closure is `_LimitOp(max_size)`)
- [x] 2.8 Convert `skip()` to the same pattern (closure is `_SkipOp(n)`)

## 3. Mode switches

- [x] 3.1 Add the `self._consumed` check (raise if set) to the top of `sequential()` (`base_stream.py`)
- [x] 3.2 Add `self._consumed = True` on the receiver at the end of `sequential()`, after constructing the new `Stream`
- [x] 3.3 Add the same check-and-set pair to `parallel()`

## 4. Terminal ops

- [x] 4.1 Add the `self._consumed` check (raise if set, no set) to the top of every terminal op in `stream.py`: `collect` (both overloads), `reduce` (both overloads), `for_each`, `for_each_ordered`, `find_any`, `find_first`, `max`, `min`, `all_match`, `any_match`, `none_match`, `count`, `to_array`
  - Implemented the `max`/`min` check once in the shared `_min_max()` helper, and `all_match`/`any_match`/`none_match`'s once in the shared `_match()` helper, rather than duplicating in each public wrapper.
- [x] 4.2 Add the same check to `BaseStream.iterator()` (`base_stream.py`)
- [x] 4.3 Add the same check to `ParallelStream.find_first()`'s override (`parallel_stream.py`)
- [x] 4.4 Confirm `on_close()`/`close()` (`base_stream.py`) are left untouched — no check added

## 5. Tests

- [x] 5.1 Add `tests/test_pipeline_immutability.py` covering: each of the 8 intermediate ops returns a distinct object (`is not`) from the receiver
- [x] 5.2 Add coverage: calling any intermediate op a second time on an already-`_derive()`'d receiver raises `IllegalStateException`, for each of the 8 ops
- [x] 5.3 Add coverage: calling any terminal op (parametrized across all of them, sequential and parallel) on an already-extended receiver raises `IllegalStateException`
- [x] 5.4 Add coverage: `sequential()`/`parallel()` invalidate the pre-switch reference (both directions)
- [x] 5.5 Add coverage: the new instance returned by `_derive()`/mode-switch is fully usable (chain continues, terminal ops succeed)
- [x] 5.6 Add non-regression coverage: a never-extended reference still supports a second terminal call without raising, including the existing exhausted-source-yields-empty case (re-run `test_distinct_state_fresh_on_second_composition`-style assertions to confirm no regression)
- [x] 5.7 Add coverage: `on_close()`/`close()` remain callable on an already-extended reference, and handlers registered on a derived instance still fire via the original reference (mirrors `test_close_after_stream_switch`/`test_close_after_sequential_switch`, confirm those two existing tests still pass unmodified)
- [x] 5.8 Verify existing full suite passes unmodified (no test currently holds and reuses a pre-extension reference, per explore-session grep)
  - Full suite passed only after fixing the `close_handlers or []` bug found in 1.3 above; `test_close_simple`/`test_close_after_stream_switch`/`test_close_after_sequential_switch` initially failed and now pass unmodified. 346 passed, coverage 98.96%, `ruff check`/`ruff format --check`/`ty check src` all clean.

## 6. Docs

- [x] 6.1 Update `README.md`'s migration log with a new **BREAKING** entry describing the new-instance-per-op + invalidation-on-reuse behavior
- [x] 6.2 Update `roadmap.md`: move this item from Next to Done with a summary, matching the existing Done-entry style

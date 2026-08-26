## 1. The ordering characteristic on the Op protocol

- [x] 1.1 Add an `Ordering` enum (`PRESERVE` / `CLEAR` / `SET`) to `sink.py`
  beside `Op`, with a docstring naming Java's `StreamOpFlag` SET/CLEAR/PRESERVE
  encoding as the thing being ported and stating why the bitmask is not (see
  design.md).
- [x] 1.2 Add `ordering: ClassVar[Ordering] = Ordering.PRESERVE` to `Op`,
  documenting it in the class docstring alongside `make_shared_state()` as the
  second piece of op protocol carrying a default that most ops accept.
- [x] 1.3 Set `ordering = Ordering.SET` on `_SortedOp` in `ops.py`.
- [x] 1.4 Add `_UnorderedOp(Op)` to `ops.py`: `ordering = Ordering.CLEAR`, and
  a `link()` returning `downstream` unchanged — no sink class, no wrapper. Note
  in its docstring that this mirrors Java's identity `opWrapSink`, so the op
  costs nothing per element and exists only to occupy a position.
- [x] 1.5 Confirm `RACING` is unaffected: `_UnorderedOp` returns `None` from
  the inherited `make_shared_state()`, so it contributes nothing to the state
  map and links identically into every branch's sink chain.

## 2. Stream reads ordering from the chain

- [x] 2.1 Rewrite `is_ordered()` in `stream.py` to fold `self._chain` left to
  right from `True`, per design.md.
- [x] 2.2 Rewrite `unordered()` as `return self._extend(_UnorderedOp())`,
  deleting the mutate-and-return-`self` docstring exception.
- [x] 2.3 Delete `self._ordered` from `Stream.__init__` and the
  `new_stream._ordered = self._ordered` line from `_derive()`. Verify no
  reader of `_ordered` remains (`grep -rn "_ordered" src/`).
- [x] 2.4 Update `_derive_executor()`'s docstring if it references the ordering
  flag as separate carried state.

## 3. Terminals

- [x] 3.1 Delete `find_first()`'s `is_ordered()` short-circuit to `find_any()`;
  it always drives `_evaluate(_FindSink(), SEQUENTIAL)`. Update the comment
  above it to explain that Java's `FindOp.mustFindFirst` is fixed at
  construction and never consults upstream `ORDERED`.
- [x] 3.2 Make `for_each_ordered()` pass `SEQUENTIAL` only when
  `self.is_ordered()`, and `None` (the stream's own executor) otherwise.
  Docstring should cite `ForEachOps.OfRef.evaluateParallel`'s
  `ForEachOrderedTask` vs. `ForEachTask` selection.

## 4. Tests

- [x] 4.1 `tests/test_unordered.py`: replace `test_unordered_returns_self_for_chaining`
  with a distinct-instance-plus-`IllegalStateException` test; keep the
  survives-mode-switch and does-not-affect-other-instances tests, which stay
  true.
- [x] 4.2 `tests/test_unordered.py`: add positionality coverage — `.unordered()`
  before vs. after an op leaves that op's behaviour unchanged, and
  `.map(f).unordered()` vs. `.unordered().map(f)` produce the same elements.
- [x] 4.3 `tests/test_unordered.py`: add `sorted()`-restores coverage —
  `.unordered().sorted(c)` is ordered, `.sorted(c).unordered()` is not.
- [x] 4.4 `tests/test_find_first.py`: retire the unordered-parallel-races test;
  replace it with one asserting the true first element is returned on an
  unordered parallel stream. Add the regression from the proposal:
  `.parallel().unordered().sorted(asc).find_first()` over an async source whose
  minimum arrives last returns that minimum, run enough times to be meaningful.
- [x] 4.5 `tests/test_for_each_ordered.py`: add an unordered-parallel test
  asserting every element is delivered exactly once, and a
  `.unordered().sorted(c).for_each_ordered()` test asserting sorted order.
- [x] 4.6 `tests/test_pipeline_immutability.py` (or wherever the enumerated
  intermediate ops are covered): add `unordered` to the derive-and-consume
  coverage.

## 5. Specs and docs

- [x] 5.1 Edit `openspec/specs/stream-ordering/spec.md`'s `## Purpose`
  directly — the delta's Purpose is ignored for an existing capability. Retire
  the "purely a declarative marker ... does not itself alter iteration order"
  claim and describe ordering as a chain-derived, positional characteristic.
- [x] 5.2 `README.md`: update the `unordered()` row (positional; `sorted()`
  restores; returns a new instance), the `find_first()` row (drop the
  races-when-unordered clause), the `for_each_ordered()` row (degrades on an
  unordered pipeline) and the `is_ordered()` row (chain-derived).
- [x] 5.3 `README.md` `## Migration`: add entries for the two breaking changes
  — `unordered()` no longer returns `self`, and `find_first()` no longer races
  on an unordered stream (use `find_any()`).
- [x] 5.4 `roadmap.md`: add the Done entry, including the measured
  before/after for `.parallel().unordered().sorted(asc).find_first()` and the
  recorded rejection of the O(1) incremental-`_ordered` alternative, so it is
  not re-proposed.

## 6. Gates

- [x] 6.1 `uv run ruff check .` and `uv run ruff format --check .` clean.
- [x] 6.2 `uv run ty check src` clean — in particular the `ClassVar[Ordering]`
  on `Op` and `_UnorderedOp.link()`'s return type.
- [x] 6.3 `uv run pytest --cov-fail-under=98` green.
- [x] 6.4 `openspec validate make-ordering-a-chain-characteristic` still valid.

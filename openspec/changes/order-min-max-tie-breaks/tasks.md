## 1. Implementation

- [x] 1.1 Flip `_min_max()`'s `observes_order` argument to `True` in
  `src/snakestream/stream.py`, and replace the comment above it — it currently
  records the superseded reasoning ("ordering delivery would buy nothing",
  "ties resolve to whichever candidate arrives first") — with the tie-identity
  reason and a pointer to `unordered()` as the lever.
- [x] 1.2 Update `is_new_extremum()`'s docstring in
  `src/snakestream/comparator.py`: its "one home for the rule both callers
  implement" claim is true again, and the rule is now first-in-encounter-order
  on an ordered pipeline rather than first-seen.
- [x] 1.3 Update the `min_by`/`max_by` exclusion comment in
  `src/snakestream/collectors.py` (around the `counting()` factory) to cite the
  `collector-min-max` requirement rather than stating the reason inline, and fix
  its stale reference to "the roadmap's item 1" — the marking question is item 4.

## 2. Tests

- [x] 2.1 `tests/test_max.py` / `tests/test_min.py`: an ordered racing pipeline
  over records whose comparator keys tie returns the earliest in encounter
  order, equal to the sequential result, and does so on every run (repeat the
  assertion enough times that arrival order would vary — a mapping operation
  with variable per-element cost is what makes the branches finish out of
  order).
- [x] 2.2 `tests/test_unordered.py`: `.parallel().unordered().max(c)` returns
  one of the tied records and engages no delivery barrier.
- [x] 2.3 `tests/test_unordered.py`: `.parallel().unordered().max(comparing(k)
  .then_comparing(t))` is determinate across runs — the documented lever works.
- [x] 2.4 `tests/test_min_by.py` / `tests/test_max_by.py`: the collector form
  and the stream form return the same record for the same ordered racing
  pipeline and comparator; and neither collector's `characteristics` contains
  `UNORDERED`.
- [x] 2.5 `tests/test_sorted.py`: stability for a sync comparator, an async
  comparator, a `comparing()` key comparator, and a `.reversed()` key comparator
  (which must keep tied elements in encounter order rather than reversing them).
- [x] 2.6 `tests/test_racing_encounter_order.py`: a racing sort and a
  `.parallel().unordered().sorted(c)` both equal the sequential result exactly,
  tied elements included — the latter also covering that an unordered sort still
  sorts the whole stream rather than per-branch subsets.
- [x] 2.7 Confirm no existing test asserted the old racing tie-break or the old
  "max()/min() pay nothing" cost claim; update any that did.

## 3. Documentation

- [x] 3.1 `README.md`: the `max()` and `min()` rows gain the tie-break rule and
  its dependence on the pipeline's ordering.
- [x] 3.2 `README.md`: the `parallel()` row currently lists `max()`/`min()` among
  the terminals that "pay nothing either way" — move them out and say they take
  the delivery barrier on an ordered pipeline.
- [x] 3.3 `README.md`: migration-log entry under the existing `0.3.5 -> next`
  block, noting the silent break, its safe direction, and `unordered()` as the
  restore.
- [x] 3.4 `roadmap.md`: close open question 3 with the decision and the reason
  it went the way the item did not predict; narrow question 4 to exclude
  `min_by`/`max_by` by citing the new requirement rather than the comment.
- [x] 3.5 `roadmap.md`: record the barrier's 50/50 cost decomposition from
  design.md, so a future pass at cheapening the ordered path starts from a
  number rather than from scratch.

## 4. Validation

- [x] 4.1 `uv run pytest` — full suite green.
- [x] 4.2 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 4.3 `uv run ty check src`
- [x] 4.4 `uv run pytest --cov-fail-under=98`
- [x] 4.5 `openspec validate order-min-max-tie-breaks --strict`

## 1. The declaration

- [x] 1.1 In `src/snakestream/collectors.py`, pass `characteristics` to
  `to_map()`'s `Collector(...)` call, computed from `merge_function is None`:
  `_ORDER_BLIND` for the no-merge form, `()` for the 3-arg form.
- [x] 1.2 Add the comment above that call recording why one factory gives two
  answers — the no-merge result is a function of the element multiset alone,
  while `merge_function` need not commute — and that the exclusion is permanent,
  not merely undeclared. Point at `_ORDER_BLIND` for the shared reasoning rather
  than restating it.
- [x] 1.3 Note in the same comment that the duplicate-key exception may name a
  different colliding key under `RACING`, and that *whether* it raises does not
  change, so the next reader meets the one behaviour change at the line that
  causes it.

## 2. Tests for the declaration

- [x] 2.1 In `tests/test_to_map.py`, assert `Characteristics.UNORDERED in
  to_map(k, v).characteristics`.
- [x] 2.2 In the same file, assert `Characteristics.UNORDERED not in to_map(k,
  v, merge).characteristics`, with the comment naming `lambda a, b: a` as why.
- [x] 2.3 Add a test that the same elements collected in two different orders
  through `to_map(k, v)` produce `dict`s that compare equal, discharging the
  "declaration SHALL be true of the behaviour" clause.

## 3. Tests for the racing path

- [x] 3.1 In `tests/test_racing_delivery_order.py`, add the observation test for
  the no-merge form: over `SOURCE` with `_slow_head`, assert the result holds
  every key/value pair and that `list(result)` differs from encounter order.
  Follow `test_grouping_by_into_an_unordered_downstream_skips_the_barrier`'s
  shape, which is the same assertion pair one container down.
- [x] 3.2 Add the mirror test for the 3-arg form: with a `merge_function`
  returning its first argument and a source whose collisions are arranged so the
  two orders disagree, assert the surviving value is the encounter-order one —
  the test that fails if someone later marks both forms.
- [x] 3.3 Add a test that a duplicate key raises `IllegalStateException` under
  `.parallel()` as well as sequentially, pinning that the mark changes which key
  is named and not whether the collection raises. Do not assert on which key.

## 4. Specs and docs

- [x] 4.1 README line 244: extend the `to_map` row to say the no-merge form
  declares `UNORDERED` and the merge form does not.
- [x] 4.2 README line 245: the `to_map(k, v, merge, map_supplier)` row currently
  calls this question "still-open" — rewrite it to state the settled answer and
  what a caller-supplied mapping type would have to say about it.
- [x] 4.3 `roadmap.md`: delete the **Open questions needing a session** section,
  now empty, and add the question's resolution to **Done** with the reasoning
  that decided it (value versus exception message; merge functions need not
  commute).
- [x] 4.4 `roadmap.md` queued gap 2 says the container-choice argument
  "Interacts with the open `to_map()` question below" — update the reference now
  that the question is closed and the section is gone.
- [x] 4.5 Migration entry **is** owed — the check reversed the task's own
  assumption. `mark-order-blind-collectors` logged an entry while calling itself
  not breaking, and this change alters two observables under `.parallel()`: the
  `dict`'s key iteration order, and which key a duplicate-key exception names.
  Entry added at the top of README's Migration list, noting also that the mark
  propagates through `grouping_by`/`mapping` when `to_map` is their downstream.

## 5. Validation

- [x] 5.1 `uv run pytest` — full suite green.
- [x] 5.2 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty
  check src`.
- [x] 5.3 `uv run pytest --cov-fail-under=98`.
- [x] 5.4 `openspec validate mark-to-map-order-blind --strict`.

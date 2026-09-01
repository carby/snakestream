## 1. The derivation

- [x] 1.1 Replace `_READ_AHEAD: int = 16` in `src/snakestream/execution.py` with `_IN_FLIGHT_PER_WORKER: int = 4` and `_in_flight(workers: int) -> int`, keeping the existing comment's measurement and rationale. Verify `_in_flight(PROCESSES) == 16`, so the effective bound at the default worker count is unchanged.
- [x] 1.2 Re-express the measurement table in the comment on the per-worker axis (`W/worker: 0.25 0.5 1 2 4 8 16 32` against the existing timings, measured at 4 workers) and state that the knee sits at 1.0 per worker — the fact the ratio is derived from. Verify the table's timings are carried over unaltered; this task re-labels an axis, it does not re-measure.
- [x] 1.3 Rewrite the "Deliberately not exported" paragraph to point at the requirement rather than argue the case in a comment: the bound is spec'd as non-public in `racing-encounter-order`, and the levers are `unordered()`/`sequential()`. Verify the comment no longer contains "Revisit on a concrete report", which the spec now settles.
- [x] 1.4 Give `_in_flight()` a docstring stating the default product (16 at 4 workers) explicitly, per design.md's first trade-off — a reader must not have to multiply to answer "how many groups can be resident?". Verify by reading it cold.

## 2. The window

- [x] 2.1 Add `size` to `_Window.__slots__` and its constructor, and change `full()` to compare against `self.size` rather than the module global. Verify no module global is read on the per-pull path (`grep -n "_IN_FLIGHT\|_in_flight" src/snakestream/execution.py` shows no hit inside `_Window`).
- [x] 2.2 Update the `_Window` class docstring: it names `_READ_AHEAD` today, and must instead say the size is fixed at construction and why — the "fixed for the duration of a run" clause in the spec is this line of code.
- [x] 2.3 Change the single construction site in `race_through()` to `_Window(_in_flight(workers))`. Verify it is still the only construction site (`grep -n "_Window(" src/snakestream/execution.py` returns one hit).
- [x] 2.4 Update `_guarded()`'s docstring where it refers to the read-ahead bound being enforced there, so it names the window's size rather than the deleted constant. Verify the paragraph still explains *why* the bound belongs at that point (last place pull order is encounter order, only place a pull happens).

## 3. Tests

- [x] 3.1 Point the four bound assertions at the derivation: `tests/test_racing_encounter_order.py:392`, `tests/test_racing_encounter_order.py:432`, `tests/test_racing_delivery_order.py:553`, `tests/test_find_first.py:236` become `<= _in_flight(PROCESSES)`. Verify all four pass unchanged in meaning — the numeric bound they assert is identical.
- [x] 3.2 Repoint `tests/test_racing_encounter_order.py:656`'s monkeypatch from `execution._READ_AHEAD = 1` to `execution._in_flight = lambda workers: 1`, and update its "given a window of one" comment to say the seam it now patches. Verify the test still reproduces last-slot contention (it should still pass, and still fail if the ordering fix in `_guarded()` is reverted).
- [x] 3.3 Add a test for the scaling scenario: drive `race_through()` directly with `workers=8` over a source whose head element is far slower than the rest, and assert the elements pulled ahead of the first release may exceed `_in_flight(PROCESSES)` — i.e. a wider race is not given the narrower window. Assert it as an invariant against `_in_flight(8)`, never a measured figure.
- [x] 3.4 Add a test for the non-public requirement: no name in `dir(snakestream)` reads or sets the bound, and `PROCESSES` is still exported. Verify it fails if `_in_flight` is re-exported from `snakestream/__init__.py`.
- [x] 3.5 Confirm nothing outside `execution.py` and these tests referenced the old constant (`grep -rn "_READ_AHEAD" .` returns only archived change documents, which are historical and must not be edited).

## 4. Documentation

- [x] 4.1 Update `CLAUDE.md`'s ordering-barrier section (the "Read-ahead is bounded by `_READ_AHEAD`" sentence) to describe the derivation and the per-worker scaling. Verify the surrounding paragraph's claim about `_guarded()` owning the bound still reads true.
- [x] 4.2 Close roadmap **Next** item 3 into **Done**, recording that its answer flipped *back*: it says "its answer flipped to 'export it'", and this change declines the export because `stream-find-first` had already spec'd the observable effect the item was opened for. Note the correction explicitly — the item asserted an obligation that was already discharged.
- [x] 4.3 Keep item 3's number free of renumbering per the section's own standing rule: archived proposals cite "**Next** item 2" and "item 3" by number, and item 3's own text says the numbering is deliberately not compacted.
- [x] 4.4 **Leave `## Next` empty**, and replace its "Refill from **Now**'s **Queued changes**" line with the rule that supersedes it: **Next** holds only work someone has committed to next, so it stays empty until an item is *chosen* from **Queued changes** rather than promoted to fill the heading. Verify the section reads as a deliberate empty state, not an oversight — a reader must not go looking for the four items that used to be there.
- [x] 4.5 Verify **no** README change and **no** migration-log entry, and say so in the commit message. The standing rule is that every break gets an entry; the absence here is the claim that there is no break, and it should be visible as a decision rather than an omission.

## 5. Gates

- [x] 5.1 `uv run pytest` passes, including the two new tests.
- [x] 5.2 `uv run ruff check .` and `uv run ruff format --check .` pass (markdown fences in the change documents included).
- [x] 5.3 `uv run ty check src` passes.
- [x] 5.4 `uv run pytest --cov-fail-under=98` passes — `_in_flight()` is a new function on a hot path and must be covered by the existing racing tests, not only the new ones.
- [x] 5.5 `openspec validate bound-in-flight-work-per-worker --strict` passes.

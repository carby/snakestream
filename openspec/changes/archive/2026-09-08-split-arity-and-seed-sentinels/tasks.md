## 1. Characterise the current behaviour before changing it

- [x] 1.1 Add failing tests for the four defects in `tests/` — `reducing(binary_operator=op)`, `reducing(identity=0, binary_operator=op)`, `reducing(0, binary_operator=op)`, `grouping_by(f, downstream=to_set())` — and verify each fails with the `TypeError` design.md's table records, so the fix is demonstrably what makes them pass
- [x] 1.2 Add a passing test for `Stream.reduce(accumulator=f)` on a non-empty and an empty stream, and verify it passes on the unmodified tree — this is the behaviour the shared sentinel is silently holding up, and it must not regress across the split

## 2. Split the sentinel

- [x] 2.1 Define `_MISSING = object()` in `stream.py` with a comment stating why it is private and not shared (design.md Decision 1), and convert `Stream.reduce()`'s three slot defaults to it; verify `uv run pytest` is still green
- [x] 2.2 Define `_MISSING = object()` in `collectors.py` with the same comment, and convert `reducing()`'s three and `grouping_by()`'s two slot defaults to it; verify `uv run pytest` is still green
- [x] 2.3 Verify no module imports `_MISSING` from another by running `uv run pytest tests/test_name_visibility.py`, and confirm `grep -rn "UNSET" src/snakestream` shows only seed-role uses remaining

## 3. Fix dispatch

- [x] 3.1 Rewrite `Stream.reduce()`'s dispatch per design.md Decision 2 — shift on the trailing slot, then the single `if identity is _MISSING: identity = UNSET` normalizer — and verify 1.2's tests plus the existing `reduce` suite pass
- [x] 3.2 Rewrite `reducing()`'s dispatch the same way, shifting by two positions or one according to whether `mapper` was supplied, then normalizing `mapper` to `None` and `identity` to `UNSET`; verify 1.1's three `reducing` tests now pass
- [x] 3.3 Rewrite `grouping_by()`'s dispatch, and set `supplied_factory` **after** the shift so it means "`map_factory` survived as supplied" (design.md Decision 2); verify 1.1's `grouping_by` test passes and that `grouping_by(f, to_set())` still derives `UNORDERED` from its downstream
- [x] 3.4 Add positional-vs-keyword equivalence tests for every documented overload of all three functions, including `reducing(10, binary_operator=op)`'s mixed spelling, per the scenarios in the three delta specs; verify all pass

## 4. Reject unsatisfiable argument sets

- [x] 4.1 Raise `StreamBuildException` from `Stream.reduce()` for a combiner without an identity and for no accumulator at all (design.md Decision 4); verify the two scenarios in the `reduce-without-identity` delta
- [x] 4.2 Raise `StreamBuildException` from `reducing()` for a mapper without an identity and for no arguments; verify the two scenarios in the `collector-reducing` delta
- [x] 4.3 Raise `StreamBuildException` from `grouping_by()` for `map_factory` without `downstream`, naming the unsatisfied three-argument form rather than reporting a downstream type error; verify the scenario in the `collector-grouping-by` delta
- [x] 4.4 Confirm `ReduceSink.merge_from()`'s two `pragma: no cover - unreachable` branches are still unreachable now that 4.1 rejects the call that would have reached them, and verify `uv run pytest --cov-fail-under=98` passes

## 5. Correct the prose the split invalidates

- [x] 5.1 Rewrite `sink.py:22-25`'s comment per design.md Decision 5 — `collectors.py` not `collector.py`, "neither is downstream of the other" not "neither may import the other", and the seed role alone — and verify no other comment in `sink.py` still describes the arity role
- [x] 5.2 Update `ReduceSink`'s and `reducing()`'s docstrings where they describe `UNSET` as doing arity duty, keeping the two dispatchers' "keep these in step by hand" instruction intact
- [x] 5.3 Add the Migration entry to `README.md` per design.md's Migration Plan, and verify the README's parity tables need no change (no public name is added, removed or renamed)

## 6. Close the roadmap item

- [x] 6.1 Move `roadmap/items/unset-dual-role.md`'s prose to the top of `roadmap/decisions.md` as a new entry recording what shipped — including that the positional paths cost nothing, that the keyword form was the real crossing point, and Decision 1's duplication rationale — then delete the item file
- [x] 6.2 Edit `roadmap/items/sink-sentinel-placement.md` in place: its "And half of it may vanish" conditional has resolved, so restate as fact that `_MISSING` needed no home and the item now places one trio; do **not** close it or change its bucket
- [x] 6.3 Run `python tools/roadmap_index.py`, then verify `uv run pytest tests/test_roadmap.py` passes and `uv run ruff format --check .` is clean (a Python-tagged code fence holding aligned trailing comments fails the gate — use an untagged fence)

## 7. Full verification

- [x] 7.1 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run ty check src`, and verify all are clean
- [x] 7.2 Run `uv run --python 3.14t pytest` and verify the free-threaded leg is green, matching what CI runs
- [x] 7.3 Run `openspec validate split-arity-and-seed-sentinels --strict` and verify every delta scenario has a corresponding passing test

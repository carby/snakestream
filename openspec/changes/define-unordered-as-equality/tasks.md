## 1. The definition

- [ ] 1.1 Extend the `Characteristics` docstring in `src/snakestream/collector.py`: `UNORDERED` promises `==`-equality of the collected result and makes no promise about that result's iteration order. Use Java's "does not commit to preserving the encounter order of input elements" as the parity phrasing, and say why the stricter reading is not the rule — it would disqualify `to_set()`.
- [ ] 1.2 Confirm no other prose in `src/` states or implies the stricter reading: `grep -rn "insertion order\|retains no record" src/`.

## 2. Repair the `to_set()` premise

- [ ] 2.1 Replace the comment at `src/snakestream/collectors.py:52` — "a set retains no record of insertion order" — with the equality justification: two sets holding the same members compare equal irrespective of how either was built.
- [ ] 2.2 Split the hedge at `src/snakestream/collectors.py:67`. Java's javadoc documents characteristics for exactly three factories (`toSet()`, `groupingByConcurrent()`, `toConcurrentMap()`) and is silent for the rest; `CH_ID`/`CH_NOID` are private fields in `Collectors.java`, not contract. The sentence currently reads as though the two are one claim.
- [ ] 2.3 Update the comment's forward reference: roadmap question 4's derivation half is settled by this change, and only the marking half (`counting()`, `summing_int/long()`, `summarizing_int/long()`) remains open there.

## 3. Derive on `grouping_by()` and `partitioning_by()`

- [ ] 3.1 Pass `characteristics=downstream.characteristics` in `grouping_by()`, matching `mapping()` (`collectors.py:534`) and `collecting_and_then()` (`collectors.py:574`) verbatim.
- [ ] 3.2 Replace `grouping_by()`'s comment at `collectors.py:459` with the derivation's actual reason: `dict.__eq__` is key-order-insensitive and compares values pairwise, and the classifier is a function of the element, so the result is equal under reordering exactly when the downstream's is.
- [ ] 3.3 Pass `characteristics=downstream.characteristics` in `partitioning_by()`.
- [ ] 3.4 Replace `partitioning_by()`'s "same reasoning as `grouping_by()` above" with its own: both partitions are seeded in the supplier, so the result is always the same two keys in the same order for any input, and the downstream is the only order-sensitive part.

## 4. Tests

- [ ] 4.1 Invert `tests/test_grouping_by.py:78` — rename to reflect that `grouping_by(len, to_set())` now reports `UNORDERED`, and add the ordered-downstream, default-downstream and nested cases from `collector-grouping-by`.
- [ ] 4.2 Invert `tests/test_partitioning_by.py:68` the same way, and cover the two-key-order scenario including the empty stream.
- [ ] 4.3 Add the behavioural scenarios: same elements in two orders collect equal via `grouping_by(f, to_set())`, and an ordered racing pipeline collecting `grouping_by(f, to_set())` / `partitioning_by(p, to_set())` engages no reorder barrier. Follow the barrier-observation pattern already used in `tests/test_racing_delivery_order.py`.
- [ ] 4.4 Add the `collector-protocol` scenario that equality — not iteration order — is the test a declarer must meet.
- [ ] 4.5 Do **not** add a test for the non-promise itself (design.md — Decisions).

## 5. Documentation

- [ ] 5.1 Add a README migration-log entry: on an ordered racing pipeline, `grouping_by`/`partitioning_by` with an order-blind downstream no longer deliver in encounter order; the collected value is unchanged under `==`, the returned mapping's key iteration order is no longer deterministic, and `.sequential()` or an order-observing downstream restores it.
- [ ] 5.2 Check whether README's collector table states characteristics anywhere; update if so.

## 6. Validation

- [ ] 6.1 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- [ ] 6.2 `uv run pytest --cov-fail-under=98`.
- [ ] 6.3 `openspec validate "define-unordered-as-equality" --strict`.

## 7. Roadmap

- [ ] 7.1 Update roadmap question 4: its derivation half is resolved here; record that the remaining half is the marking decision for `counting()` / `summing_int/long()` / `summarizing_int/long()`, and that the float family plus `to_map(..., merge)` are permanently unmarkable (this change's non-goals).

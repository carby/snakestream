## 1. State the guard rule the marked collectors will rely on

- [x] 1.1 Confirm the guard already holds before building on it: remove the
      `UNORDERED` declaration from `to_set()`, check that
      `test_to_set_takes_the_order_blind_path` fails on its declaration
      assertion, and restore it. This is the `collector-to-set` scenario
      "Dropping the declaration is caught", verified by hand rather than by a
      test that mutates shipped code.
- [x] 1.2 In `tests/test_racing_delivery_order.py`, add a comment above
      `test_to_set_takes_the_order_blind_path` naming the two
      recording-downstream tests as the other half of its guard, and saying why
      the correctness assertion beside it cannot be the part that does the work.

## 2. Mark the exactly order-invariant collectors

- [x] 2.1 Declare `UNORDERED` on `counting()` in `collectors.py`, replacing the
      deferral comment with the reasoning the spec now carries: order-invariant
      in fact, Java silent, this library's `UNORDERED` governs a delivery
      barrier rather than a combine strategy.
- [x] 2.2 Declare `UNORDERED` on `summing_int()` / `summing_long()`, noting that
      the shared body means the declaration must not leak to `summing_double()`.
- [x] 2.3 Declare `UNORDERED` on `summarizing_int()` / `summarizing_long()`, and
      not on `summarizing_double()` — check how `_summarizing()` shares its body
      across the three, so the mark is applied per-factory rather than in the
      shared helper.

## 3. Write down the permanent exclusions

- [x] 3.1 Add the comment on `summing_double()` / `averaging_*` recording that
      float addition is not associative, so these are order-sensitive in fact
      and closed to a later marking pass — not merely undeclared.
- [x] 3.2 Same for `summarizing_double()`, with the reason specific to it: one
      order-sensitive field makes the whole `NamedTuple` compare unequal.

## 4. Test the declarations and the behaviour behind them

- [x] 4.1 Assert the presence of `UNORDERED` on `counting()`, `summing_int()`,
      `summing_long()`, `summarizing_int()`, `summarizing_long()`, in the test
      file for each collector alongside its existing tests.
- [x] 4.2 Assert its absence on `summing_double()`, `averaging_int/long/double()`
      and `summarizing_double()`.
- [x] 4.3 Assert the behaviour the declarations claim: the same elements in two
      different orders collect equal under each marked factory, and for
      `summarizing_int()` assert equality across all five fields including
      `average`.
- [x] 4.4 In `tests/test_racing_delivery_order.py`, add the marked collectors to
      the ordered-racing coverage — result correct, equal to the sequential
      result — using the existing `_slow_head` source.
- [x] 4.5 Assert that `summing_double()` under an ordered racing pipeline equals
      the sequential result exactly, which is the barrier doing its job.

## 5. Correct the measurement claims

- [x] 5.1 Re-run the four benchmark shapes on the final code and record the
      figures: cheap chain, uniform IO, periodic straggler, random tail.
- [x] 5.2 Correct `race_through()`'s docstring — replace "nothing at all on
      IO-bound work" with the uniform-versus-tail distinction, keeping the
      uniform figure and adding a tail figure, and say plainly that the original
      benchmark could not have detected the difference.

## 6. Validate and land

- [x] 6.1 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run ty check src`, and `uv run pytest --cov-fail-under=98`.
- [x] 6.2 Check README's collector tables for anything that states or implies
      these collectors' characteristics, and update if so.
- [x] 6.3 Move roadmap question 4 to **Done**, recording that the fourth pass
      brought the benchmark its own rule demanded and the answer was yes, with
      the tail-latency figure as the reason it flipped. Note in item 5 that
      question 4 is closed, so its enumeration no longer has to carry it.

## 1. Type alias

- [x] 1.1 Add `NumberMapper = Callable[[T], int | float | Awaitable[int | float]]` to `type.py`.

## 2. Implementation

- [x] 2.1 Add `counting()` to `collector.py`, returning an `async def` collector that returns the `int` count of pulled elements.
- [x] 2.2 Add `summing_int(mapper: NumberMapper)` and `summing_long(mapper: NumberMapper)` to `collector.py`, each returning a collector that maps every element via `_maybe_await` and accumulates the `int` sum.
- [x] 2.3 Add `summing_double(mapper: NumberMapper)` to `collector.py`, identical to 2.2 but coercing each mapped value to `float` before accumulating.
- [x] 2.4 Add `averaging_int(mapper: NumberMapper)`, `averaging_long(mapper: NumberMapper)`, `averaging_double(mapper: NumberMapper)` to `collector.py`, each returning a collector computing the `float` mean of mapped values (`0.0` for an empty stream).
- [x] 2.5 Add a short module-level comment above the `summing_*`/`averaging_*` group noting that the near-identical bodies are intentional (mirroring distinct Java `Collectors` method names), not copy-paste.

## 3. Tests

- [x] 3.1 Add `tests/test_counting.py`: non-empty and empty stream.
- [x] 3.2 Add `tests/test_summing.py`: `summing_int`/`summing_long`/`summing_double` each with a sync mapper, an async mapper, and an empty stream; assert `summing_double`'s result is a `float`.
- [x] 3.3 Add `tests/test_averaging.py`: `averaging_int`/`averaging_long`/`averaging_double` each with a sync mapper, an async mapper, and an empty stream (asserting `0.0`).
- [x] 3.4 Run `uv run pytest` to confirm no regressions and coverage stays at/above the gate.

## 4. Docs

- [x] 4.1 Add seven rows to README's `Collectors` table (`counting`, `summing_int`, `summing_long`, `summing_double`, `averaging_int`, `averaging_long`, `averaging_double`), following the existing table format.
- [x] 4.2 Move roadmap.md **Now** item #1 to **Done**, following the existing Done-entry format (what/why/tests/link to this change).

## 5. Validation

- [x] 5.1 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 5.2 `uv run ty check src`

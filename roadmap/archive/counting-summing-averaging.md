+++
id = "counting-summing-averaging"
title = "Added `counting()`, `summing_*()` and `averaging_*()`"
filed = 2026-08-17
closed = 2026-08-17
outcome = "shipped"
+++

Added `counting()`, `summing_int`/`summing_long`/`summing_double`, and
`averaging_int`/`averaging_long`/`averaging_double` (`collector.py`) —
numeric reducing collectors, `collector.py`'s equivalent of the matching
`Collectors` statics, following the same factory-returns-closure shape
`joining()` established. `counting()` returns the `int` element count;
`summing_int`/`summing_long`/`summing_double` map each element then sum
the results (`int` for the first two, `float` for the last);
`averaging_int`/`averaging_long`/`averaging_double` map each element and
return the arithmetic mean as a `float` (`0.0` for an empty stream).
Java's `Collectors` distinguishes `summingInt`/`summingLong`/
`summingDouble` and the `averaging*` trio by primitive type — a
distinction Python's numeric tower doesn't have — so each pair/trio is
implemented identically apart from `summing_double`'s explicit `float()`
coercion; kept as separate, Java-parity-named functions rather than
collapsing to `summing(mapper)`/`averaging(mapper)`, since these are
distinct Java method names (not one overloaded method, unlike `joining()`'s
three arg-count variants). Added a new `NumberMapper` type alias to
`type.py`. Mapper dispatch reuses the existing `_maybe_await` helper, so
sync and async mappers both work. Added `tests/test_counting.py`,
`tests/test_summing.py`, `tests/test_averaging.py`: non-empty/empty
streams and sync/async mappers for each function, plus a `float`-type
assertion for `summing_double`. Updated README's `Collectors` table with
seven new rows. No breaking changes. See
`openspec/changes/add-collectors-counting-summing-averaging`.

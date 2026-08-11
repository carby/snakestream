## Context

`_min_max()` and `sorted()` (`stream.py`) both already compute a `sign`/comparison result from the user-supplied `Comparator` and branch on it — `_min_max` does `if (sign > 0) == keep_positive and sign != 0`, `sorted()`'s sync branch feeds the comparator to `cmp_to_key`, and its async branch (`sort.py`) does `await comparator(left[i], right[j]) <= 0`. None of these currently distinguish an `int` result from a `bool` result, because `bool` is a subclass of `int` in Python and both `>`/`<=` comparisons against `0` work the same either way — a bool comparator just happens to never produce a negative value, so `min()`/`sorted()` degrade silently instead of erroring. This gap survives even after the `comparator-contract` fix (commit `4f526bb`) because that fix corrected the *interpretation* of the sign, not whether a bool sneaking in gets caught.

## Goals / Non-Goals

**Goals:**
- Fail fast and loudly (`TypeError`) the first time a comparator returns a literal `bool`, in all three comparator-consuming operations (`sorted()`, `min()`, `max()`), sync and async comparators alike.
- Keep the check cheap — one `isinstance` per comparator invocation, no behavior change for correctly-typed `int` comparators.
- Fix the two existing tests that were silently relying on this class of bug.

**Non-Goals:**
- Not attempting a static-typing fix (a `Protocol` or stricter alias) — established in conversation that Python's `bool <: int` subtyping makes this structurally impossible to catch statically.
- Not validating the *magnitude* or transitivity of the comparator's results (e.g. detecting a non-total-order comparator) — only the bool-vs-int class of mistake, which is the one that silently degrades today.
- Not changing `_min_max`'s or `sorted()`'s existing sign-interpretation logic, only adding a guard in front of it.

## Decisions

- **Where to check**: at the single point each function already extracts the comparator's return value (`_min_max`'s `sign = ...`/`await ...`, and `sorted()`'s sync `cmp_to_key(comparator)` path and the async `merge_sort`/`_merge` comparator call in `sort.py`). Centralizing isn't possible without a shared helper since sync/async and the three call sites differ; instead add a tiny local guard `_reject_bool(sign)` (or inline `isinstance` check) reused at each of the ~3-4 call sites.
  - Alternative considered: wrap the user's comparator once at entry (`min()`/`max()`/`sorted()`) in a checking adapter that both awaits-if-needed and validates. Rejected for now as a larger refactor than this fix needs; noted as a possible follow-up if the duplication across call sites becomes annoying.
- **Check uses `isinstance(sign, bool)`, not `type(sign) is bool`**: `isinstance` correctly catches `True`/`False` (including any bool-returning expression) while never misfiring on plain `int` results, since no other builtin subclasses `bool`.
- **Error type**: `TypeError`, matching Python convention for "wrong type passed by caller" and consistent with how `ty`/mypy would have flagged this if the language allowed it.
- **Message content**: name the offending function (`min`/`max`/`sorted`) and state the expected contract ("comparator must return a 3-way int: negative, zero, or positive — not bool") so the error is actionable without needing to read `comparator-contract`'s spec.
- **Sync/async parity**: the guard runs identically after `await`-ing an async comparator or calling a sync one — same check, same message, since `sign`'s value is what's being validated, not how it was obtained.

## Risks / Trade-offs

- [Any caller currently passing a bool comparator to `min()`/`max()`/`sorted()` — even one that "happened to work" like the two existing tests — now gets a hard failure instead of a silent (possibly correct-by-luck) result] → This is the intended outcome; documented as **BREAKING** in README's migration log per `CLAUDE.md`.
- [Slight per-call overhead from the `isinstance` check on every comparator invocation, including inside `sorted()`'s O(n log n) comparisons] → Negligible (`isinstance` against a single builtin type is a cheap C-level check); no measurable impact expected at the scales this library targets.
- [Duplication of the same guard across `_min_max` and both branches of `sorted()`'s comparator use] → Accepted per the "Decisions" alternative above; revisit as a shared helper only if a fourth call site appears.

## Migration Plan

1. Add the bool-rejection guard to `Stream._min_max()` (`stream.py`).
2. Add the same guard to `Stream.sorted()`'s comparator path (`stream.py`) and, if the async merge-sort path in `sort.py` also directly consumes the comparator's raw result, add it there too.
3. Fix `test_find_min_value_object_comparator` (`tests/test_min.py:91`) and `test_find_max_value_object_comparator` (`tests/test_max.py:91`) to use 3-way comparators.
4. Add regression tests asserting `TypeError` for bool comparators across `min()`, `max()`, `sorted()`, sync and async.
5. Update README's migration log and parity notes; move the roadmap item from **Now** to **Done**.

No runtime/deployment migration needed — library-only change.

## Open Questions

None.

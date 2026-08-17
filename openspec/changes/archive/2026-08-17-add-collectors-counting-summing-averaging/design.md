## Context

`collector.py` holds plain `async def` functions matching the
`Callable[[AsyncGenerator[T, None]], R]` shape `collect()` expects
(`CLAUDE.md`: "Collectors are just async generator consumers"). `joining()`
established the pattern for a *configurable* collector: a factory function
that captures its arguments in a closure and returns the actual collector.
This change adds seven more factories following that same pattern, but
raises a naming question Java doesn't have to answer: Java's `Collectors`
distinguishes `summingInt`/`summingLong`/`summingDouble` (and the
`averaging*` trio) because `int`/`long`/`double` are genuinely different
primitive types with different overflow/precision behavior and different
`ToIntFunction`/`ToLongFunction`/`ToDoubleFunction` mapper shapes. Python has
no such distinction — `int` is arbitrary-precision (covers both `int` and
`long`) and `float` is the only other numeric primitive in play.

## Goals / Non-Goals

**Goals:**
- Add `counting()` and the six `summing*`/`averaging*` factories, matching
  Java's `Collectors` names exactly (snake_case-adapted), per this project's
  established preference for staying close to Java's naming over inventing
  new terms.
- Keep each factory's return type predictable and Java-consistent:
  `counting()` → `int`; `summing_int`/`summing_long` → `int`;
  `summing_double` → `float`; all three `averaging_*` → `float`.
- Reuse the `joining()`-established factory-returns-closure shape; no new
  collector abstraction.

**Non-Goals:**
- No collapsing of `summing_int`/`summing_long`/`summing_double` into a
  single `summing(mapper)`, or the `averaging_*` trio into one
  `averaging(mapper)`. Unlike `joining()`'s three overloads (one function,
  same behavior, differing only in how many optional args are supplied),
  Java's `summingInt`/`summingLong`/`summingDouble` are three distinct method
  names in the API being mirrored — collapsing them would be inventing a
  narrower surface than Java's, which the project's Java-parity naming
  preference argues against, not for.
- No overflow/precision emulation of Java's fixed-width `int`/`long` (e.g.
  wrapping at 2^31 or 2^63). Python's arbitrary-precision `int` is a strict
  superset of what either Java type can represent; emulating overflow would
  be adding failure modes Python doesn't have, not matching a real Java
  guarantee worth porting.
- No `Collector`-class hierarchy; each factory returns a plain `async def`
  closure, matching every other entry in `collector.py`.

## Decisions

- **Seven separate functions, not two.** `counting()`, `summing_int(mapper)`,
  `summing_long(mapper)`, `summing_double(mapper)`, `averaging_int(mapper)`,
  `averaging_long(mapper)`, `averaging_double(mapper)`. `summing_int` and
  `summing_long` are implemented identically (accumulate via `+=` over the
  mapped values, returning whatever numeric type the mapper produces — `int`
  in the idiomatic case); `summing_double` differs only by wrapping each
  mapped value in `float(...)` before accumulating, guaranteeing a `float`
  result even if the mapper returns an `int`. Similarly, all three
  `averaging_*` functions share one running-mean implementation (sum /
  count, `float` division, `0.0` for an empty stream) — `averaging_int` and
  `averaging_long` are identical to each other, `averaging_double` only
  differs in that its type hint documents a `float`-returning mapper. The
  duplication is intentional documentation of the Java surface being
  mirrored, not accidental — a future reviewer skimming names against
  `Collectors` javadocs should find a 1:1 match.
  - Alternative considered: `summing(mapper)` / `averaging(mapper)`, two
    functions instead of six, since Python's numeric tower makes the
    int/long/double split meaningless at runtime. Rejected: the project has
    collapsed Java overloads before (`joining()`'s three arg-count variants
    into one function), but only when they were genuinely one Java method
    with optional args. Here they're six distinct Java method names: a
    caller reading Java `Collectors` docs and porting code expects
    `summingInt`/`summingDouble` to exist under their own names, the same
    reasoning already applied when `toArray()` kept only the part of Java's
    surface with a real Python motivation and explicitly documented the
    other overload as intentionally skipped (not silently merged).
- **`counting()` returns `int`, matching Java's `Long`** (Python has no
  `int`/`long` split; `int` is the correct unqualified numeric type).
- **Empty-stream behavior:** `counting()` on an empty stream returns `0`;
  every `summing_*` on an empty stream returns `0` (`int`) or `0.0`
  (`summing_double`); every `averaging_*` on an empty stream returns `0.0`
  — all matching Java's `Collectors` javadocs exactly.
- **Mapper dispatch reuses `_maybe_await`** (`callable_dispatch.py`), the
  same helper already used by `map()`/`filter()`/`reduce()`/etc., so sync and
  async mappers both work with no duplicated dispatch logic.
- **New `ToIntFunction`-equivalent type alias.** Rather than one alias, reuse
  the existing `Mapper[T, R]` shape from `type.py` (`Callable[[T], R |
  None]`) is a poor fit since summing/averaging mappers must return a
  number, not `R | None`. Add a `NumberMapper = Callable[[T], int | float |
  Awaitable[int | float]]` alias to `type.py` for these six factories'
  mapper argument, following the project's convention that composite
  callable-type shapes used in public signatures live in `type.py`, not
  inline.

## Risks / Trade-offs

- [Risk] Six near-duplicate function bodies (`summing_int`/`summing_long`
  identical, `averaging_int`/`averaging_long` identical) look like dead
  copy-paste to a reviewer unfamiliar with the Java-parity rationale →
  Mitigation: a short module-level comment near the group explaining why the
  duplication is intentional (mirrors distinct Java method names), plus this
  design doc, so the decision isn't re-litigated per function.
- [Risk] `summing_int`/`summing_long` on a mapper that returns `float` would
  silently return a `float` despite the "int" name, since nothing coerces
  the mapper's output → Mitigation: accepted, matches the project's existing
  posture of runtime-only contracts on collector element shape (e.g.
  `joining()`'s `TypeError` guard is the exception, not the rule — most
  collectors trust the caller's mapper to match the documented contract);
  `ty` already flags a mismatched mapper if the caller's `Stream[T]` is
  properly typed and the mapper's return type disagrees with `NumberMapper`.

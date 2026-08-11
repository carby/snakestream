## Context

`Stream.of()` currently is:

```python
@staticmethod
def of(*args, **kwargs) -> Stream:
    source = []

    if args and len(args) == 1:
        if isinstance(args[0], dict):
            source.append(args[0])
        elif isinstance(args[0], list):
            source = args[0]
        else:
            source.append(args[0])
    else:
        source += list(args)

    if kwargs and len(kwargs.items()):
        if len(source):
            source += list(kwargs.items())
        else:
            return Stream(list(kwargs.items()))

    if len(source) == 1:
        return Stream(source[0])
    return Stream(source)
```

`Stream(source)` always routes through `base_stream._normalize(source)`, which already:
- yields `dict` sources as a single element,
- spreads anything else with `__iter__`/`__next__`,
- yields anything else as a single scalar element.

Because of that, the `dict`/`list` `isinstance` branches in `of()` are redundant: `Stream(source[0])` for a one-element `source` list produces an identical call to `Stream(args[0])` directly, in every case (dict, list, generator, scalar, `None`). This was confirmed by manually tracing all 15 existing cases in `tests/test_of.py`.

## Goals / Non-Goals

**Goals:**
- Collapse `of()`'s branching to the two cases that actually differ: one positional arg (pass through to `Stream()` unchanged) vs. multiple (wrap in a list, one element per arg).
- Make `str`/`bytes` behave as atomic values everywhere a source is normalized, not just when passed to `of()` — so the fix belongs in `_normalize()`, not `of()`.
- Preserve every existing non-kwargs `test_of.py` behavior unchanged.

**Non-Goals:**
- Not touching `_accept()`'s async-generator/async-iterable detection.
- Not changing `Stream.builder()`, `Stream.concat()`, or `Stream.iterate()`.
- Not adding a replacement API for kwargs-based construction (e.g. `Stream.of_dict()`) — no known caller need; `Stream.of(*d.items())` already covers it.

## Decisions

1. **Drop `**kwargs` entirely** rather than keep it or move it to a separate constructor. Rationale: it has no Java equivalent, is undiscoverable (nothing in the type signature suggests `Stream.of(a=1)` produces `[("a", 1)]`), and the roadmap review flagged it as one of the two sources of "unclear without tracing the logic." Alternative considered: keep kwargs but document it — rejected because the shape (tuple-pairs mixed into the same stream as positional elements) is inherently confusing regardless of documentation.

2. **Single positional arg passes straight to `Stream()`** instead of being pre-branched by type. Rationale: `_normalize()` already owns "what does this source mean" — duplicating that logic in `of()` is exactly the dead-branch problem being fixed. Alternative considered: keep explicit `isinstance` checks in `of()` for readability — rejected since they're proven redundant, and a comment can't substitute for removing genuinely dead code.

3. **str/bytes scalar fix lives in `_normalize()`** (`base_stream.py`), not in `of()`, since `_normalize()` is also reachable directly via `Stream(some_string)` (bypassing `of()` entirely) and both paths should agree. Alternative considered: special-case only inside `of()` — rejected, would leave `Stream("abc")` (no `.of()`) inconsistent with `Stream.of("abc")`.

4. **Multiple positional args still wrap into a list** (`Stream(list(args))`), unchanged from today's `else` branch — this is the one case where `of()`'s own branching is load-bearing (Java's `Stream.of(T... values)` semantics: N args → N elements), so it's kept as-is rather than folded away.

## Risks / Trade-offs

- [Removing kwargs breaks any external caller using `Stream.of(key=value, ...)`] → Mitigation: pre-1.0 library (per `CLAUDE.md`/README), tracked in the migration log; `TypeError` on the call site makes the break immediately visible rather than silent.
- [str/bytes scalar change breaks any caller relying on `Stream.of("abc")` yielding chars] → Mitigation: same migration-log tracking; arguably fixes a latent footgun rather than removing an intentional feature — no existing test asserted the char-spreading behavior as desired.

## Migration Plan

Single-commit change, no phased rollout needed (library code, no running service). Update `README.md`'s migration log with both **BREAKING** entries per `CLAUDE.md`. Move the roadmap item from **Now** to **Done** in the same change.

## Open Questions

None — both breaking decisions were confirmed with the user before writing this design.

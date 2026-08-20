## 1. Implementation

- [x] 1.1 In `src/snakestream/base_stream.py`, split `_normalize()`'s iterable arm: keep `for i in source: yield i` when `hasattr(source, "__iter__")`, and add an `elif hasattr(source, "__next__")` arm that drives the source with `next()`.
- [x] 1.2 Write the `__next__` arm as `while True:` with `next(source)` inside a `try`, `except StopIteration: return`, and the `yield` outside the `try` — per design.md Decision 3, so PEP 479 does not turn exhaustion into `RuntimeError: async generator raised StopIteration`, and a downstream `athrow(StopIteration)` is not swallowed.
- [x] 1.3 Confirm the `dict`/`str`/`bytes` scalar branch and the final `else` scalar branch are unchanged, and that no other call site in `src/` branches on source shape.

## 2. Tests

- [x] 2.1 Add a test module (or extend an existing construction test module) with a `__next__`-only helper class — implements `__next__`, deliberately does *not* implement `__iter__` — asserting `assert not hasattr(obj, "__iter__")` so the test cannot silently drift onto the `__iter__` path.
- [x] 2.2 Test that a `__next__`-only source producing `1, 2, 3` collects to `[1, 2, 3]` in order, with no `TypeError`.
- [x] 2.3 Test that a `__next__`-only source that raises `StopIteration` on its first advance collects to `[]` and raises nothing — this is the case that covers the `except StopIteration` arm.
- [x] 2.4 Test that a `__next__`-only source composes through intermediate operations (e.g. `.map()` then `.filter()`) and yields the same result as the equivalent list source.
- [x] 2.5 Test that laziness is preserved: build a `__next__`-only source that records each advance, apply `.limit(2)`, and assert the source was advanced only as far as the pipeline needed — it is not drained up front.
- [x] 2.6 Add a regression guard that a plain non-iterator iterable (e.g. a `list`) still takes the `__iter__` path and spreads, and that a scalar with neither dunder is still a one-element stream.

## 3. Spec sync

- [x] 3.1 Verify the delta in `openspec/changes/fix-next-only-source-normalization/specs/stream-construction/spec.md` matches the implemented behaviour, and that its `### Requirement: Iterable source spreading` header text matches the existing requirement in `openspec/specs/stream-construction/spec.md` exactly.
- [x] 3.2 Run `openspec validate fix-next-only-source-normalization --strict` and fix any reported issues.

## 4. Verification

- [x] 4.1 `uv run pytest` — full suite green, no regressions in the existing construction/`Stream.of()` tests.
- [x] 4.2 `uv run pytest --cov-fail-under=98` — the new branch and its `except StopIteration` arm are covered, so the branch-coverage gate still passes.
- [x] 4.3 `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 4.4 `uv run ty check src`.
- [x] 4.5 Re-run the original repro (a `__next__`-only class through `Stream.of(...).collect(to_list)`) and confirm it now streams instead of raising `TypeError`.

## 5. Roadmap upkeep

- [x] 5.1 Move roadmap **Now** item 1 (the `__next__` branch — renumbered from 2 when the stale collectors item was retired) out of **Now** into **Done**, with a short entry describing the fix and the decision taken (support rather than narrow the guard).
- [x] 5.2 Renumber the remaining **Now** items and update the dependency-order preamble and any cross-references to item numbers, including the **Later** section's back-reference to the **Now** range.

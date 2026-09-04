## Why

Third of four sequenced floor raises heading to 3.14-only; see the two archived
predecessors (`2026-09-04-raise-python-floor-to-311`, `…-to-312`) for the
sequence and its destination, free-threading (PEP 779) as the substrate for a
contiguous-splitting `spliterator()`.

This step drops 3.12. It is the **smallest and most mechanical** of the four,
and unlike the previous two it carries no silent break: `requires-python` is
the only thing a caller can observe changing. The 3.13 feature it takes is
**PEP 696 (type parameter defaults)**, and it takes it only as a *consumer* —
`collections.abc.AsyncGenerator`'s send type now defaults, so
`AsyncGenerator[T, None]` collapses to `AsyncGenerator[T]` at 14 sites.

Two 3.13 typing features were checked against the code and declined. Both
declines are architectural rather than incidental, and both are recorded in
`design.md` so the questions are not re-opened: PEP 696 defaults on the
package's *own* generics (decision 2) and PEP 742 `TypeIs` on the dispatch
predicates (decision 3).

## What Changes

- **BREAKING**: `requires-python` moves from `>=3.12` to `>=3.13`. Installing
  on 3.12 now fails at resolution. This is the change's **only** observable
  break.
- 14 `UP043` findings are fixed — `AsyncGenerator[T, None]` → `AsyncGenerator[T]`
  across `stream.py` (5), `collector.py` (5), `execution.py` (2) and
  `tests/test_find_first.py` (2). All are ruff-autofixable, and each denotes the
  identical type before and after, so nothing about behaviour or static checking
  moves.
- The 3.12 leg is removed from both CI matrices; `ruff`'s `target-version`
  moves to `py313`.
- The `stream-iterator` spec's one written `AsyncGenerator[T, None]` is
  respelled to match the code. Same type, no requirement changed.
- Docs stating the matrix are corrected; a README Migration entry records the
  dropped interpreter.

**Explicitly not taken, with reasons in `design.md`:**

- **PEP 696 defaults on `Collector[T, A, R]`.** The accumulator parameter `A` is
  written `Any` at 28 of its 45 annotation sites and is the obvious candidate to
  default — but PEP 696 defaults must be *trailing*, so only `R` can take one,
  and `R` is the parameter that always carries meaning. Reaching `A` would mean
  reordering a public generic, which breaks every existing three-argument
  annotation silently and at type level. Declined on that, not on taste.
- **PEP 742 `TypeIs` on `is_async_callable()`.** Verified not applicable: the
  ~30 `cast("Awaitable[…]", …)` calls sit where classification was *hoisted*
  away from the use site, and `TypeIs` narrows only at the call.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install-smoke-test`: the stated matrix moves from 3.12–3.14 to 3.13–3.14.
- `stream-iterator`: the return type is written `AsyncGenerator[T]` rather than
  `AsyncGenerator[T, None]`. **A spelling change only** — PEP 696 gives the send
  parameter a default of `None`, so the two denote the same type and every
  scenario is carried over untouched. The delta exists so the spec and the code
  read the same, not because a requirement moved.

## Impact

- `pyproject.toml` — `requires-python`, `[tool.ruff] target-version`
- `.github/workflows/check.yml` — both matrices
- `src/snakestream/stream.py`, `collector.py`, `execution.py` — 12 annotations
- `tests/test_find_first.py` — 2 annotations
- `CLAUDE.md`, `README.md`, `openspec/specs/install-smoke-test/spec.md`,
  `openspec/specs/stream-iterator/spec.md`
- No public API surface added or removed; no runtime behaviour change; no
  static-typing change.

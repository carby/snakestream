## Context

`src/snakestream` is fully type-hinted (`type.py` defines `Predicate`, `Mapper`, `FlatMapper`, `Comparator`, `Consumer`, `Accumulator`, `CloseHandler` as `Union[sync, Awaitable[...]]`-style aliases used throughout `stream.py`, `base_stream.py`, `parallel_stream.py`), but no CI step currently verifies the hints are correct — only `ruff` (lint/format) and `pytest` run today. CI (`.github/workflows/check.yml`) already matrices across Python 3.10–3.14 via `uv`, and the project already depends on Astral's `ruff` and `uv`, making Astral's `ty` a natural first candidate to try before falling back to the more established `mypy`/`pyright`.

## Goals / Non-Goals

**Goals:**
- Pick one type checker (`ty` if it handles this codebase well, else `mypy` or `pyright`) and gate CI on it.
- Keep the gate green from the moment it's added — no starting in a known-failing state.
- Minimize config: reuse the existing `code_check` job rather than adding a new matrix/job.

**Non-Goals:**
- Chasing 100% strictness immediately (e.g. `--strict` mypy mode) — start with defaults and tighten later if desired.
- Type-checking `tests/` — scope is `src/snakestream` only, matching the coverage config's `source = ["snakestream"]`.
- Running the type checker across the full 3.10–3.14 matrix — one representative Python version is enough, mirroring how the coverage gate is only enforced on 3.14.

## Decisions

- **Try `ty` first**: it's Rust-based (fast, matching `ruff`'s speed profile), from the same vendor already in the toolchain (`uv`, `ruff`), and actively developed. Alternative considered: default straight to `mypy` (most mature, widest community usage, but slower and more config-heavy) or `pyright` (mature, fast, but Node/npm-based tooling that doesn't fit the `uv`-only dev workflow as cleanly). Decision: spend a short, bounded evaluation on `ty`; fall back to `mypy` if it chokes on this codebase's `Awaitable`-union type aliases or the `TYPE_CHECKING`-guarded import in `stream.py`.
- **Add as a `uv run --with` step, not a permanent dev dependency, until proven**: run `uv run --with ty ty check src` during evaluation (same pattern already used for `pip-audit` in CI) to avoid committing to a dependency before confirming it works. Once validated, promote it to `[dependency-groups] dev` in `pyproject.toml` for local use (`uv run ty check`) and pin the CI step accordingly.
- **Single CI leg, not full matrix**: add the type-check step gated to one Python version (align with the existing `if matrix.python-version == '3.14'` pattern used for `pip-audit` and the coverage gate), since type-checking results don't meaningfully vary across CPython versions the way branch-coverage measurement does.
- **Fix real errors, don't suppress broadly**: if the chosen checker finds genuine type drift, fix it inline as part of this change rather than blanket-ignoring, so the gate is meaningful from day one. Scoped per-line ignores (with a comment explaining why) are acceptable for rare, justified cases (e.g. known checker limitations with the codebase's `Awaitable`-typing pattern).

## Risks / Trade-offs

- [Risk] `ty` is newer and may have rough edges with `Awaitable`/`Union` heavy code in `type.py`, or with the `TYPE_CHECKING`-guarded `StreamBuilder` import → Mitigation: bounded local evaluation before committing; fall back to `mypy` if `ty` produces excessive false positives or crashes.
- [Risk] Adding a new gate could surface a backlog of real type errors, expanding scope beyond "add a checker" → Mitigation: fix straightforward errors as part of this change; if the backlog is large, scope this change down to a minimal passing baseline and file follow-up items rather than blocking the whole change.
- [Risk] Single-Python-version enforcement could miss version-specific typing differences (e.g. `typing` module changes across 3.10–3.14) → Mitigation: acceptable trade-off consistent with the existing coverage-gate precedent; revisit if it causes a real miss.

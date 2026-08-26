## Why

Story 2 of the second 2026-08-25 batch is the last open item in the roadmap's
**Now**, unblocked now that story 1 landed the `collector.py` -> `collectors.py`
split. It bundles six findings that all point the same way: places where the
code hand-rolls something the interpreter or the linter already provides, plus
the lint gate that would have caught most of them.

The lint half is the reason to do it now rather than incrementally. A trial run
of `ASYNC,B,SIM,RUF,PERF,C4,RET,PIE,FURB,PLR,PLW` over `src/` on 2026-08-25
produced **nine findings total** — the cleanup cost of turning those rules on is
already paid by parts (b)-(e) of this same change. `ASYNC` found nothing at all,
which is precisely why it is worth enabling: it costs nothing today and guards
the one thing this library is entirely made of.

## What Changes

- **(a) `anext()` for `__anext__()`.** `execution.py` calls `source.__anext__()`
  (`_guarded`) and `branch.__anext__()` (`race_through`, two sites) directly.
  `anext()` is a builtin as of 3.10 — the same floor that made the `aiter()`
  already used twenty lines away available.
- **(b) stdlib shapes in `collectors.py`.** `_finish_groups` becomes an async
  dict comprehension with the loop-invariant `finisher is not None` test hoisted
  out; `partitioning_by._supply` stops looping over a two-element literal tuple
  to build a two-key dict.
- **(c) `RUF005` at `stream.py:128`:** `self._chain + [op]` -> `[*self._chain, op]`.
- **(d) `RUF036` — `None` mid-union in three `type.py` aliases.** For `Consumer`
  and `BiConsumer` this is a mechanical reordering. For `Mapper` it is not:
  **BREAKING (typing only)** — `None` is dropped from `Mapper` entirely, so
  `Mapper[T, R]` becomes `Callable[[T], R | Awaitable[R]]`. A mapper that
  genuinely returns `None` is already expressible by binding `R = None`; the
  union only widened every `.map()` result to optional, and nothing documented
  why. No runtime behaviour changes.
- **(e) `__init__.py`'s `finally: del` misses `dist_name`.** The `del` at `:11`
  drops `version` and `PackageNotFoundError` but not the `dist_name` bound at
  `:6`, so `snakestream.dist_name` is importable today (verified 2026-08-26).
  It is removed from the module namespace. Nothing in `src/`, `tests/`, or
  `README.md` references it.
- **(f) Widen the ruff selection.** `E,F,W,C90,UP` gains
  `ASYNC,B,SIM,RUF,PERF,C4,RET,PIE,FURB,PLR,PLW` over `src/`. Two findings are
  genuine false positives and get a `noqa` carrying its reason rather than a
  fix; `B008` on the two `downstream: Collector = to_list()` defaults is
  answered with a module-level `_TO_LIST` so the statelessness argument sits
  where the default is written. `tests/` is deliberately **out of scope**.

## Capabilities

### New Capabilities
- `lint-rule-selection`: which ruff rule families the CI lint gate enforces over
  `src/`, and the rule that a suppression must carry the reason it is correct
  rather than silently disabling a check.

### Modified Capabilities
- `generic-stream-typing`: the `Mapper` alias's declared return type. The
  existing requirement fixes that `Mapper` declares both a sync and an
  `Awaitable` arm; it does not say the result may be `None`, and the `None` arm
  contradicts the requirement that `map()` returns `Stream[R]` for a mapper
  returning `R`.

## Impact

- **Source:** `src/snakestream/execution.py` (a), `collectors.py` (b, f),
  `stream.py` (c), `type.py` (d), `__init__.py` (e),
  `callable_dispatch.py` (f, `noqa` only).
- **Config:** `pyproject.toml` `[tool.ruff.lint] select` (f).
- **Public API:** `snakestream.dist_name` disappears (e) — an accidental
  export, never documented. `Mapper`'s declared type narrows (d); `ty` must
  still pass clean.
- **Tests:** no test file should need editing. That is the tripwire for the
  whole change: parts (a)-(e) change no behaviour, so a diff that forces a test
  edit has gone wider than the story.
- **Benchmarks:** none. Every site touched runs once per import, per stream
  construction, per composition, or per collection — `_finish_groups` runs at
  `end()`. Reaching a per-element path is the signal the change overran; do not
  spend a harness run on it.
- **Docs:** README's parity tables are unaffected — no public method is added
  or renamed.

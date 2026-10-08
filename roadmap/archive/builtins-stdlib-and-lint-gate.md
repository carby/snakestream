+++
id = "builtins-stdlib-and-lint-gate"
title = "Built-ins, stdlib and the lint gate"
filed = 2026-08-26
closed = 2026-08-26
outcome = "shipped"
+++

**Built-ins, stdlib and the lint gate** (2026-08-26). Story 2 of the second
2026-08-25 batch, and the one that waited on story 1. Six findings, one
change: `openspec/changes/builtins-stdlib-and-lint-gate`.

**The tripwire held.** 567 tests pass with **no test file edited**, coverage
98.04% against the 98% gate, `ty check src` clean, and the diff touches
exactly eight files — the seven modules named in the story plus
`pyproject.toml`.

**(a) `anext()` at all three sites**, `_guarded`'s and both of
`race_through`'s. **The roadmap was wrong that this story faces no
per-element code**: all three of these run once per element, not once per
composition, and the "do not spend a harness run on it" note applied to
everything in the story except exactly this part. Measured rather than
asserted, 300k elements, five reps, both orderings: `anext(it)` **69ms**
best / 70ms median against `it.__anext__()` **79ms** best / 81ms median —
about **13% faster**, ~35ns per element, the builtin's type-level lookup
beating the instance attribute lookup. So the per-element hunk is a small
improvement. The `aiter()` comment at `:151` was left alone (it explains
arity, not the builtin); the adjacent `:153` comment was refreshed to name
the call the next line makes.

**(b) `_finish_groups` and `partitioning_by._supply`.** The invariant left
the loop rather than the comprehension merely wrapping the branch: no
finisher now returns `dict(groups)` outright, and the finishing arm is one
async dict comprehension. `_supply` builds its two-key dict directly.

**(c)** `[*self._chain, op]` in `_extend` (that line lives in `_derive()`
since 2026-08-26). **(e)** `dist_name` joins the
`finally: del`; `snakestream.dist_name` is gone (verified importable before,
absent after) and `__version__` still resolves.

**(d) `Mapper` lost its `None` arm entirely** rather than taking `RUF036`'s
reordering. The user's call, put before the specs were written. The union
widened every `.map()` result to optional for nothing — a mapper returning
`None` is already `R = None` — and `ty` confirms the fix: `.map(to_str)` now
reveals `Stream[str]` where it read `Stream[str | None]`, and a `str | None`
mapper still binds `R` to `str | None`. No internal site was leaning on the
optional. `Consumer` and `BiConsumer` took the plain reorder, `None` to the
tail. Recorded as a delta on the `generic-stream-typing` spec, since a typed
`map()` result is externally visible.

**(f) The selection widened to
`E,F,W,C90,UP,ASYNC,B,SIM,RUF,PERF,C4,RET,PIE,FURB,PLR,PLW`** — exactly the
trialled set, no family added unmeasured. **The trial was over `src/` and the
gate is not**: `ruff check .` immediately turned up 262 findings in `tests/`,
which the story excluded. Resolved with a `per-file-ignores` entry dropping
the new families for `tests/**` while `E,F,W,C90,UP` still apply everywhere,
so the scope the story decided is the scope the config enforces. `src/` is
clean. `B008` took the `_TO_LIST` module-level default over a `noqa`, so the
statelessness argument sits where the default is written; `RUF023` sorted
`Collector.__slots__`; and both false positives carry a rule-scoped `noqa`
with its reason inline — `B004` on `callable_dispatch.py`'s class-level
`__call__` lookup, `PERF203` on the close-handler loop. Neither is a
file-level ignore. **`ASYNC` still finds nothing**, which was the argument
for it.

+++
id = "collapse-derive-wrappers"
title = "Collapsed the derive wrappers into one copier"
filed = 2026-08-26
closed = 2026-08-26
outcome = "shipped"
+++

**Collapsed the derive wrappers into one copier** (2026-08-26). `_extend(op)`
and `_derive_executor(executor)` were one-expression wrappers over
`_derive(chain, executor)`, each passing one axis through unchanged while the
call site wrote the other as noise. There is now one
`_derive(self, op: Op | None = None) -> Stream[Any]`: the chain-extension rule
lives in its body, and `sequential()`/`parallel()` derive with no op and
assign `_executor` themselves. See
`openspec/changes/archive/2026-08-26-collapse-derive-wrappers`.

**This is the third pass over the same cluster, and what matters is why it is
not a revert of the first.** The 2026-08-24 merge landed the same one-copier
shape and was undone in two steps — `_extend` on 2026-08-25, then
`_derive_executor()` re-added on 2026-08-26 — because it paid two costs, and
both are avoidable independently of the layer count:

- *The copier took a pre-built chain*, so each of the nine op methods spelled
  out `[*self._chain, op], self._executor` and the `Op` the method is *about*
  became the least visible part of the line. Taking the `Op` instead puts the
  rule in the callee: `return self._derive(_MapOp(mapper))`, which is
  `_extend`'s ergonomics exactly. That property is what had to survive, and it
  did.
- *The docstring was copied verbatim onto both public methods.* It now sits on
  `sequential()` alone, at full length, with `parallel()` pointing at it —
  because the new body is a working template for the move
  `pipeline-immutability` forbids: delete one line and
  `derived._executor = RACING` becomes `self._executor = RACING; return self`.
  The warning moved to where the temptation now is rather than staying where
  it happened to be.

`op is not None`, not `if op`: every `Op` is truthy today, but `_UnorderedOp`
carries no state, and an `Op` that later grew `__bool__`/`__len__` would be
silently dropped from the chain by a truthiness test. **Accepted knowingly:**
`_executor` is no longer assigned exactly once per instance — the copier sets
it and the mode method overwrites it. Unobservable today (no `await` between
the two statements, the instance has not escaped), and recorded so that adding
an `await` to `_derive()` is recognised as breaking it. **Retired by
`unify-derive-signature` (2026-08-27):** `_derive()` grew an `executor`
parameter and assigns `new_stream._executor = executor or self._executor`
once, so there is no longer a second statement for an `await` to land
between.

**`_derive()` stays a method on `Stream`**, explicitly rather than by default.
Moving it beside `execution.py`'s `_wrap_sink`/`_copy_into`/`stream_through`
fails that family's own membership rule — none of them needs a stream
instance, and `_derive()` *is* the thing. The `self._consumed = True` it
performs is the `pipeline-immutability` invariant, and an invariant enforced
from outside the class is one every future call site can route around. Checked
against the roadmap rather than assumed: neither a third `Executor` nor
`spliterator()` constructs a `Stream`, so neither creates the payoff a
module-level version would need.

**583 tests green with no test file edited** — the tripwire, since
`pipeline-immutability`, `pipeline-composition` and `stream-execution-model`
already pin every contract touched, including that a queued chain survives a
mode switch. `ruff`, `ruff format --check`, `ty check src`,
`--cov-fail-under=98` (98.06%) and `openspec validate --strict` all pass.
`skip_specs: true`: no observable behaviour changed. Off the per-element path
(chain-building and mode-switch code, run once per composition), so no
benchmark gate applied. The dead `cast()` went in a separate first commit —
`_derive()` returns `Stream[Any]` and `Any` is assignable to `Stream[T]`, the
same finding the 2026-08-25 batch made for the eight intermediate ops, which
never reached these two methods because they called `_derive()` directly then.

**The prose sweep found more than the tasks named, and that is the reusable
lesson.** Five stale references were annotated, not three: the tasks cited
`roadmap.md:1195` and `727-745`, both of which had drifted, and the sharpest
one they missed was the 2026-08-26 entry claiming "`_derive_executor()` now
exists and owns the shared explanation". History entries are annotated as
superseded, never rewritten to pretend the prior shape never existed. This is
not tidiness — `_derive_executor()` was resurrected in the first place
*because* `CLAUDE.md` described a method that did not exist, and leaving the
Done entries stale would arm the same mechanism again. Cite the sentence in a
documentation task, not the line number.

+++
id = "merge-derive-and-derive-executor"
title = "Merged `_derive()` and `_derive_executor()` into one copier"
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Merged `_derive()` and `_derive_executor()` into one copier** (2026-08-24).
`stream.py:99-106` and `stream.py:132-137` were line-for-line the same
five-field copy — `self._stream`, `self._close_handlers`, `self._chain`,
`self._ordered`, `self._executor` — differing only in whether `_chain` or
`_executor` was the field that varied. Now one `_derive(self, chain:
list[Op], executor: Executor) -> Stream[Any]` takes both as parameters: the
eight intermediate ops call `self._derive(self._chain + [op],
self._executor)`, and `parallel()`/`sequential()` call
`self._derive(self._chain, RACING)` / `self._derive(self._chain,
SEQUENTIAL)`. `_derive_executor()` is gone.

Landed to the shape the roadmap's own implementation notes proposed, with
one adjustment: the pre-existing `_derive()` took a single `op: Op` and
composed `self._chain + [op]` internally rather than taking a pre-built
chain, so the call sites (not just the method body) needed the `self._chain
+ [op]` expression moved onto them — the unified signature is
`_derive(chain, executor)` exactly as designed, only the caller-vs-callee
split of that one line differs from the sketch. The check-before-copy /
consume-after-copy ordering is unchanged: `_check_not_consumed()` still runs
before the copy and `self._consumed = True` still after, so a raising copy
leaves the receiver valid. The `_derive_executor()` docstring ("must not
compose", "must not assign onto self") moved onto `parallel()` and
`sequential()` rather than being deleted with the method, since those two
are the only call sites its warning actually protects.

535 tests green with **no test file edited**; `ruff`, `ruff format --check`
and `ty check src` all pass. A grep for `_derive_executor` across `src/` and
`openspec/specs/` after the edit returns nothing. `skip_specs: true`: no
spec-level behavior changed, only where the copy-constructor logic lives.

**Superseded 2026-08-26 by `collapse-derive-wrappers`.** This merge was
reverted on 2026-08-25/26 and has now been redone in a different shape, so
read the two costs it paid rather than the signature it landed. The copier
takes the `Op`, not a pre-built chain — `_derive(op: Op | None = None)` —
which is what keeps the nine call sites one-liners instead of spelling the
chain-extension rule out nine times, the cost that brought `_extend` back.
And the docstring is not copied onto both public methods, which is the cost
that brought `_derive_executor()` back: it sits on `sequential()` alone.
Off the per-element path (chain-building/mode-switch code, run once per
composition), so no benchmark gate applied. See
`openspec/changes/unify-derive-copier`.

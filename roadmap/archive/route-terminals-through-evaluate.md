+++
id = "route-terminals-through-evaluate"
title = "Routed every terminal through `_evaluate()`"
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Routed every terminal through `_evaluate()`.** `_evaluate()`'s docstring
called itself "the one place a stream's execution mode is consulted", but
`for_each_ordered()` and `find_first()` each bypassed it and hand-rolled
`self._check_not_consumed()` + `SEQUENTIAL.value(self._chain, self._stream,
sink)` directly — three drive sites instead of one. `_evaluate()` gained an
optional `executor: Executor | None = None` parameter
(`(executor or self._executor).value(...)`); both terminals now read
`await self._evaluate(sink, SEQUENTIAL)`.

Landed exactly to the shape this entry's own implementation notes proposed,
with no surprises: no behaviour changed (both terminals still force
sequential/ordered execution regardless of the stream's mode,
`find_first()`'s `is_ordered()` short-circuit to `find_any()` untouched),
and the `stream-find-first` spec's wording ("achieve this by naming the
sequential executor explicitly for that drive") held verbatim against the
new call shape — checked directly, no edit needed. `skip_specs: true`: no
spec-level behavior changed, only how many places decide which executor
drives a terminal. 535 tests green with **no test file edited**; `ruff`,
`ruff format --check`, `ty check src` and `openspec validate --strict` all
pass. A grep for `self._stream` after the edit confirms only `__init__`,
`_derive`, `_compose`, `_evaluate` and `_derive_executor` reference it now —
`for_each_ordered()` and `find_first()` were the only two hand-rolled call
sites, and both are gone. See
`openspec/changes/route-terminals-through-evaluate` (pending archive).

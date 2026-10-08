+++
id = "chain-building-and-dead-code-smalls"
title = "Chain-building and dead-code smalls"
filed = 2026-08-25
closed = 2026-08-25
outcome = "shipped"
+++

**Chain-building and dead-code smalls** (2026-08-25). Story 3 of the
2026-08-25 batch, and the last of its three `stream.py` stories. Four
independent findings, one commit each, none of them observable.

**(a)** The eight intermediate ops were each the same 90-column line —
`cast("Stream[X]", self._derive(self._chain + [_SomeOp(...)], self._executor))`
— so the chain-extension rule was written eight times while the one thing
each method is *about*, the `Op` it queues, was the least visible part of
the line. A private `_extend(op)` now holds
`self._derive(self._chain + [op], self._executor)`, and each op is a
one-liner: `return self._extend(_MapOp(mapper))`.

`_extend` takes a **built** `Op` rather than the class plus its arguments.
The eight `Op` constructors take between zero and two arguments of unrelated
types (`_DistinctOp()` takes none, `_SortedOp` takes a comparator and a
flag), so an `_extend(op_cls, *args)` form would degrade to `*args: Any` and
lose exactly the type information the call site has. It also does not run
`_check_not_consumed()` — `_derive()` already does, and duplicating the
guard one frame up would make it ambiguous which one is load-bearing.
`_derive_executor()` was deliberately left out: `parallel()`/`sequential()`
pass `self._chain` **unchanged** under a different executor, the opposite of
what `_extend` does, and folding both into one helper would re-couple what
the batch's earlier stories separated.

**Superseded 2026-08-26 by `collapse-derive-wrappers`:** `_extend` is gone,
and so is `_derive_executor()`; there is one `_derive(op: Op | None = None)`.
The ergonomic win described above survives intact — the call site is now
`return self._derive(_MapOp(mapper))`, the chain-extension rule still lives
in exactly one body, and the built-`Op`-not-class argument is unchanged and
for the same reason. What changed is where the rule lives: in the copier
itself rather than a wrapper over it, which is what let the executor axis
leave the copier's signature instead of being passed through as noise.

**Beyond the story as written: the eight `cast()` wrappers went too, and
that is most of the win.** The `cast` was never necessary — `_derive()`
returns `Stream[Any]`, and `Any` is assignable to each method's declared
return type, so the cast narrowed nothing while reading like a real
narrowing. Verified against the `ty` version CI runs on the 3.14 leg before
committing to the shape, since `cast` is erased at runtime and no test can
tell the two forms apart. The `cast` import stays: `sequential()`,
`parallel()`, `iterate()` and the 3-arg `collect()` still use it.

**(b)** `_ForEachSink._finish` deleted. `TerminalSink._finish` is
`return container`, `_ForEachSink._create_container` is `return None`, and
the sink assigns `self._container` nowhere else — so the override returned
`None` for the one input on which the base already returns `None`. Recorded
in the commit message because the override *looks* load-bearing: a reader
who assumes `for_each` must discard a result will read it as the thing doing
the discarding. It is not; `result()` being `None` comes from
`_create_container`. The three other `_finish` overrides in `terminals.py`
were checked and kept — each translates the `_UNSET` sentinel, which the
base does not do.

**(c)** `sorted(..., reverse: bool = False)`. `stream.py` now has no
unannotated parameter at all (AST-checked, not eyeballed).

**(d)** `asyncio.ensure_future` -> `asyncio.create_task` at both
`race_through()` sites. The benchmark exemption was written as
**conditional** rather than granted — it held only while the diff stayed a
one-word substitution at each site, and it did: two lines, one word each,
nothing else moved. Both arguments are `branch.__anext__()` on an async
generator, always a coroutine, so `ensure_future`'s
`isfuture`/`iscoroutine`/`isawaitable` ladder always landed on the coroutine
arm and called its internal `loop.create_task` anyway.

561 tests green, **no test file edited** — the entire verification story for
a change with no new behaviour to assert. `ruff`, `ruff format --check`,
`ty check src` and `openspec validate --strict` all pass, 98.03% coverage.
No spec impact: the change set `skip_specs: true`, the same treatment as
`split-ops-into-ops-module` and `collapse-terminal-drive-loop`. See
`openspec/changes/tidy-stream-chain-building`.

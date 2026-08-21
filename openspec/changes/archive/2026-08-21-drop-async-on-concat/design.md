## Context

See proposal.md — Why. The mechanics that shape the approach:

- `Stream.concat` is `async def` but its body is two statements with no
  `await`: build `_concat(a, b)`, wrap it in `Stream`. `_concat` is an
  `async def ... yield` generator function, so *calling* it constructs an
  async generator and runs none of its body.
- `_concat` reaches into `a._compose()` / `b._compose()`, which is legal here
  because it is module-private to `stream.py` and `_compose()` is
  non-consuming (`base_stream.py:151` neither checks nor sets `_consumed`).
- `Stream` is the only name `__init__.py` exports, and no code in `src/` calls
  `Stream.concat`. The only in-repo call sites are the two in
  `tests/test_concat.py`.
- The project is pre-1.0 and already carries a README migration log of
  breaking changes in exactly this shape; this change joins it.

## Goals / Non-Goals

**Goals:**

- Make `concat`'s call shape honest: no `await` on something that never
  suspends, consistent with the other four static factories on `Stream`.
- Break loudly, not silently, for anyone on the old signature.
- Zero change to what the concatenated stream produces, when it produces it,
  or how it composes.

**Non-Goals:**

- Touching `_concat`, the generator bridge, or `terminal-sinks`' rule that
  `concat` composes through it.
- Adding a variadic `concat(*streams)` overload (Java's is two-arg; that is a
  separate proposal if ever wanted).
- Changing `_consumed` bookkeeping for `a` and `b`. Today `concat` leaves both
  inputs unconsumed; that stays as-is so this change has exactly one
  observable effect.

## Decisions

**Clean break, no compatibility shim.** The alternative is returning an
awaitable-*and*-usable object (a `Stream` subclass implementing `__await__`
that returns itself), so both `Stream.concat(a, b)` and
`await Stream.concat(a, b)` keep working through a deprecation window.
Rejected: it would put an `__await__` on a `Stream` permanently or until a
second breaking change removes it, it makes the type signature worse than the
one being fixed, and the project's established convention for pre-1.0
signature changes is a hard break plus a migration-log line
(`stream_of()` -> `Stream.of()`, the `Stream.of()` kwargs removal, the
`str`/`bytes` change). One breaking change is cheaper than a shim plus a
later second break.

**Rely on the natural failure mode rather than a custom error.** After the
change, an unmigrated `await Stream.concat(a, b)` raises
`TypeError: object Stream can't be used in 'await' expression` at the call
site. That is immediate, unambiguous, and names the exact expression at fault
— better than a bespoke `StreamBuildException`, which would need `Stream` to
grow an `__await__` purely to raise from it, i.e. the shim above with worse
ergonomics.

**Keep `_concat` a module-level async generator function; only the
`staticmethod` changes.** `def concat(a, b) -> Stream[T]: return
Stream(_concat(a, b))`. Inlining `_concat`'s body into `concat` is not
possible — a function containing `yield` becomes a generator function — and
folding it into a lambda or comprehension would lose the `AsyncGenerator`
return type the bridge expects.

**The specs' laziness requirement is a codification, not a new behaviour.**
It is already true (nothing runs until the async generator is advanced) and is
worth pinning because the removed `async` is the thing a reader might mistake
for where the laziness came from.

## Risks / Trade-offs

- **Silent breakage for downstream users who wrap the call.** → Ruled out for
  the direct call: `await <Stream>` is a `TypeError`, not a no-op. The one
  shape that could go quiet is code doing `asyncio.gather(Stream.concat(...))`
  or similar, which now gets a non-awaitable and also raises. Mitigation is
  the migration-log entry, which is the project's established channel for
  this and is in scope here.
- **Type checkers will not flag every stale call site.** → `ty` catches
  `await` on a non-awaitable in typed code, but untyped downstream code only
  learns at runtime. Accepted: same trade-off as every prior entry in the
  migration log, and the runtime error is loud.
- **Churn for a one-line win.** → Accepted deliberately: the roadmap's
  argument is that the cost of the break only grows with the number of call
  sites shipped against the old signature, and today that count is two, both
  in this repo.

## Migration Plan

1. Change the signature and drop `await` at the two in-repo call sites in the
   same commit — there is no window where both forms work, by design.
2. Add the migration-log entry to README under the existing
   `## Migration` list, in the same `**0.3.5 -> next:**` form as its
   neighbours, stating the old form, the new form, and the `TypeError` an
   unmigrated caller sees.
3. Rollback is a straight revert of the same three files; no data, no state,
   no persisted artifacts are involved.

## Open Questions

None. The variadic-`concat` and `_consumed`-bookkeeping questions are named as
Non-Goals above rather than left open — neither is needed to decide this
change's specs, approach, or tasks.

## Context

See `proposal.md` — Why. The relevant constraint is that `_normalize()` is an
`async def ... yield` async generator, and the fix has to advance a sync
iterator from inside it. Everything else about the surrounding machinery
(`_accept()`, the chain, the sinks) is untouched.

## Goals / Non-Goals

**Goals:**

- Make the `__next__` arm of `_normalize()`'s guard reachable and correct, so
  the accepted-source set the README and `stream-construction` spec already
  advertise is the set that actually works.
- Keep the `__iter__` path byte-for-byte equivalent in behaviour, including
  laziness — a source is still advanced one element at a time as the pipeline
  pulls, never drained up front.

**Non-Goals:**

- No change to `dict`/`str`/`bytes` scalar handling, to the async side
  (`_accept()` / `_maybe_aclosing`), or to `Stream.of()`'s arity semantics.
- Not closing or otherwise lifecycle-managing sync sources. `_maybe_aclosing`
  covers async sources; sync iterators have no `aclose()` and this change does
  not invent a sync equivalent.

## Decisions

**Decision 1: support `__next__`-only sources rather than dropping the
`__next__` test from the guard.**

The roadmap frames this as the one open decision, with two honest fixes:
make the advertised support real, or narrow the guard so the accepted-source
set is honest. Choosing support, because three independent things already
promise it and only the implementation disagrees: README line 57 lists
`Iterator` among accepted sources; `openspec/specs/stream-construction`'s
"Iterable source spreading" requirement names `__next__` explicitly; and
`_maybe_aclosing`'s docstring exists specifically so that "a bare async
iterator implementing only `__anext__`" works on the async side. Narrowing
would mean editing all three to retract a capability, and would leave sync and
async source handling deliberately asymmetric for no reason anyone could point
at later. Supporting it is also the smaller diff.

*Alternative considered:* delete `or hasattr(source, "__next__")`, so such an
object falls through to the `else` and becomes a single scalar element. Cheap,
but it silently turns a `TypeError` into a wrong-looking one-element stream —
worse than the current loud failure, and it contradicts the spec.

**Decision 2: dispatch on `__iter__` first, `__next__` second — not one
merged path.**

Structure the branch as: if the source has `__iter__`, keep `for i in source`;
otherwise (it has `__next__`) drive it with `next()`. Routing everything
through `next()` would work for well-behaved iterators but would change
behaviour for plain iterables (lists, tuples, sets, dicts' views) that are not
themselves iterators — `next([1, 2, 3])` is a `TypeError`. Keeping `for` as
the primary path also means the overwhelmingly common case executes exactly
the code it does today, so the fix cannot regress it.

**Decision 3: catch `StopIteration` explicitly inside the loop; never let it
propagate.**

This is the non-obvious part. Under PEP 479 a `StopIteration` escaping a
generator body is converted, and inside an *async* generator it surfaces as
`RuntimeError: async generator raised StopIteration` — verified by direct
repro. So the loop must be `while True: try: value = next(source) except
StopIteration: return` with the `yield` outside the `try`, not a bare
`yield next(source)`. Putting the `yield` inside the `try` would additionally
swallow any `StopIteration` a downstream consumer's `athrow()` delivered, so
the `try` wraps the `next()` call alone.

*Alternative considered:* `for i in iter(source.__next__, sentinel)`, using the
two-argument `iter()`. Rejected — it requires inventing a sentinel value that
the source is guaranteed never to yield, which is exactly the unsafe
assumption the library avoids elsewhere (it carries a dedicated `_UNSET`
sentinel in `sink.py` for precisely this reason, and reusing that here would
couple normalization to the sink module for no gain).

## Risks / Trade-offs

- **A source implements `__next__` but is not a real iterator (e.g. it has
  `__next__` as an unrelated method name)** → It gets driven to exhaustion or
  raises whatever that method raises, instead of becoming a scalar element.
  This is already the guard's stated contract and matches Python's own
  duck-typed iterator protocol; no mitigation beyond documenting via the spec
  scenarios.
- **A `__next__`-only source that never signals exhaustion streams forever** →
  Identical to the existing behaviour for an infinite generator source, which
  the library already supports and pairs with `limit()`. Not a new risk.
- **Coverage gate**: the new arm is a distinct branch and the project runs a
  branch-coverage gate, so it must be covered in the same change or CI fails.
  Mitigated by the tests being part of this change's task list, including the
  immediately-exhausted case that covers the `except StopIteration` arm.

## Migration Plan

None needed. The change is additive at the behaviour level: every source that
works today produces identical output, and the only sources whose behaviour
changes are ones that raise `TypeError` today. No public signature changes, so
no README migration-log entry (unlike roadmap item 5).

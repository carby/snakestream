## Context

See proposal.md — Why. What shapes the approach:

- `close()` (`stream.py:436`) loops the handler list, catches per handler into a
  list, and — if any raised — attaches every later exception to the first as a
  note and raises the first. That failure contract is specified in detail and
  must be reproduced, not re-derived, by anything that also runs handlers.
- `callable_dispatch.py` already owns the question "is this user-supplied
  callable async?", and answers it in two tiers: `is_async_callable(fn)` is
  decidable *before* invoking; a plain `def` returning a coroutine is only
  detectable *after*, via `isawaitable(result)`.
- `_accept()` (`stream.py:95`) passes any `AsyncIterable` through untouched as
  the source, and `Stream` implements `__aiter__`. So the source slot can
  already hold a `Stream` object. `execution._maybe_aclose()` (`:62`) tears a
  source down with `getattr(thing, "aclose", None)` — a probe a `Stream` is
  about to start answering. This is the one place where an additive change is
  not additive.
- Close is a once-per-pipeline operation. Nothing here is on a per-element path,
  so no decision below is a performance decision.

## Goals / Non-Goals

**Goals:**

- One handler list, one failure contract, two ways to run it.
- Reuse `callable_dispatch`'s existing classification rather than growing a
  second notion of "async callable" in `stream.py`.
- Leave the source slot in a state where `Stream` growing an `aclose` attribute
  cannot change what consumption does.

**Non-Goals:**

- Making `close()` able to complete an awaitable handler by any means.
- Firing close handlers implicitly on exhaustion, cancellation or garbage
  collection. Java does not, and `stream-close-handling` is explicit that
  `close()` is the trigger.
- Closing the source from `aclose()`. See decision 5.
- Any change to how close handlers propagate across `sequential()`/`parallel()`
  or `concat()`; those requirements are untouched and the new method inherits
  them by reading the same list.

## Decisions

### 1. Widen the alias; do not add a second one

`CloseHandler` becomes `Callable[[], Awaitable[None] | None]` in `type.py`,
which makes it the nullary `Consumer` — `Consumer[T]` is already
`Callable[[T], Awaitable[None] | None]`. Every other alias in that file already
permits both implementations, so this removes an exception rather than adding a
concept.

*Alternative rejected:* a second `AsyncCloseHandler` alias with `on_close()`
overloaded across the two. It would put the sync/async split in the type system,
where it would then have to be honoured by `_close_handlers`, `concat()`'s list
concatenation and the two closers — four places paying for a distinction that is
decided per invocation anyway. The library's uniform answer to "sync or async
callable?" is one alias and a runtime classification, and this is that question.

### 2. `close()` refuses an awaitable handler; it does not skip or drive it

Three alternatives were weighed and all lose:

| Filling for "sync `close()`, async handler" | Why not |
|---|---|
| Skip it silently | The resource is never released and Python's only complaint is a `RuntimeWarning` from a garbage-collected coroutine, raised far from the call site and easily unseen. |
| Drive it (`asyncio.run`, or reach for a running loop) | Only possible when no loop is running; every terminal here is a coroutine, so the common case is exactly the one where it is impossible. Behaviour forking on "does a loop happen to be running" is worse than either branch alone. |
| Make `close()` itself async | Removes `with`, removes `contextlib.closing()`, and breaks the documented `DsnStream(dsn)` subclass shape. Ruled out by the roadmap item's own framing: the sync `close()` stays as it is. |

So: raise. `StreamBuildException`, on the same reading `ComparatorContractException`'s
docstring already sets out — "build" names the fault (the pipeline was assembled
with a handler this closer cannot run), not the moment it is discovered, which
here is at close time because a callable's shape is only knowable when it is
classified or invoked.

The refusal is raised from **inside** the existing per-handler `try:`, not
before or around the loop. That is what makes it cost no new plumbing: it lands
in the same `exceptions` list as a handler's own failure and inherits the whole
specified contract for free — remaining handlers still run, first-in-encounter-order
still propagates, later ones still ride along as notes. A refusal that
short-circuited the loop would be a second failure contract to specify and test.

### 3. `aclose()`, and the source-slot collision it creates

**Name.** `aclose()`. Java offers nothing to match (there is no counterpart), so
the Python precedent decides: `AsyncGenerator.aclose()`, `contextlib.aclosing()`,
and this repo's own `_maybe_aclose`/`_maybe_aclosing`. It also makes
`contextlib.aclosing(stream)` work by construction, mirroring
`contextlib.closing(stream)` — the same "wrapper standing in for two methods"
story `__enter__`'s docstring already tells.

**The collision.** The same precedent is what breaks: `_maybe_aclose()` probes
`getattr(thing, "aclose", None)` on the source, and a `Stream` can *be* the
source. Add the method and `Stream(inner_stream)` starts firing `inner_stream`'s
close handlers at the end of the outer stream's consumption — implicitly, on a
path where no caller wrote a close, and on abandonment as well as exhaustion.
That is a divergence in observable API behaviour, which the roadmap's guiding
principle calls a defect rather than an internal liberty. There is no test over
`Stream(stream)` today, so it would land silently.

**Resolution: the source slot stops being able to hold a `Stream`.** `_accept()`
unwraps a `Stream` source to `source.iterator()` — non-destructive, per that
method's own contract, and composing an async generator pulls nothing. The
invariant becomes "the source is an iteration, never a stream", and
`_maybe_aclose()` then closes the composed generator, which cascades to the
inner source, which is what source teardown *means*. The probe never sees a
`Stream` again, so the collision cannot recur under a later rename either.

*Alternatives rejected:*

- **Name it `close_async()`.** Dodges the probe by accident, forfeits the
  `aclosing()` mirror, leaves the trap armed for whoever renames it later — and
  leaves today's real gap in place: a `Stream` in the source slot has its
  iteration torn down by nothing at all.
- **Guard the probe** with `isinstance(thing, Stream)`. Fixes this instance and
  not the class of problem, and inverts `execution.py`'s dependency on
  `stream.py` to do it.
- **Narrow `_maybe_aclose()`'s probe** to async generators specifically. Its
  docstring says it asks the loose question deliberately, so that a bare
  `__anext__`-only async iterator with an `aclose()` is still closed.

One consequence to accept: unwrapping at construction means a `Stream` built
over an already-consumed stream raises `IllegalStateException` at construction
rather than at consumption. Earlier and at the offending call — an improvement,
but a visible timing shift, so it belongs in the tasks as a thing to check
rather than assume.

**Correction found during task 1.1 (implementation):** the paragraphs above
analyze a silent divergence — handlers firing implicitly where no caller wrote
a close. The actual current behaviour is not silent: `Stream.__init__` builds
`_accept(source) or _normalize(source)`, and because `_accept()` returns a
`Stream` source unmodified, the `or` forces a truthiness check on it —
`Stream.__bool__` raises by design (`python-data-model`), so `Stream(other_stream)`
raises `TypeError` at construction today, before any handler cascade is
reachable. The unwrap this decision prescribes fixes that crash as a side
effect, since `source.iterator()` returns a plain `AsyncGenerator`, which the
`or` treats as ordinarily truthy. Group 1's regression tests pin the corrected
premise: against unmodified `src/` they fail with `TypeError` from `__bool__`,
not with a spuriously-invoked handler assertion.

### 4. Classification: reuse both tiers, and admit the asymmetry

`aclose()` needs no classification at all — `isawaitable(result)` on the return
value is the whole test, and it is exact. `close()` uses both tiers:

```
  is_async_callable(h)  True  -->  refuse BEFORE calling.   Resource untouched.
                       False  -->  call it, then
                                     isawaitable(result)?  -->  refuse AFTER.
                                                                Side effect has
                                                                happened; the
                                                                close is half done.
```

The second branch is lossy and cannot be made otherwise — a plain `def`
returning a coroutine is indistinguishable from a plain `def` until it has run.
The spec states it rather than hiding it. Note the two tiers exist here for a
different reason than at the per-element call sites: there, tier two is a
one-time correctness net for a callable that classified wrong; here it is the
difference between refusing before and after a side effect.

`close()` does **not** memoise classification the way `AsyncDispatch` does. The
handler list is walked once per `close()`, so there is no repeat to amortise,
and the mixin's state is per-sink by design.

### 5. What the two closers share, and what they don't

They differ in one step (invoke vs. invoke-and-maybe-await) and share the tail
that decides which failure propagates and how the others are attached. The tail
is what gets factored out — a private helper taking the collected exceptions and
raising. That is centralising *the contract and the note wording*, which is the
case `feedback_thin_helpers_earn_nothing` explicitly allows; the loop itself
stays duplicated, being two genuinely different loops that a shared body could
only rejoin behind a flag.

Neither closer touches `self._stream`. Awaiting the source's own `aclose()` from
`aclose()` is one keystroke away and would make the twins observably different —
`close()` releases handlers, `aclose()` releases handlers *and* the source —
which is the divergence decision 3 exists to prevent, arriving through the
front door. Java's `close()` does not touch the traversal either.

`aclose()` runs handlers sequentially, never `asyncio.gather`. Gathering would
break both "in registration order" and the definition of "the first exception in
encounter order", i.e. two specified requirements, to save latency on an
operation that runs once per pipeline.

### 6. Both context-manager protocols, neither preferred

`__aenter__` returns `self`; `__aexit__` awaits `aclose()` and returns `None` so
nothing is suppressed — the same two lines `__enter__`/`__exit__` already are,
against the other closer. `__exit__` is not reimplemented or narrowed: `with`
keeps delegating to `close()`, which means a stream carrying an awaitable
handler is refused at block exit on exactly `close()`'s terms. That is the
correct outcome and needs no code, but it does need a scenario, because
"delegation is total" is the property that keeps the two protocols from drifting.

## Risks / Trade-offs

- **`Stream(stream)` is untested today, and decision 3 changes what it does
  internally** → Add the stream-as-source scenarios first, against the current
  implementation, and confirm they pass before the unwrap lands. A test that
  only ever ran after the change proves nothing about what it preserved.
- **`with` over an async handler is a runtime failure, not a static one** → `ty`
  cannot catch it: the widened alias makes the handler well-typed and only the
  closer is wrong. Mitigated by the message, which must name the handler and
  point at `aclose()`/`async with` rather than reporting an unusable type error.
- **The after-the-fact refusal leaves a half-run close** → Unavoidable
  (decision 4); specified rather than papered over, and the message must not
  claim the resource is untouched.
- **Two protocols, one of which silently does less** → A reader could take
  `async with` as the strictly better option and use it everywhere. The spec
  says otherwise, and `sequential()`'s docstring is the precedent for putting
  the rules in one place and pointing the twin at it: state the rules on
  `aclose()` and have `close()` reference them.
- **Coverage gate (98%) over new branches** → The refusal has two arms
  (before-call, after-call) and `aclose()` has the sync/awaitable fork; each
  needs a test or the gate fails on the GIL-enabled leg.

## Open Questions

- Whether `roadmap/items/async-with-on-stream.md` splits. The
  stream-as-source question (decision 3) is a distinct piece of work with its
  own risk profile, and the roadmap's "scaffolding earns an edit to the item"
  rule contemplates exactly this. Deferrable: it changes neither the specs nor
  the task breakdown, only how the queue records them.
- Whether the main `stream-close-handling` spec's `## Purpose` line, which names
  only `on_close()`/`close()`, is updated by this change's archive or by the
  standing post-archive sweep.

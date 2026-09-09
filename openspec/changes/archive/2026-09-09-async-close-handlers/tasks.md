Both of design.md's Open Questions are resolved here rather than left implicit,
because both name work that appears below: the roadmap item is **not** split
(task 8.1 edits it in place), and the `stream-close-handling` `## Purpose` line
is updated by this change (task 8.2) rather than left to a later sweep. Neither
resolution changes what gets built.

Task group 1 runs **first, and against unmodified `src/`**. It pins behaviour
that group 6 then has to preserve; a test that only ever ran after the change
would prove nothing about what it preserved (design.md — Risks).

## 1. Pin the stream-as-source behaviour before touching anything

- [x] 1.1 Add `tests/test_close.py` coverage for a `Stream` used as another
      stream's source: build `inner = Stream([1, 2, 3]).on_close(handler)`, then
      `Stream(inner)`, consume the outer to exhaustion, and assert `handler` was
      never invoked. Verify it passes against unmodified `src/` — if it does
      not, stop: the premise of group 6 is wrong and the design needs revisiting
      before any code changes.
      **Corrected:** against unmodified `src/` this fails with `TypeError`
      from `Stream.__bool__`, not a wrongly-invoked handler — see design.md's
      "Correction found during task 1.1". User directed proceeding with the
      task 6.1 fix as written, which also resolves the crash; the test stands
      as group 6's regression gate
- [x] 1.2 Add the short-circuit twin of 1.1 — the outer stream consumed under a
      short-circuiting terminal (`find_any()`) rather than to exhaustion — and
      the follow-up assertion that closing `inner` afterwards still invokes the
      handler exactly once. Same corrected premise as 1.1 applies
- [x] 1.3 Record in the change (a comment in the new tests naming
      `_accept()`/`_maybe_aclose()`) that these pin the
      `stream-close-handling` requirement "A stream consumed as another stream's
      source does not fire its close handlers", so a later reader knows why an
      apparently unrelated test lives in `test_close.py`

## 2. Widen the handler type

- [x] 2.1 Widen `CloseHandler` in `src/snakestream/type.py` to
      `Callable[[], Awaitable[None] | None]`, placing it so its kinship with
      `Consumer[T]` is visible (design.md decision 1). Verify
      `uv run ty check src` passes and `uv run pytest tests/test_close.py`
      is unchanged — the widening alone must be behaviour-neutral
- [x] 2.2 Add a `tests/test_close.py` case registering an `async def` handler via
      `on_close()` and asserting it registers, returns the same stream instance,
      and raises nothing at registration time (`stream-close-handling`,
      "An async handler registers exactly as a sync one does"). Verify it passes

## 3. `close()` refuses an awaitable handler

- [x] 3.1 Extract the failure tail of `Stream.close()` — first-exception-wins
      plus one note per later exception — into a private module-level helper in
      `stream.py` taking the collected exceptions (design.md decision 5). Verify
      the six existing `test_close.py` failure tests pass unmodified
- [x] 3.2 Raise `StreamBuildException` from **inside** `close()`'s existing
      per-handler `try:` for a handler classified async by
      `callable_dispatch.is_async_callable()` (before calling it) or whose
      result `isawaitable()` (after calling it). The message must name the
      handler and point at `aclose()`/`async with`, and must not claim the
      resource is untouched. Verify no `RuntimeWarning: coroutine ... was never
      awaited` is emitted — run with `-W error::RuntimeWarning`
- [x] 3.3 Cover the five `close()` refusal scenarios from
      `stream-close-handling`: the plain refusal, `[sync_a, async_b, sync_c]`
      (both sync handlers still invoked), `[bad, async_b]` (bad's exception
      raised, carrying a note for the refusal), the plain-`def`-returning-a-
      coroutine case (handler called, then refused), and the same refusal raised
      both inside and outside a running event loop. Verify all pass
- [x] 3.4 Confirm no event loop is created or reached for on the refusal path —
      grep the changed lines for `asyncio.run`/`get_event_loop`/`new_event_loop`
      and confirm none appear (design.md decision 2 rules the whole approach out,
      not just one spelling of it)

## 4. `aclose()`

- [x] 4.1 Add `async def aclose()` to `Stream`: walk the same
      `_close_handlers` list in registration order, one at a time, awaiting a
      result that `isawaitable()`, collecting failures, and raising through the
      helper from 3.1. It must not touch `self._stream` and must not call
      `_check_not_consumed()` (design.md decision 5). Verify
      `uv run ty check src` passes
- [x] 4.2 Give `aclose()` the docstring that states the shared rules — order,
      one-at-a-time, the failure contract, handlers-only — and have `close()`'s
      docstring point at it rather than restate them, following
      `sequential()`/`parallel()`'s precedent (design.md — Risks, last entry)
- [x] 4.3 Cover the `aclose()` scenarios in a new `tests/test_aclose.py`: empty
      handler list, an async handler run to completion, sync-only handlers
      behaving as under `close()`, `[sync_a, async_b, sync_c]` in order, and a
      consumed reference still closeable. Verify all pass
- [x] 4.4 Cover the sequencing requirement specifically: two async handlers where
      the first suspends (`asyncio.sleep(0)` plus a shared list recording
      entry/exit), asserting the second is not entered until the first has
      exited — the test that fails if anyone reaches for `asyncio.gather`
- [x] 4.5 Cover the `aclose()` failure scenarios: `[bad, good]`, an async handler
      raising after suspending, and three mixed failures producing one note per
      later failure in encounter order. Verify all pass
- [x] 4.6 Cover "aclose() leaves the source alone": `aclose()` on a stream over
      an unconsumed async generator, then assert the source was neither advanced
      nor closed and the stream still consumes normally

## 5. The asynchronous context manager

- [x] 5.1 Add `__aenter__` (returns `self`) and `__aexit__` (awaits `aclose()`,
      returns `None`) to `Stream`, beside the existing `__enter__`/`__exit__`,
      with docstrings mirroring theirs. Verify `uv run ty check src` passes.
      **Note:** `__aenter__` must itself be `async def` — `async with` requires
      the value it returns to be awaitable, unlike `__enter__`
- [x] 5.2 Cover the `python-data-model` async-context-manager scenarios in
      `tests/test_data_model.py`: handler runs on exit, `__aenter__` returns the
      stream itself, handlers run when the block raises and the exception is not
      suppressed, sync handlers work under `async with`, three mixed failures
      propagate the first with notes, an extended reference may still be entered,
      and the stream is consumable inside the block
- [x] 5.3 Add the one new synchronous scenario — a stream carrying an async
      handler used under `with` is refused at block exit on `close()`'s terms —
      which is what pins that `__exit__` delegates rather than restates
- [x] 5.4 Verify `contextlib.aclosing(stream)` works, mirroring the existing
      `contextlib.closing(stream)` usage, with a test asserting the handler ran

## 6. Close the source-slot collision

- [x] 6.1 Unwrap a `Stream` source in `stream.py`'s `_accept()` to
      `source.iterator()`, so the source slot holds an iteration and never a
      stream (design.md decision 3). Verify group 1's tests still pass — they
      are the regression gate for this task.
      **Note:** this also fixed the crash found at task 1.1 (see design.md's
      "Correction found during task 1.1") — `_accept()` no longer returns a
      `Stream`, so `_accept(source) or _normalize(source)` never triggers
      `Stream.__bool__`
- [x] 6.2 Confirm the timing shift the design accepts: `Stream(already_consumed)`
      now raises `IllegalStateException` at construction rather than at
      consumption. Add a test asserting the construction-time raise, and check
      whether any existing test in `tests/` depended on the later timing — if one
      does, report it rather than silently updating it.
      **Checked:** no existing test constructs `Stream(other_stream_instance)`,
      so none depended on the old timing
- [x] 6.3 Confirm the unwrap did not disturb `_estimate_size()`, which walks the
      same branches: a `Stream` source is an async source and must still report
      no size hint. Verify `uv run pytest tests/test_spliterator.py` passes
- [x] 6.4 Run the full suite and confirm nothing else relied on a `Stream`
      sitting raw in the source slot: `uv run pytest`

## 7. Documentation

- [x] 7.1 Update `README.md`'s data-model and close-handling entries with
      `aclose()`, `__aenter__`/`__aexit__`, and the widened handler contract.
      No Migration entry — the alias widens, the members are additive, and
      `close()`'s behaviour over handlers it accepts today is untouched. Verify
      by re-reading the Migration log's stated criterion and confirming this
      change does not meet it
- [x] 7.2 Update `CLAUDE.md`'s AutoClose section: close handlers are no longer
      "plain no-arg callables" without qualification, and `async with` joins
      `with` as an idiom
- [x] 7.3 Verify `uv run ruff format --check .` and `uv run ruff check .` pass
      over the whole tree, docs included

## 8. Roadmap and spec bookkeeping

- [x] 8.1 Edit `roadmap/items/async-with-on-stream.md` in place — no split, no
      bucket change: add `refs.changes = ["async-close-handlers"]`, restate the
      `gate` as what the work still has to clear once this change is scaffolded,
      and record what the analysis corrected (the item treated the source-slot
      question as absent; it is decision 3). Regenerate with
      `python tools/roadmap_index.py` and verify
      `uv run pytest tests/test_roadmap.py` passes
- [x] 8.2 Update `openspec/specs/stream-close-handling/spec.md`'s `## Purpose`
      line, which names only `on_close()`/`close()`, to cover `aclose()` too.
      Edit the main spec directly — a delta's Purpose is ignored for an existing
      capability. Verify `openspec validate async-close-handlers --strict`
      still passes

## 9. Final gate

- [x] 9.1 Run the full check the way CI does on the GIL-enabled leg:
      `uv run pytest --cov-fail-under=98`, `uv run ruff check .`,
      `uv run ruff format --check .`, `uv run ty check src`. Every one must pass.
      98.56% coverage; all pass
- [x] 9.2 Run `uv run --python 3.14t pytest` on the free-threaded leg and
      confirm it passes — group 6 touches source normalization, which every
      execution path goes through. 1170 passed (one unrelated pre-existing
      RuntimeWarning from `test_comparing.py`'s hypothesis-driven test)
- [x] 9.3 Verify `uv run pytest tests/test_name_visibility.py` passes: the
      failure-tail helper from 3.1 is used only inside `stream.py` and must
      therefore carry a leading underscore per the naming rule

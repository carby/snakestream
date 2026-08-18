## Context

Three independent, self-contained defects were found during a review pass (tracked as roadmap.md's **Now** #1). Each lives in a different file, has no shared code path, and no dependents blocking it, so this design covers all three together but each can be implemented and reviewed as an isolated diff.

Current code:

- `BaseStream.close()` (`base_stream.py:80-82`):
  ```python
  def close(self) -> None:
      for close_handler in self._close_handlers:
          close_handler()
  ```
- `Stream.flat_map()` (`stream.py:158-171`): builds `fn`, whose body does
  ```python
  async for i in iterable:
      async for j in flat_mapper(i).collect(to_generator):
          yield j
  ```
  If the outer `fn` generator receives `GeneratorExit` (e.g. a downstream `.limit()` closes it after enough elements) while suspended inside the inner `async for`, the inner generator returned by `flat_mapper(i).collect(to_generator)` is abandoned without `aclose()` ever being called on it.
- `StreamBuilder.build()` (`stream_builder.py:20-21`): `return Stream(self._elements)` passes the live list by reference; `Stream`'s lazy `_normalize()` iterates it at consumption time, so later `add()`/`accept()` calls are visible in the already-built stream.

## Goals / Non-Goals

**Goals:**
- Make `close()` run every handler regardless of earlier failures, and surface failures afterward.
- Make `flat_map()` explicitly close its per-element inner generator when the outer chain is torn down early.
- Make `StreamBuilder.build()` snapshot its elements so post-build `add()`/`accept()` calls can't leak in.

**Non-Goals:**
- Not changing `on_close()`/`close()`'s public signature, or `StreamBuilder`'s public method signatures.
- Not adding `IllegalStateException`-style raise-on-`add()`-after-`build()` (Java's actual contract) — snapshotting is a smaller, equally correct fix, and matches this project's precedent of adapting rather than literally porting Java semantics where a simpler fix satisfies the same observable contract (no post-build mutation leaks in).
- Not touching `ParallelStream`'s `flat_map()` usage — it's inherited unchanged from `Stream`, and the fix lives at that single shared call site.

## Decisions

**`close()`: run every handler, then raise the first captured exception.** Iterate all handlers in a `try`/`except Exception` per handler, collecting failures into a list; after the loop, if any failures occurred, raise the first one. This is a minimal, version-uniform fix matching the requirement ("run every handler regardless, then surface failure") without over-engineering multi-exception reporting.

Alternative considered: `ExceptionGroup` (raising all failures together) — rejected because it's Python 3.11+ only, and this project's CI matrix still targets 3.10.

**`flat_map()`: wrap the inner generator in `contextlib.aclosing()`.**
```python
async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
    async for i in iterable:
        async with aclosing(flat_mapper(i).collect(to_generator)) as inner:
            async for j in inner:
                yield j
```
`aclosing()` guarantees `aclose()` runs on the inner generator whether the `async for` completes normally, raises, or the outer generator itself is torn down via `GeneratorExit` while suspended at the `yield j`. This is the standard-library-idiomatic fix (`contextlib.aclosing`, mirroring `contextlib.closing`) and requires no new dependency.

Alternative considered: manually wrapping in `try`/`finally` calling `.aclose()` — rejected in favor of `aclosing()` since it's the stdlib primitive built for exactly this, already familiar from `contextlib.closing()` used elsewhere in this codebase's docs (`CLAUDE.md` references `contextlib.closing()` for `on_close()`/`close()`).

**Discovered during implementation: `aclosing()` around `flat_mapper(i).collect(to_generator)` alone is not sufficient.** `collect(to_generator)` returns `to_generator(self._compose())` — a second-layer async generator whose body was `async for n in composition: yield n` with no cleanup of its own. Calling `.aclose()` on *that* wrapper (what `flat_map()`'s `aclosing()` closes) throws `GeneratorExit` into `to_generator`'s frame, but plain `async for` does not propagate `.aclose()` to the thing it iterates — confirmed with a minimal repro (a generator closed via `.aclose()` never triggers its upstream's `finally:` block, even after yielding to the event loop). So the inner stream's real composed generator (e.g. a tracked source with `finally:` cleanup) was still abandoned one layer down.

Fixed by also wrapping `to_generator()`'s own `composition` in `aclosing()` (`collector.py`), so closing the `to_generator` wrapper now cascades into closing what it composes:
```python
async def to_generator(composition: AsyncGenerator) -> AsyncGenerator[Any, None]:
    async with aclosing(composition):
        async for n in composition:
            yield n
```
This is the minimal fix that makes `flat_map()`'s `aclosing()` wrapping actually reach the tracked generator in the roadmap item's stated repro case (a single-level inner stream with no further chained ops). It does not fix the general N-layers-deep version of this gap — every op in `stream.py` has the same `async for iterable: yield ...` shape with no `aclose()` propagation of its own — but that's the pre-existing, out-of-scope concern already tracked under the **Next**-bucket Sink-chain redesign item, not something this fix needs to solve.

**`StreamBuilder.build()`: snapshot via `list(self._elements)`.**
```python
def build(self) -> Stream[T]:
    return Stream(list(self._elements))
```
Simplest fix that satisfies the observable contract (post-build mutation doesn't leak). Considered adding a `self._built` flag that raises on further `add()`/`accept()` (closer to Java's actual `IllegalStateException` contract) but rejected as unnecessary scope growth beyond what the roadmap item asks for — the defect is the reference-sharing, not the absence of a raise.

## Risks / Trade-offs

- [`close()` raising only the first handler exception silently drops later handler failures] → acceptable: every handler still *runs* (the actual bug being fixed), only exception *reporting* is single-exception; matches the "no config change needed, minimal fix" precedent already used elsewhere in this project's Done log (e.g. the branch-coverage pragma fix).
- [`aclosing()` changes `flat_map()`'s generator-teardown timing slightly — the inner generator's `finally` blocks now run at abandonment time instead of never] → this is exactly the intended fix; no behavioral risk for correctly-written inner generators, and previously-silent leaks are the bug being fixed.
- [`StreamBuilder.build()`'s snapshot is a **BREAKING** change per `CLAUDE.md`'s migration-log convention] → low risk: relying on post-build mutation leaking into a built stream was never a documented feature, and README's migration log will record it per existing convention.

## Migration Plan

Straightforward code fix, no data migration. Update README's migration log for the `StreamBuilder.build()` behavior change per `CLAUDE.md`'s convention. No feature flag needed — apply directly.

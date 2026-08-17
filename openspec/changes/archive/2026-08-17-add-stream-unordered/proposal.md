## Why

Java's `BaseStream.unordered()` lets a caller declare that encounter order
doesn't matter for a pipeline, which the runtime can then use to pick cheaper
execution strategies. Snakestream has no equivalent yet, and the roadmap
(`roadmap.md` Now #2) calls it out as a prerequisite: the disabled
`find_first()` stub in `stream.py` (commented out because "until we have
ordered parallel stream then we cant do this one") and the planned
`forEachOrdered()` both need a way to know whether a given stream has
explicitly opted out of ordering guarantees before their semantics can be
defined.

## What Changes

- Add `BaseStream.unordered()` — marks the stream instance as not
  order-dependent and returns `self`, consistent with the existing
  chain-of-closures mutation model (`.filter()`/`.map()`/etc. all mutate and
  return `self` rather than a new instance).
- Add `BaseStream.is_ordered()` — reports the current ordering flag, mirroring
  the existing `is_parallel()` query method.
- Propagate the ordering flag across `.sequential()`/`.parallel()` mode
  switches, since both construct a fresh `Stream`/`ParallelStream` instance
  from the composed source (`base_stream.py`'s `sequential()`/`parallel()`).
- No change to actual iteration/execution behavior in this change — `Stream`
  already preserves encounter order and `ParallelStream` already does not
  (per `CLAUDE.md`); `unordered()` only records intent for later consumers
  (`forEachOrdered()`, `find_first()`) to act on.

## Capabilities

### New Capabilities
- `stream-ordering`: tracks and exposes whether a stream instance has been
  marked unordered via `BaseStream.unordered()`/`is_ordered()`, and how that
  flag propagates across `.sequential()`/`.parallel()`.

### Modified Capabilities
(none — no existing capability's requirements change)

## Impact

- `src/snakestream/base_stream.py`: new `_ordered` instance state,
  `unordered()`/`is_ordered()` methods, propagation in `sequential()`/
  `parallel()`.
- No changes to `stream.py`/`parallel_stream.py` iteration logic.
- New tests covering: default-ordered state, `unordered()` mutation and
  chaining (returns `self`), flag propagation across `.sequential()`/
  `.parallel()` mode switches, and independence across separate `Stream`
  instances.
- README's public API section gets a new `unordered()`/`is_ordered()` entry
  under `BaseStream`, and the roadmap's Now #2 checkbox moves toward Done.

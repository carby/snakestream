## Why

`collect(to_generator)` is a second spelling of `iterator()`. `Stream.collect()`
implements it as `collector(self.iterator())`, and the `StreamingCollector` it
unwraps holds `_stream`, a generator that re-yields its argument under
`maybe_aclosing`. Every element therefore crosses one extra generator layer for
a teardown guarantee `iterator()` already gives: `_stream_through()` wraps its
source in `maybe_aclosing` (`execution.py:124`), as do both fork-join paths
(`:297`, `:458`), and the outer wrapper is itself only closed when the caller
closes it - exactly the condition under which it would close the composition.
Measured on a 200k-element `.map()` pipeline, best of five: `iterator()` 878
ns/element, `collect(to_generator)` 1146 ns/element, **+31%** for the layer.

The cost is not only per-element. `to_generator` has no Java counterpart -
Java's answer to "give me a lazy handle" is `stream.iterator()`, which this
library already has - so it is an invented name that buys a duplicate spelling,
and it forces a documented exception into `Stream.collect()`'s overload set and
dispatch, and into six specs. The library has already voted against it
internally: `pipeline-composition` requires `flat_map` to iterate the inner
stream's own composition "rather than through a `collect(to_generator)`
wrapper, so there is a single generator layer to close" - the fix for a real
leak.

Roadmap item `to-generator-as-a-factory` proposed making `to_generator` a
factory so `collect(to_generator())` matches every other collector's call
shape. That fixes the harmless asymmetry (missing parens) and leaves the
harmful one (the return value is an `AsyncGenerator`, not something to
`await`) - arguably worsening it, since the call site would then look
identical to `collect(to_list())` while behaving differently. Deleting the
exception removes both.

## What Changes

- **BREAKING**: `to_generator` and `StreamingCollector` are removed from
  `snakestream.collector`. `collect(to_generator)` becomes `iterator()`, and
  `async for x in stream:` covers the common case through `__aiter__` with no
  import at all. The break is loud and at import time (`ImportError`), before
  any stream is built; there is no shim.
- **BREAKING**: `Stream.collect()` accepts only a `Collector` or the
  three-argument supplier/accumulator/combiner form. Its `StreamingCollector`
  overload, `isinstance` branch and the "or to_generator for a lazy, streaming
  result" clause of its `StreamBuildException` message all go.
- `collector.py` holds the protocol and nothing else - `Collector`,
  `CollectorSink`, `Characteristics` - with no instances and no functions. Its
  import of `maybe_aclosing` existed solely for `_stream`, so the module's last
  dependency edge onto `execution.py` drops with it.
- Six specs lose the exception they carry for `to_generator`. One of them,
  `pipeline-composition`'s `flat_map` requirement, gets *simpler*: it can state
  the single-layer rule directly instead of contrasting against a wrapper that
  no longer exists.
- README's quickstart, API table and Collectors section, and CLAUDE.md's
  Collectors paragraph, all drop "the one exception" prose. A README Migration
  entry lands in the same commit.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `collector-protocol`: removes the requirement "`to_generator` is the one
  non-`Collector` collector" and its three scenarios; restates what `collect()`
  rejects now that there is no non-`Collector` argument.
- `terminal-sinks`: drops `collect(to_generator)` from the operations that use
  the executor's element-producing form, and the scenario asserting it still
  composes through the bridge.
- `stream-iterator`: drops `collect(to_generator)` as a second way to reach the
  same generator, and the scenario pinning the two together.
- `stream-execution-model`: drops `collect(to_generator)` from the list of
  operations that compose through the bridge.
- `racing-encounter-order`: drops `collect(to_generator)` from the operations
  that observe delivery order; `iterator()` alone carries it.
- `pipeline-composition`: restates `flat_map`'s single-generator-layer
  requirement without the `collect(to_generator)` contrast.

## Impact

- **Public API**: `snakestream.collector.to_generator` and
  `snakestream.collector.StreamingCollector` are removed. Callers migrate
  `.collect(to_generator)` to `.iterator()`. Nothing else about `collect()` or
  about any `Collector` changes.
- **Code**: `src/snakestream/collector.py`, `src/snakestream/stream.py`.
- **Tests**: 42 call sites across nine files migrate to `.iterator()`. Two in
  `tests/test_collect.py` call `to_generator(source)` directly as a standalone
  adapter and are deleted rather than migrated - one of them
  (`test_to_generator_no_aclose_on_source`) is a coverage path for
  `maybe_aclosing`'s no-`aclose()` branch, which has to be confirmed still
  covered against the 98% gate.
- **Docs**: README quickstart, API table, Collectors section, Migration log;
  CLAUDE.md's Collectors paragraph.
- **Roadmap**: `to-generator-as-a-factory` is superseded by this change and
  edited in place - it stays queued until the work lands.

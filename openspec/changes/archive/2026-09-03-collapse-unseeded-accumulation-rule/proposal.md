## Why

One rule — *an accumulation that never saw an element finishes as `None`* — is
written out five times, and no one of the five references any other:

| Site | Body |
|---|---|
| `terminals.py` `_ReduceSink._finish` | `None if container is _UNSET else container` |
| `terminals.py` `_MinMaxSink._finish` | `None if container is _UNSET else container` |
| `terminals.py` `_FindSink._finish` | `None if container is _UNSET else container` |
| `collectors.py` `_extremum()._finish` | `None if container.found is _UNSET else container.found` |
| `collectors.py` `reducing()._finish` | `None if container.acc is _UNSET else container.acc` |

The sentinel they all read already lives in `sink.py` *precisely because* both
modules need it and neither may import the other — so the rule's home is
already built and only the rule is missing from it.

Two of the three sinks additionally share a second hook: `_MinMaxSink` and
`_FindSink` have byte-identical `_create_container()` bodies returning `_UNSET`.
So the duplication is a shared *shape* — "a terminal that starts with no value"
— not just a shared expression, and naming the shape is what collapses both
hooks at once.

**Why now, and why this one.** Every other literal duplication left in `src/`
sits on the per-element path, where **Done** records five consecutive measured
rejections (`add-callsite-dispatch`, `collapse-terminal-collector-duplication`,
the flush dedup, the `merge()` generator, `asyncio.Semaphore`). A `_finish`
runs **once per collection**, so the `+10% ns/element` threshold that governs
that neighbourhood does not apply here at all — the same exemption
`collapse-sort-decorate-lanes` claimed and used. This is the last structural
cleanup in the repository that provably costs nothing, which is the whole of
its case. Filed on the roadmap as **Now**, item 1 of the
`sort-mixed-lane-by-successive-passes` read (2026-09-02), and already checked
against **Done**: it re-proposes nothing in the rejection log.

## What Changes

- **`sink.py` gains `_unseeded(container)`**, the single statement of the rule,
  beside the `_UNSET` it reads. Not a thin wrapper around a check-and-raise —
  it is a *rule with a name*, and the name is what the five sites are missing.
- **`sink.py` gains `_UnseededSink`**, a `TerminalSink` subclass that supplies
  `_create_container() -> _UNSET` and `_finish() -> _unseeded(container)`.
- **`_MinMaxSink` and `_FindSink` derive from it** and delete both overrides.
  **`_ReduceSink` derives from it** and deletes `_finish` only — it keeps its
  own `_create_container()`, which returns the caller's identity.
- **`collectors.py`'s `_extremum()` and `reducing()` call `_unseeded()`** on
  their box field instead of restating the comparison.
- **`terminals.py`'s `_ReduceSink` docstring** loses its "implemented twice"
  hedge for the empty-finishes-as-`None` half: that half stops being duplicated
  here even though the `_UNSET`-seed *fold* stays duplicated in `reducing()`
  for the measured reason that docstring records. The pointer to `reducing()`
  stays; what it warns about narrows.

Explicitly **not** in scope: the `_UNSET`-seed rule inside `accept()`, which
`_ReduceSink` and `reducing()` genuinely do implement twice on measurement
(+70%, `collapse-terminal-collector-duplication`). Only the *finish* half
collapses.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. `skip_specs: true`.

No requirement changes and no observable behaviour changes. The rule being
collapsed is already specified where callers can see it —
`reduce-without-identity`, `collector-min-max`, `collector-reducing` and
`stream-find-first` each state their own empty-source result — and this change
alters none of them. `sink-protocol`'s "A terminal sink over an empty source
returns its empty container" is likewise untouched: `_UnseededSink`'s empty
container *is* `_UNSET`, and finishing it to `None` is what those four
capabilities already require. Per the artifact instruction, specs describe
behaviour, so a change with no behaviour delta gets no delta spec.

## Impact

- **Code:** `src/snakestream/sink.py` (two additions), `terminals.py` (three
  sinks lose four method bodies), `collectors.py` (two `_finish` closures
  become one-line calls).
- **Tests:** none expected to change. The five sites are private and reached
  only through public terminals whose results are unchanged; nothing in
  `tests/` references `_finish`, `_create_container` or `_UNSET` by name — to
  be confirmed as task 1 rather than assumed.
- **Public API:** none. Every new name is underscore-private and unexported.
- **Performance:** one added attribute lookup and one call per *collection*,
  on a path that runs once per terminal. No per-element path is touched, so no
  benchmark gates this change; see design.md for why that claim is structural
  rather than measured.
- **Docs:** `CLAUDE.md` needs no edit — it does not describe `_finish`. The
  roadmap's **Now** entry for this item is removed at archive.

## Context

`collector.py` holds plain `async def` functions that take the composed
`AsyncGenerator` and consume/transform it (`CLAUDE.md`: "Collectors are just
async generator consumers", no separate Collector class hierarchy). `to_list`
and `to_generator` are both zero-argument collectors passed directly as
`collect(to_list)`. Java's `Collectors.joining()` family is a *factory*:
`Collectors.joining(delimiter, prefix, suffix)` returns a `Collector`
configured with those three strings, rather than being a collector itself.
This is the first collector in this codebase that needs configuration, so
the design question is how a parameterized collector fits the existing
"collector = plain async function" shape.

## Goals / Non-Goals

**Goals:**
- Support all three Java overloads — `joining()`, `joining(delimiter)`,
  `joining(delimiter, prefix, suffix)` — via one Python function with default
  arguments, not three separate names or `@overload`.
- Keep the "collector is an `async def(AsyncGenerator) -> R`" contract
  intact: `joining(...)` returns such a function; it does not itself consume
  anything.
- Match Java's `TypeError`-on-non-`str` behavior (Java: compile error on
  `Stream<CharSequence>`; Python has no compile-time equivalent, so this
  surfaces as a runtime `TypeError`).

**Non-Goals:**
- No implicit `str()` coercion of non-string elements — Java's `joining()` is
  only defined for `CharSequence` streams, and silently stringifying
  arbitrary objects (e.g. `None` → `"None"`) is a different, unrequested
  feature.
- No changes to `to_list`/`to_generator` or to `Stream.collect()` itself —
  `joining()` fits the existing `collect(collector)` single-arg form as-is.

## Decisions

- **`joining()` is a factory function, not a collector itself.** It returns a
  closure `async def _join(composition: AsyncGenerator[str, None]) -> str`
  that captures `delimiter`/`prefix`/`suffix` from the enclosing scope. This
  is the natural Python shape for "a function configured with arguments that
  returns another function," and requires no new abstraction beyond what
  `collector.py` already has (plain async functions matching the
  `Callable[[AsyncGenerator[T, None]], R]` shape `collect()` expects).
  Alternative considered: a callable class (`Joining(delimiter, prefix,
  suffix)` with `__call__`) — rejected as unnecessary machinery for a single
  captured-closure use case, and inconsistent with `collector.py`'s existing
  plain-function style (unlike `stream.py`'s `_DistinctOp`/`_LimitOp`
  classes, which exist specifically to hold *per-composition* state across
  parallel branches — `joining()`'s prefix/delimiter/suffix are fixed at
  factory-call time, not per-composition state).
- **All three Java overloads collapse to one function with defaults:**
  `joining(delimiter: str = "", prefix: str = "", suffix: str = "")`. Matches
  how this codebase already prefers default arguments over `@overload` for
  optional-parameter variance where the underlying behavior doesn't actually
  branch (contrast with `collect()`'s two truly different code paths, which
  do use `@overload`).
- **Non-`str` elements raise `TypeError`.** The join loop uses `"".join()`
  semantics via incremental concatenation, so a non-`str` element naturally
  raises `TypeError` from `str.join`/`+`-style concatenation — no explicit
  `isinstance` check needed; the error just needs to not be masked or
  swallowed.
- **Empty stream returns `prefix + suffix`.** Matches Java's
  `Collectors.joining()` Javadoc exactly (no elements → delimiter never
  used, prefix/suffix still applied).
- **New README `Collectors` section.** No such section exists yet since
  `to_list`/`to_generator` predate the `Collectors`-parity effort in
  roadmap.md. Adding one now, in the same table format as the existing
  `Stream` table, gives `counting()`, `toMap()`, `groupingBy()`, etc.
  (roadmap.md **Now** #2-5) a consistent place to land without a later
  unrelated documentation-structure change.

## Risks / Trade-offs

- [Risk] `TypeError` on non-`str` elements is a runtime-only guard (no
  static enforcement that the stream is `Stream[str]`) → Mitigation:
  accepted; this matches the existing project posture (e.g. the
  `Comparator` `TypeError` guard in `sort.py`) of enforcing element-shape
  contracts at collection time rather than via typing alone, and `ty`
  already flags `Stream[int]` piped into a `Callable[[AsyncGenerator[str,
  None]], str]`-typed collector if the caller's stream is properly typed.

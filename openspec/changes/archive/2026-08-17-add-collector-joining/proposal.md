## Why

`collector.py` currently only offers `to_list`/`to_generator` — general-purpose
sinks with no string-specific behavior. Java's `Collectors.joining()` /
`joining(delimiter)` / `joining(delimiter, prefix, suffix)` are the simplest
of the not-yet-implemented `Collectors` statics (roadmap.md's **Now** #1: a
single accumulating string, no map/set/grouping structure) and establish the
shape (a factory function returning a `collect()`-compatible collector) that
later `Collectors` work (`counting()`, `toMap()`, `groupingBy()`, ...) will
build on.

## What Changes

- Add `joining()`, `joining(delimiter)`, and `joining(delimiter, prefix,
  suffix)` to `collector.py` — a single `joining(delimiter="", prefix="",
  suffix="")` factory function (matching Java's three overloads via default
  arguments, the same pattern already used elsewhere in this codebase rather
  than introducing `@overload`s for a factory) that returns an `async def`
  collector consuming an `AsyncGenerator[str, None]` and returning a `str`.
- Elements must already be `str`; a non-`str` element raises `TypeError`,
  matching Java's `Collectors.joining()`, which is only defined on
  `Stream<CharSequence>`.
- Add a `Collectors` section to README's API table (none exists yet) so this
  and future `Collectors`-family additions (`counting()`, `toMap()`, etc.)
  have a place to be tracked, matching how `Stream` methods are already
  tracked.
- Not breaking: purely additive, new top-level function in `collector.py`.

## Capabilities

### New Capabilities
- `collector-joining`: string-concatenation collector (`joining()` /
  `joining(delimiter)` / `joining(delimiter, prefix, suffix)`) for use with
  `Stream.collect()`.

### Modified Capabilities
(none)

## Impact

- `collector.py`: new `joining()` function.
- `README.md`: new `Collectors` table section, one row.
- `roadmap.md`: move item #1 to **Done** once implemented.
- New `tests/test_joining.py`.

+++
id = "joining-collector"
title = "Added `joining()`"
filed = 2026-08-17
closed = 2026-08-17
outcome = "shipped"
+++

Added `joining()` / `joining(delimiter)` / `joining(delimiter, prefix,
suffix)` (`collector.py`) — a string-concatenation collector for use with
`Stream.collect()`, `collector.py`'s equivalent of `Collectors.joining`
and the first entry in the `Collectors`-parity effort tracked by this
roadmap. Implemented as a single `joining(delimiter: str = "", prefix:
str = "", suffix: str = "")` factory function, collapsing Java's three
overloads into default arguments rather than `@overload`s, since the
underlying behavior doesn't actually branch by argument count (contrast
with `collect()`'s two genuinely different code paths, which do use
`@overload`). It returns a plain `async def` closure over the composed
`AsyncGenerator[str, None]`, matching `collector.py`'s existing
plain-function collector shape (`to_list`/`to_generator`) rather than a
callable class — no per-composition state is needed since
prefix/delimiter/suffix are fixed at factory-call time. The join uses
`delimiter.join(parts)`, so a non-`str` element naturally raises
`TypeError` (matching Java's `Collectors.joining()`, defined only on
`Stream<CharSequence>`) with no explicit `isinstance` check needed; an
empty stream returns `prefix + suffix`, matching Java's Javadoc exactly.
Added a new `Collectors` table section to README (none existed yet) to
give this and future `Collectors`-family additions a place to be
tracked. Added `tests/test_joining.py`: no-arg join, delimiter-only,
delimiter+prefix+suffix, single-element (no delimiter applied), empty
stream with and without prefix/suffix, and the `TypeError` regression for
a non-`str` element. No breaking changes. See
`openspec/changes/add-collector-joining`.

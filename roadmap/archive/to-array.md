+++
id = "to-array"
title = "Added `Stream.to_array()`"
filed = 2026-08-17
closed = 2026-08-17
outcome = "shipped"
+++

Added `Stream.to_array()` (`stream.py`) — a terminal operation returning a
`list` of every element pulled through the composed chain, functionally
identical to `collect(to_list)`. Java's `toArray()`/`toArray(generator)`
exist because arrays are a distinct, reified type from `List` and Java has
no runtime generic-array construction; neither motivation applies to
Python, where `list` is already the general-purpose ordered collection, so
only the no-arg form was added — implemented as `to_array()` (snake_case),
matching every other Java-name adaptation already in the class
(`for_each`, `find_any`, `flat_map`), not the literal Java casing. The
`toArray(generator)` overload was decided against and is documented in
README as intentionally skipped rather than tracked as future work. Added
`tests/test_to_array.py`: non-empty and empty streams, equivalence with
`collect(to_list)`, `ParallelStream` coverage, and a `TypeError` regression
for calling it with an argument. Updated README's parity table and
removed the item from its "Left to do" list. No breaking changes. See
`openspec/changes/add-stream-toarray`.

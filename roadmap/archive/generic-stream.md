+++
id = "generic-stream"
title = "Made `Stream` generic"
filed = 2026-08-12
closed = 2026-08-12
outcome = "shipped"
+++

Made `Stream` generic (`Stream[T]`): `BaseStream`/`Stream`/`ParallelStream` were
plain classes, so the `T`/`R` in their method signatures were unbound
`TypeVar`s and element types were `Unknown` end to end — `ty` accepted
`Stream.of([1,2,3]).map(lambda s: s.upper())` without complaint despite
`int` having no `.upper()`. Fixed by making `BaseStream`/`Stream`/
`ParallelStream` `Generic[T]`; `map()`/`flat_map()` now return `Stream[R]`
via a narrowly-scoped `cast(Stream[R], self)` since the chain-of-closures
model mutates and returns the same `self` rather than a new instance
(deliberately not revisiting the separate mutable-builder-vs-immutable-
pipeline decision below); type-preserving ops (`filter`, `distinct`,
`peek`, `limit`, `sorted`) return `Stream[T]` directly; terminal ops are
typed against the stream's bound `T`. Also fixed `type.py`'s `FlatMapper`
alias, which hardcoded an unparameterized `Stream` instead of `Stream[R]`,
and `StreamBuilder.build()`, which dropped its already-declared `T`
instead of returning `Stream[T]`. Typing-only change, no runtime behavior
differs. Added `tests/test_static_typing.py` plus `tests/typing/`
fixtures that shell out to `ty check` to regression-test that the
motivating bug is now caught and that valid generic usage still
type-checks cleanly. See `openspec/changes/make-stream-generic`.

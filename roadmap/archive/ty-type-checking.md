+++
id = "ty-type-checking"
title = "Added static type checking to CI with `ty`"
filed = 2026-08-10
closed = 2026-08-10
outcome = "shipped"
+++

Added static type checking to CI using `ty`, Astral's newer Rust-based
type checker — chosen over `mypy`/`pyright` since it fit the existing
`uv`/`ruff` toolchain and handled the codebase's `Awaitable`-union type
aliases without issue. Fixed the 6 genuine type errors it surfaced
(`BaseStream.on_close`'s return type, `ParallelStream`'s task-list
typing, `StreamBuilder`'s unbound `TypeVar`, `Stream.collect`'s generic
return type, and `Stream._min_max`'s sentinel-return typing), plus one
scoped `ty: ignore` for a case the checker can't narrow via the
runtime `iscoroutinefunction()` check in `Stream.sorted`. Gated to the
3.14 matrix leg only, matching the coverage-gate precedent.

## Why

`BaseStream`/`Stream`/`ParallelStream` are plain (non-generic) classes, so the `T`/`R` type variables referenced throughout their method signatures are unbound and the element type flowing through a pipeline is `Unknown` to the type checker end to end. `ty` accepts `out: list[int] = await Stream.of([1,2,3]).map(lambda s: s.upper()).collect(to_list)` without complaint, even though `int` has no `.upper()`. This is a real gap: `type.py`'s `Mapper`/`Predicate`/`Comparator`/etc. aliases do check a callable's own signature correctly, so half the typing contract already works — the element type is the missing half, and it's the half that would have caught this class of bug statically.

## What Changes

- `BaseStream`, `Stream`, and `ParallelStream` become `Generic[T]`, parameterized by the stream's current element type.
- Intermediate operations that change element type (`map`, `flat_map`) are typed to return `Stream[R]` given a `Mapper[T, R]`/`FlatMapper[T, R]`; operations that preserve element type (`filter`, `distinct`, `peek`, `limit`, `sorted`) are typed to return `Stream[T]`.
- Terminal operations are typed against the stream's `T`: `collect(Callable[[AsyncGenerator[T]], R]) -> R`, `reduce`, `for_each(Consumer[T])`, `find_any() -> T`, `min`/`max`, `all_match`/`any_match`/`none_match(Predicate[T])`, `count`.
- `StreamBuilder[T].build()` is fixed to return `Stream[T]` instead of a bare (unparameterized) `Stream`, closing the gap where the generic parameter was already declared but dropped at the one place it should have been threaded through.
- No behavior changes at runtime — this is a typing-only change. Method bodies are untouched; only signatures/class declarations gain type parameters.

## Capabilities

### New Capabilities
- `generic-stream-typing`: element-type parameterization (`Stream[T]`) flowing correctly through intermediate and terminal operations, verified by `ty`.

### Modified Capabilities
(none — `static-type-checking` already requires CI to run `ty` and fail on type errors; this change doesn't alter that requirement, it just gives `ty` a real element-type contract to check)

## Impact

- `src/snakestream/base_stream.py` — `BaseStream` becomes `Generic[T]`.
- `src/snakestream/stream.py` — `Stream` becomes `Generic[T]`; every intermediate/terminal method signature gains `T`/`R` parameterization.
- `src/snakestream/parallel_stream.py` — `ParallelStream` inherits the generic parameter from `Stream`.
- `src/snakestream/stream_builder.py` — `StreamBuilder.build()` return type fixed to `Stream[T]`.
- `src/snakestream/type.py` — no alias changes expected; existing `Mapper`/`FlatMapper`/etc. aliases already carry `T`/`R`.
- No test behavior changes expected (runtime is untouched), but `ty` should newly catch element-type mismatches that previously passed silently — worth a small negative-case check (e.g. a `.map()` misuse) to confirm the gap is actually closed.

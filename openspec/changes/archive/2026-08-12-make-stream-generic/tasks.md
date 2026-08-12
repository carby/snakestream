## 1. BaseStream

- [x] 1.1 Make `BaseStream` inherit `Generic[T]` (`base_stream.py`); type `self._stream: AsyncGenerator[T]` and `_accept`/`_normalize` accordingly where practical without changing behavior.
- [x] 1.2 Type `sequential()`/`parallel()` to return `Stream[T]`/`ParallelStream[T]`.
- [x] 1.3 Type `on_close()` to return `BaseStream[T]`.

## 2. Stream

- [x] 2.1 Make `Stream` inherit `Generic[T]` via `BaseStream[T]` (`stream.py`).
- [x] 2.2 Type `filter`, `distinct`, `peek`, `limit`, `sorted` to return `Stream[T]` (element-type-preserving).
- [x] 2.3 Type `map(mapper: Mapper[T, R]) -> Stream[R]` and `flat_map(flat_mapper: FlatMapper[T, R]) -> Stream[R]`, each returning `cast(Stream[R], self)` per design.md decision 2.
- [x] 2.4 Type static constructors `of`, `empty`, `concat`, `iterate` to infer/declare `Stream[T]` from their arguments.
- [x] 2.5 Type `builder() -> StreamBuilder[T]` if inferable, else leave as documented limitation.
- [x] 2.6 Type terminal ops (`collect`, `reduce`, `for_each`, `find_any`, `min`, `max`, `_min_max`, `_match`, `all_match`, `any_match`, `none_match`, `count`) against the stream's bound `T`.

## 3. ParallelStream

- [x] 3.1 Make `ParallelStream` inherit `Stream[T]` (`parallel_stream.py`); confirm the type parameter flows through without redeclaration.
- [x] 3.2 Type `_compose`/`_parallel` internals only as far as needed to keep `ty` clean — no public signature changes expected beyond inherited ones.

## 4. StreamBuilder

- [x] 4.1 Fix `StreamBuilder.build()` to return `Stream[T]` instead of bare `Stream` (`stream_builder.py`).

## 5. Verification

- [x] 5.1 Run `uv run ty check src` and fix any newly-surfaced type errors.
- [x] 5.2 Added `tests/typing/bad_stream_map.py` (intentional `int.upper()` misuse) and `tests/typing/good_stream_types.py` (valid `map`/`filter`/`StreamBuilder.build()` usage), plus `tests/test_static_typing.py`, which shells out to `ty check` against each fixture and asserts the bad one fails with `unresolved-attribute` and the good one passes cleanly — a permanent regression test, not just a scratch check, closing the gap from proposal.md's motivating example.
- [x] 5.3 Run `uv run pytest` to confirm no runtime behavior changed.
- [x] 5.4 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 5.5 Update README.md's parity/typing notes if it references the unbound-`TypeVar` gap this change closes. (No such section exists in README.md — nothing to update.)

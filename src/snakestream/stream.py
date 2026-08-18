from __future__ import annotations

from contextlib import aclosing
from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Any, cast, overload
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator

from snakestream.base_stream import BaseStream
from snakestream.callable_dispatch import _maybe_await
from snakestream.collector import to_generator, to_list
from snakestream.exception import StreamBuildException
from snakestream.sort import check_comparator_result_type, merge_sort
from snakestream.type import (
    R,
    T,
    Accumulator,
    BiConsumer,
    BinaryOperator,
    CloseHandler,
    Comparator,
    Consumer,
    FlatMapper,
    Mapper,
    Predicate,
    Supplier,
)


if TYPE_CHECKING:
    from snakestream.stream_builder import StreamBuilder


PROCESSES: int = 4
_UNSET = object()


async def _concat(a: Stream, b: Stream) -> AsyncGenerator:
    async for i in a._compose():
        yield i
    async for j in b._compose():
        yield j


class _DistinctOp:
    def make_state(self) -> set:
        return set()

    async def __call__(self, iterable: AsyncGenerator, seen: set | None = None) -> AsyncGenerator:
        if seen is None:
            seen = self.make_state()
        async for i in iterable:
            if i in seen:
                continue
            else:
                seen.add(i)
                yield i


class _LimitOp:
    def __init__(self, max_size: int) -> None:
        self._max_size = max_size

    def make_state(self) -> list[int]:
        return [0]

    async def __call__(self, iterable: AsyncGenerator, size_holder: list[int] | None = None) -> AsyncGenerator:
        if size_holder is None:
            size_holder = self.make_state()
        while True:
            if size_holder[0] >= self._max_size:
                await iterable.aclose()
                return
            # reserve the slot before pulling: a genuinely async upstream
            # can cede control during the pull, so checking and reserving
            # must be atomic (no await between them) to stay correct across
            # racing branches sharing size_holder
            size_holder[0] += 1
            try:
                i = await anext(iterable)
            except StopAsyncIteration:
                return
            yield i


class _SkipOp:
    def __init__(self, n: int) -> None:
        self._n = n

    def make_state(self) -> list[int]:
        return [0]

    async def __call__(self, iterable: AsyncGenerator, skipped_holder: list[int] | None = None) -> AsyncGenerator:
        if skipped_holder is None:
            skipped_holder = self.make_state()
        while skipped_holder[0] < self._n:
            try:
                await anext(iterable)
            except StopAsyncIteration:
                return
            skipped_holder[0] += 1
        async for i in iterable:
            yield i


class Stream(BaseStream[T]):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        super().__init__(source, close_handlers)

    @staticmethod
    def of(*args: T) -> Stream[T]:
        if len(args) == 1:
            return Stream(args[0])
        return Stream(list(args))

    @staticmethod
    def empty() -> Stream[Any]:
        return Stream([])

    @staticmethod
    async def concat(a: Stream[T], b: Stream[T]) -> Stream[T]:
        new_stream = _concat(a, b)
        return Stream(new_stream)

    @staticmethod
    def builder() -> StreamBuilder:
        from snakestream.stream_builder import StreamBuilder

        return StreamBuilder()

    @staticmethod
    def iterate(seed: T, nxt: Callable[[T], T]) -> Stream[T]:
        def _make_iterator(seed: T, nxt: Callable[[T], T]) -> Generator[T, None, None]:
            yield seed
            while True:
                seed = nxt(seed)
                yield seed

        return Stream.of(_make_iterator(seed, nxt))

    # Intermediaries
    def filter(self, predicate: Predicate[T]) -> Stream[T]:
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                keep = await _maybe_await(predicate, i)
                if keep:
                    yield i

        self._chain.append(fn)
        return self

    def map(self, mapper: Mapper[T, R]) -> Stream[R]:
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                yield await _maybe_await(mapper, i)

        self._chain.append(fn)
        return cast("Stream[R]", self)

    def flat_map(self, flat_mapper: FlatMapper[T, R]) -> Stream[R]:
        # Pre-call rejection, not a dispatch site: flat_mapper must return a
        # Stream synchronously, so an async def here is always a caller
        # mistake. This is unrelated to _maybe_await's post-call awaiting.
        if iscoroutinefunction(flat_mapper):
            raise StreamBuildException("flat_map() does not support coroutines")

        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                async with aclosing(flat_mapper(i).collect(to_generator)) as inner:
                    async for j in inner:
                        yield j

        self._chain.append(fn)
        return cast("Stream[R]", self)

    def sorted(self, comparator: Comparator[T] | None = None, reverse=False) -> Stream[T]:
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            # unfortunately I now don't see other way than to block the entire stream
            # how can I otherwise know what is the first item out?
            cache = []
            async for i in iterable:
                cache.append(i)
            # sort
            if comparator is not None:
                # Always merge_sort here rather than list.sort()+cmp_to_key: the
                # comparator may be an async-__call__ object, which needs an await
                # merge_sort's _merge already does. Trades away Timsort's speed for
                # sync comparators; see the add-maybe-await-helper design doc.
                cache = await merge_sort(cache, comparator)
            else:
                cache.sort()
            # unblock the stream
            if reverse:
                for n in reversed(cache):
                    yield n
            else:
                for n in cache:
                    yield n

        self._chain.append(fn)
        return self

    def distinct(self) -> Stream[T]:
        self._chain.append(_DistinctOp())
        return self

    def peek(self, consumer: Consumer[T]) -> Stream[T]:
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                await _maybe_await(consumer, i)
                yield i

        self._chain.append(fn)
        return self

    def limit(self, max_size: int) -> Stream[T]:
        self._chain.append(_LimitOp(max_size))
        return self

    def skip(self, n: int) -> Stream[T]:
        self._chain.append(_SkipOp(n))
        return self

    # Terminals
    @overload
    def collect(self, collector: Callable[[AsyncGenerator[T, None]], R]) -> R: ...

    @overload
    def collect(
        self, supplier: Supplier[R], accumulator: BiConsumer[R, T], combiner: BiConsumer[R, R]
    ) -> Coroutine[Any, Any, R]: ...

    def collect(self, *args: Any) -> Any:
        if len(args) == 1:
            (collector,) = args
            return collector(self._compose())
        # 3-arg mutable reduction: supplier/accumulator, sync or async, are
        # dispatched via _maybe_await like every other user-supplied
        # callable. combiner is accepted for signature parity with Java's
        # Stream.collect(Supplier, BiConsumer, BiConsumer) but is never
        # invoked: collect() always folds over a single composed
        # AsyncGenerator, sequential or parallel, with no independently
        # accumulated partitions to merge - the same posture reduce()
        # already has under .parallel().
        supplier, accumulator, _combiner = args
        return self._collect_mutable(supplier, accumulator)

    async def _collect_mutable(self, supplier: Supplier[R], accumulator: BiConsumer[R, T]) -> R:
        container = await _maybe_await(supplier)
        async for n in self._compose():
            await _maybe_await(accumulator, container, n)
        return container

    @overload
    async def reduce(self, identity: T | R, accumulator: Accumulator[T, R]) -> T | R: ...

    @overload
    async def reduce(self, accumulator: BinaryOperator[T]) -> T | None: ...

    async def reduce(self, identity: Any = _UNSET, accumulator: Any = _UNSET) -> Any:
        if accumulator is _UNSET:
            # Called as reduce(accumulator): the single positional arg is the
            # accumulator, and the identity is seeded from the stream itself.
            identity, accumulator = _UNSET, identity

        composed = self._compose()
        if identity is _UNSET:
            try:
                identity = await anext(composed)
            except StopAsyncIteration:
                return None

        async for n in composed:
            identity = await _maybe_await(accumulator, identity, n)
        return identity

    async def for_each(self, consumer: Consumer[T]) -> None:
        async for n in self._compose():
            await _maybe_await(consumer, n)
        return None

    async def for_each_ordered(self, consumer: Consumer[T]) -> None:
        async for n in self._sequential(self._chain[:], self._stream):
            await _maybe_await(consumer, n)
        return None

    async def to_array(self) -> list[T]:
        return await self.collect(to_list)

    """
    async def find_first(self) -> Optional[Any]:
        # until we have ordered parallel stream then we
        # cant do this one
        return await self.find_any()
    """

    async def find_any(self) -> T | None:
        async for n in self._compose():
            return n

    async def max(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=False)

    async def min(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=True)

    async def _min_max(self, comparator: Comparator[T], asc: bool) -> T | None:
        async def compare(a: T, b: T) -> int:
            sign = await _maybe_await(comparator, a, b)
            check_comparator_result_type(sign)
            return sign

        found = cast(T, _UNSET)
        async for n in self._compose():
            if found is _UNSET:
                found = n
                continue

            # comparator(n, found): negative if n orders before found, positive
            # if after. found (the earlier element) is kept on a tie.
            sign = await compare(n, found)
            if asc:
                is_new_extreme = sign < 0
            else:
                is_new_extreme = sign > 0
            if is_new_extreme:
                found = n
        return None if found is _UNSET else found

    async def _match(self, predicate: Predicate[T], short_circuit_on: bool, default: bool) -> bool:
        async for n in self._compose():
            if bool(await _maybe_await(predicate, n)) is short_circuit_on:
                return short_circuit_on
        return default

    async def all_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=False, default=True)

    async def none_match(self, predicate: Predicate[T]) -> bool:
        return not await self._match(predicate, short_circuit_on=True, default=False)

    async def any_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=True, default=False)

    async def count(self) -> int:
        c = 0
        async for _ in self._compose():
            c += 1
        return c

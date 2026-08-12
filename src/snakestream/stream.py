from __future__ import annotations

from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Any, cast
from collections.abc import AsyncGenerator, Callable, Generator

from snakestream.base_stream import BaseStream
from snakestream.callable_dispatch import _maybe_await
from snakestream.collector import to_generator
from snakestream.exception import StreamBuildException
from snakestream.sort import check_comparator_result_type, merge_sort
from snakestream.type import R, T, Accumulator, CloseHandler, Comparator, Consumer, FlatMapper, Mapper, Predicate


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
        async for i in iterable:
            if size_holder[0] >= self._max_size:
                await iterable.aclose()
            else:
                size_holder[0] += 1
                yield i


class Stream(BaseStream):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        super().__init__(source)
        self._close_handlers = close_handlers or []

    @staticmethod
    def of(*args: Any) -> Stream:
        if len(args) == 1:
            return Stream(args[0])
        return Stream(list(args))

    @staticmethod
    def empty() -> Stream:
        return Stream([])

    @staticmethod
    async def concat(a: Stream, b: Stream) -> Stream:
        new_stream = _concat(a, b)
        return Stream(new_stream)

    @staticmethod
    def builder() -> StreamBuilder:
        from snakestream.stream_builder import StreamBuilder

        return StreamBuilder()

    @staticmethod
    def iterate(seed: T, nxt: Callable[[T], T]):
        def _make_iterator(seed: T, nxt: Callable[[T], T]) -> Generator[T, None, None]:
            yield seed
            while True:
                seed = nxt(seed)
                yield seed

        return Stream.of(_make_iterator(seed, nxt))

    # Intermediaries
    def filter(self, predicate: Predicate) -> Stream:
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                keep = await _maybe_await(predicate, i)
                if keep:
                    yield i

        self._chain.append(fn)
        return self

    def map(self, mapper: Mapper) -> Stream:
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                yield await _maybe_await(mapper, i)

        self._chain.append(fn)
        return self

    def flat_map(self, flat_mapper: FlatMapper) -> Stream:
        # Pre-call rejection, not a dispatch site: flat_mapper must return a
        # Stream synchronously, so an async def here is always a caller
        # mistake. This is unrelated to _maybe_await's post-call awaiting.
        if iscoroutinefunction(flat_mapper):
            raise StreamBuildException("flat_map() does not support coroutines")

        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                async for j in flat_mapper(i).collect(to_generator):
                    yield j

        self._chain.append(fn)
        return self

    def sorted(self, comparator: Comparator | None = None, reverse=False) -> Stream:
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

    def distinct(self) -> Stream:
        self._chain.append(_DistinctOp())
        return self

    def peek(self, consumer: Consumer) -> Stream:
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                await _maybe_await(consumer, i)
                yield i

        self._chain.append(fn)
        return self

    def limit(self, max_size: int) -> Stream:
        self._chain.append(_LimitOp(max_size))
        return self

    # Terminals
    def collect(self, collector: Callable[[AsyncGenerator], R]) -> R:
        return collector(self._compose())

    async def reduce(self, identity: T | R, accumulator: Accumulator) -> T | R:
        async for n in self._compose():
            identity = await _maybe_await(accumulator, identity, n)
        return identity

    async def for_each(self, consumer: Callable[[T], Any]) -> None:
        async for n in self._compose():
            await _maybe_await(consumer, n)
        return None

    """
    async def find_first(self) -> Optional[Any]:
        # until we have ordered parallel stream then we
        # cant do this one
        return await self.find_any()
    """

    async def find_any(self) -> Any | None:
        async for n in self._compose():
            return n

    async def max(self, comparator: Comparator) -> T | None:
        return await self._min_max(comparator, asc=False)

    async def min(self, comparator: Comparator) -> T | None:
        return await self._min_max(comparator, asc=True)

    async def _min_max(self, comparator: Comparator, asc: bool) -> T | None:
        async def compare(a: T, b: T) -> int:
            sign = await _maybe_await(comparator, a, b)
            check_comparator_result_type(sign)
            return sign

        found = cast(T, _UNSET)
        async for raw in self._compose():
            n = cast(T, raw)
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

    async def _match(self, predicate: Predicate, short_circuit_on: bool, default: bool) -> bool:
        async for n in self._compose():
            if bool(await _maybe_await(predicate, n)) is short_circuit_on:
                return short_circuit_on
        return default

    async def all_match(self, predicate: Predicate) -> bool:
        return await self._match(predicate, short_circuit_on=False, default=True)

    async def none_match(self, predicate: Predicate) -> bool:
        return not await self._match(predicate, short_circuit_on=True, default=False)

    async def any_match(self, predicate: Predicate) -> bool:
        return await self._match(predicate, short_circuit_on=True, default=False)

    async def count(self) -> int:
        c = 0
        async for _ in self._compose():
            c += 1
        return c

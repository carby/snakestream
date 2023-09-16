from __future__ import annotations
import asyncio

from functools import cmp_to_key
from inspect import iscoroutinefunction
from types import AsyncGeneratorType
from typing import Callable, Optional, AsyncIterable, List, \
    Union, AsyncGenerator, Any

from snakestream.collector import to_generator
from snakestream.exception import StreamBuildException
from snakestream.sort import merge_sort
from snakestream.type import R, T, AbstractBaseStream, AbstractStream, \
    AbstractStreamBuilder, Accumulator, Comparator, Consumer, \
    FlatMapper, Mapper, Predicate, Streamable


async def _normalize(iterable: Streamable) -> AsyncGenerator:
    if isinstance(iterable, AsyncGenerator) or isinstance(iterable, AsyncIterable):
        async for i in iterable:
            yield i
    else:
        for i in iterable:
            yield i


async def _concat(a: 'Stream', b: 'Stream') -> AsyncGenerator:
    async for i in await a._compose(a._chain, a._stream):
        yield i
    async for j in await b._compose(b._chain, b._stream):
        yield j


class BaseStream(AbstractBaseStream):
    def __init__(self, streamable: Streamable) -> None:
        self._is_parallel = False
        self._chain: List[Callable] = []
        self._stream: AsyncGenerator = _normalize(streamable)

    def is_parallel(self) -> bool:
        return self._is_parallel

    # Intermediaries
    def parallel(self) -> 'BaseStream':
        self._is_parallel = True
        return self

    # Terminals
    async def _sequential_compose(self, intermediaries: List[Callable], iterable: AsyncGenerator) -> AsyncGenerator:
        if len(intermediaries) == 0:
            return iterable
        if len(intermediaries) == 1:
            fn = intermediaries.pop(0)
            return fn(iterable)
        fn = intermediaries.pop(0)
        return await self._sequential_compose(intermediaries, fn(iterable))

    async def _compose(self, intermediaries: List[Callable], iterable: AsyncGenerator) -> AsyncGenerator:
        if self.is_parallel:
            return await self._sequential_compose(intermediaries=intermediaries, iterable=iterable)
        else:
            return await self._sequential_compose(intermediaries=intermediaries, iterable=iterable)


class Stream(BaseStream, AbstractStream):

    @staticmethod
    def empty() -> 'Stream':
        return Stream([])

    @staticmethod
    async def concat(a: 'Stream', b: 'Stream') -> 'Stream':
        new_stream = _concat(a, b)
        return Stream(new_stream)

    @staticmethod
    def builder() -> 'AbstractStreamBuilder':
        from snakestream.stream_builder import StreamBuilder
        return StreamBuilder()

    # Intermediaries
    def filter(self, predicate: Predicate) -> 'Stream':
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                if iscoroutinefunction(predicate):
                    keep = await predicate(i)
                else:
                    keep = predicate(i)
                if keep:
                    yield i

        self._chain.append(fn)
        return self

    def map(self, mapper: Mapper) -> 'Stream':
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                if iscoroutinefunction(mapper):
                    yield await mapper(i)
                else:
                    yield mapper(i)

        self._chain.append(fn)
        return self

    def flat_map(self, flat_mapper: FlatMapper) -> 'Stream':
        if iscoroutinefunction(flat_mapper):
            raise StreamBuildException("flat_map() does not support coroutines")

        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                async for j in await flat_mapper(i).collect(to_generator):
                    yield j

        self._chain.append(fn)
        return self

    def sorted(self, comparator: Optional[Comparator] = None, reverse=False) -> 'Stream':
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            # unfortunately I now don't see other way than to block the entire stream
            # how can I otherwise know what is the first item out?
            cache = []
            async for i in iterable:
                cache.append(i)
            # sort
            if comparator is not None:
                if iscoroutinefunction(comparator):
                    cache = await merge_sort(cache, comparator)
                else:
                    cache.sort(key=cmp_to_key(comparator))
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

    def distinct(self) -> 'Stream':
        seen = set()

        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                if i in seen:
                    continue
                else:
                    seen.add(i)
                    yield i

        self._chain.append(fn)
        return self

    def peek(self, consumer: Consumer) -> 'Stream':
        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            async for i in iterable:
                if iscoroutinefunction(consumer):
                    await consumer(i)
                else:
                    consumer(i)
                yield i

        self._chain.append(fn)
        return self

    # Terminals
    async def collect(self, collector: Callable) -> Union[List, AsyncGenerator]:
        collection = collector(await self._compose(self._chain, self._stream))
        if isinstance(collection, AsyncGeneratorType):
            return collection
        else:
            return await collection


    async def reduce(self, identity: Union[T, R], accumulator: Accumulator) -> Union[T, R]:
        async for n in await self._compose(self._chain, self._stream):
            if iscoroutinefunction(accumulator):
                identity = await accumulator(identity, n)
            else:
                identity = accumulator(identity, n)
        return identity

    async def for_each(self, consumer: Callable[[T], Any]) -> None:
        async for n in await self._compose(self._chain, self._stream):
            if iscoroutinefunction(consumer):
                await consumer(n)
            else:
                consumer(n)
        return None

    async def find_first(self) -> Optional[Any]:
        async for n in await self._compose(self._chain, self._stream):
            return n

    async def max(self, comparator: Comparator) -> Optional[T]:
        return await self._min_max(comparator)

    async def min(self, comparator: Comparator) -> Optional[T]:
        if iscoroutinefunction(comparator):
            async def negative_comparator(x, y):
                return not await comparator(x, y)
            return await self._min_max(negative_comparator)
        else:
            def negative_comparator(x, y):
                return not comparator(x, y)
            return await self._min_max(negative_comparator)

    async def _min_max(self, comparator: Comparator) -> Optional[T]:
        found = None
        async for n in await self._compose(self._chain, self._stream):
            if found is None:
                found = n
                continue

            if iscoroutinefunction(comparator):
                if n and await comparator(n, found):
                    found = n
            else:
                if n and comparator(n, found):
                    found = n
        return found

    async def all_match(self, predicate: Predicate) -> bool:
        async for n in await self._compose(self._chain, self._stream):
            if iscoroutinefunction(predicate):
                if await predicate(n):
                    continue
                else:
                    return False
            else:
                if predicate(n):
                    continue
                else:
                    return False
        return True

    async def none_match(self, predicate: Predicate) -> bool:
        async for n in await self._compose(self._chain, self._stream):
            if iscoroutinefunction(predicate):
                if await predicate(n):
                    return False
                else:
                    continue
            else:
                if predicate(n):
                    return False
                else:
                    continue
        return True

    async def any_match(self, predicate: Predicate) -> bool:
        async for n in await self._compose(self._chain, self._stream):
            if iscoroutinefunction(predicate):
                if await predicate(n):
                    return True
                else:
                    continue
            else:
                if predicate(n):
                    return True
                else:
                    continue
        return False

    async def count(self) -> int:
        c = 0
        async for _ in await self._compose(self._chain, self._stream):
            c += 1
        return c

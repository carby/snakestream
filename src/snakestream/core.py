from __future__ import annotations

import asyncio
from functools import cmp_to_key
from inspect import iscoroutinefunction
from typing import Callable, Optional, AsyncIterable, List, \
    Union, AsyncGenerator, Any

from snakestream.collector import to_generator
from snakestream.exception import StreamBuildException
from snakestream.sort import merge_sort
from snakestream.type import R, T, AbstractStream, AbstractStreamBuilder, Accumulator, Comparator, Consumer, \
    FlatMapper, Mapper, Predicate


PROCESSES: int = 4


async def _normalize(source: Any) -> AsyncGenerator:
    if hasattr(source, '__iter__') or hasattr(source, '__next__'):
        for i in source:
            yield i
    else:
        yield source


def _accept(source: Any) -> Optional[AsyncGenerator]:
    if isinstance(source, AsyncGenerator) or isinstance(source, AsyncIterable):
        return source
    return None


async def _concat(a: 'Stream', b: 'Stream') -> AsyncGenerator:
    async for i in a._compose():
        yield i
    async for j in b._compose():
        yield j


class BaseStream():
    def __init__(self, source: Any) -> None:
        self._stream = _accept(source) or _normalize(source)
        self._chain: List[Callable] = []
        self.is_parallel = False

    def _sequential(self, intermediaries: List[Callable], iterable: AsyncGenerator) -> AsyncGenerator:
        if len(intermediaries) == 0:
            return iterable
        if len(intermediaries) == 1:
            fn = intermediaries.pop(0)
            return fn(iterable)
        fn = intermediaries.pop(0)
        return self._sequential(intermediaries, fn(iterable))

    def _compose(self) -> AsyncGenerator:
        return self._sequential(self._chain, self._stream)

    def sequential(self) -> 'Stream':
        new_source = self._compose()
        return Stream(new_source);

    def parallel(self) -> 'Stream':
        new_source = self._compose()
        return ParallelStream(new_source);


#
# If you add a method here, also add it to AbstractStream
#
class Stream(BaseStream, AbstractStream):
    def __init__(self, source: Any) -> None:
        super().__init__(source)

    @staticmethod
    def of(source: Any) -> 'Stream':
        return Stream(source)

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
                async for j in flat_mapper(i).collect(to_generator):
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
    def collect(self, collector: Callable) -> Union[List, AsyncGenerator]:
        return collector(self._compose())

    async def reduce(self, identity: Union[T, R], accumulator: Accumulator) -> Union[T, R]:
        async for n in self._compose():
            if iscoroutinefunction(accumulator):
                identity = await accumulator(identity, n)
            else:
                identity = accumulator(identity, n)
        return identity

    async def for_each(self, consumer: Callable[[T], Any]) -> None:
        async for n in self._compose():
            if iscoroutinefunction(consumer):
                await consumer(n)
            else:
                consumer(n)
        return None

    '''
    async def find_first(self) -> Optional[Any]:
        # until we have ordered parallel stream then we
        # cant do this one
        return await self.find_any()
    '''

    async def find_any(self) -> Optional[Any]:
        async for n in self._compose():
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
        async for n in self._compose():
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
        async for n in self._compose():
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
        async for n in self._compose():
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
        async for n in self._compose():
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
        async for _ in self._compose():
            c += 1
        return c


class ParallelStream(Stream):
    def __init__(self, source: Any) -> None:
        super().__init__(source)
        self.is_parallel = True

    def _compose(self) -> AsyncGenerator:
        return self._parallel(self._chain, self._stream)

    async def _parallel(
        self,
        intermediaries: List[Callable],
        iterable: AsyncGenerator,
        processes: int = PROCESSES
    ) -> AsyncGenerator:
        async_iterators = [self._sequential(intermediaries[:], iterable) for n in range(processes)]
        tasks = [asyncio.ensure_future(n.__anext__()) for n in async_iterators]

        while any([n is not None for n in tasks]):

            waitlist = filter(lambda n: n is not None, tasks)
            done, _ = await asyncio.wait(waitlist, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                task_idx = tasks.index(task)
                try:
                    result = tasks[task_idx].result()
                    tasks[task_idx] = asyncio.ensure_future(async_iterators[task_idx].__anext__())
                    yield result
                except StopAsyncIteration:
                    tasks[task_idx] = None
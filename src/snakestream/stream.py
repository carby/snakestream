from __future__ import annotations

from functools import cmp_to_key
from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Callable, Generator, Optional, List, \
    Union, AsyncGenerator, Any

from snakestream.base_stream import BaseStream
from snakestream.collector import to_generator
from snakestream.exception import StreamBuildException
from snakestream.sort import merge_sort
from snakestream.type import R, T, Accumulator, CloseHandler, Comparator, Consumer, \
    FlatMapper, Mapper, Predicate


if TYPE_CHECKING:
    from stream_builder import StreamBuilder


PROCESSES: int = 4


async def _concat(a: 'Stream', b: 'Stream') -> AsyncGenerator:
    async for i in a._compose():
        yield i
    async for j in b._compose():
        yield j


class Stream(BaseStream):
    def __init__(self, source: Any, close_handlers: Optional[List[CloseHandler]] = None) -> None:
        super().__init__(source)
        self._close_handlers = close_handlers or []

    @staticmethod
    def of(*args, **kwargs) -> 'Stream':
        source = []

        if args and len(args) == 0:
            pass
        elif args and len(args) == 1:
            if isinstance(args[0], dict):
                source.append(args[0])
            elif isinstance(args[0], list):
                source = args[0]
            else:
                source.append(args[0])
        else:
            source += list(args)

        if kwargs and len(kwargs.items()):
            if len(source):
                source += list(kwargs.items())
            else:
                return Stream(list(kwargs.items()))

        if len(source) == 1:
            return Stream(source[0])
        return Stream(source)

    @staticmethod
    def empty() -> 'Stream':
        return Stream([])

    @staticmethod
    async def concat(a: 'Stream', b: 'Stream') -> 'Stream':
        new_stream = _concat(a, b)
        return Stream(new_stream)

    @staticmethod
    def builder() -> 'StreamBuilder':
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

    def limit(self, max_size: int) -> 'Stream':
        size = 0

        async def fn(iterable: AsyncGenerator) -> AsyncGenerator:
            nonlocal size
            async for i in iterable:
                if size >= max_size:
                    await iterable.aclose()
                else:
                    size += 1
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

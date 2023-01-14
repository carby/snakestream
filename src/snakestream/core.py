from inspect import iscoroutinefunction
from typing import TypeVar, Callable, Optional, Iterable, AsyncIterable, List, Awaitable, \
    Union, Generator, AsyncGenerator, Any

from snakestream.collectors import to_generator
from snakestream.exception import StreamBuildException

T = TypeVar('T')
R = TypeVar('R')

Streamable = Union[Iterable, AsyncIterable, Generator, AsyncGenerator]

Predicate = Callable[[T], Union[bool, Awaitable[bool]]]

# Intermediaries
Filterer = Callable[[T], T]
Mapper = Callable[[T], Optional[R]]
FlatMapper = Callable[[Streamable], 'Stream']

# Terminals
Accumulator = Callable[[T, Union[T, R]], Union[T, R]]


async def _normalize(iterable: Streamable) -> AsyncGenerator:
    if isinstance(iterable, AsyncGenerator) or isinstance(iterable, AsyncIterable):
        async for i in iterable:
            yield i
    else:
        for i in iterable:
            yield i


class Stream:
    def __init__(self, streamable: Streamable) -> None:
        self._stream: AsyncGenerator = _normalize(streamable)
        self._chain: List[Callable] = []

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

    # Terminals
    def _compose(self, intermediaries: List[Callable], iterable: AsyncGenerator) -> AsyncGenerator:
        if len(intermediaries) == 0:
            return iterable
        if len(intermediaries) == 1:
            fn = intermediaries.pop(0)
            return fn(iterable)
        fn = intermediaries.pop(0)
        return self._compose(intermediaries, fn(iterable))

    def collect(self, collector: Callable) -> AsyncGenerator:
        return collector(self._compose(self._chain, self._stream))

    async def reduce(self, identity: Union[T, R], accumulator: Accumulator) -> Union[T, R]:
        async for n in self._compose(self._chain, self._stream):
            identity = accumulator(identity, n)
        return identity

    async def for_each(self, consumer: Callable[[T], Any]) -> None:
        async for n in self._compose(self._chain, self._stream):
            if iscoroutinefunction(consumer):
                await consumer(n)
            else:
                consumer(n)
        return None

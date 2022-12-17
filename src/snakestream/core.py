from inspect import iscoroutinefunction
from typing import TypeVar, Callable, Optional, Iterable, AsyncIterable, List, Any, Awaitable, Union, Generator, \
    AsyncGenerator

from snakestream.exception import StreamBuildException

T = TypeVar('T')
U = TypeVar('U')

Streamable = Union[Iterable, AsyncIterable, Generator, AsyncGenerator]

Predicate = Callable[[T], Union[bool, Awaitable[bool]]]
Filterer = Callable[[T], T]
Accumulator = Callable[[T, Union[T, U]], Union[T, U]]
Mapper = Callable[[T], Optional[U]]
FlatMapper = Callable[[Streamable], 'Stream']




async def _normalize(iterable: Streamable) -> Union[Generator, AsyncGenerator]:
    try:
        for i in iterable:
            yield i
    except TypeError:
        async for i in iterable:
            yield i


class Stream:
    def __init__(self, streamable: Streamable) -> None:
        self._stream: Iterable = _normalize(streamable)
        self._chain: List[Callable] = []

    # Intermediaries
    def filter(self, predicate: Predicate) -> 'Stream':
        async def fn(iterable: Union[Iterable, AsyncIterable]) -> Union[Iterable, AsyncIterable]:
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
        async def fn(iterable: Union[Iterable, AsyncIterable]) -> Union[Iterable, AsyncIterable]:
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

        async def fn(iterable: Union[Iterable, AsyncIterable]) -> Union[Iterable, AsyncIterable]:
            async for i in iterable:
                async for j in flat_mapper(i).collect():
                    yield j

        self._chain.append(fn)
        return self

    # Terminals
    def _compose(self, intermediaries: List[Callable], iterable: Iterable) -> Union[Iterable, AsyncIterable]:
        if len(intermediaries) == 0:
            return iterable
        if len(intermediaries) == 1:
            fn = intermediaries.pop(0)
            return fn(iterable)
        if len(intermediaries) > 1:
            fn = intermediaries.pop(0)
            return self._compose(intermediaries, fn(iterable))

    async def collect(self) -> AsyncIterable[Any]:
        async for n in self._compose(self._chain, self._stream):
            yield n

    async def reduce(self, identity: Union[T, U], accumulator: Accumulator) -> Union[T, U]:
        iterable = self._compose(self._chain, self._stream)
        async for n in iterable:
            identity = accumulator(identity, n)
        return identity


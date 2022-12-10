from inspect import iscoroutinefunction
from typing import TypeVar, Callable, Optional, Iterable, AsyncIterable, List, Any, Awaitable, Union

T = TypeVar('T')
U = TypeVar('U')

Predicate = Callable[[T], bool]
Filterer = Callable[[T], T]
Accumulator = Callable[[T], Union[T, U]]
Mapper = Callable[[T], Optional[U]]


async def _normalize_iterator(iterable: Iterable[Any]) -> Awaitable:
    try:
        for i in iterable:
            yield i
    except TypeError:
        async for i in iterable:
            yield i


class Stream:
    def __init__(self, iterable: Iterable[Any]) -> None:
        self._iterable: Iterable[Any] = _normalize_iterator(iterable)
        self._chain: List[Awaitable] = []

    # Intermediaries
    def filter(self, predicate: Predicate) -> Filterer:
        async def fn(iterable: Iterable[Any]) -> Awaitable:
            async for i in iterable:
                if iscoroutinefunction(predicate):
                    keep = await predicate(i)
                else:
                    keep = predicate(i)

                if keep:
                    yield i

        self._chain.append(fn)
        return self

    def map(self, mapper: Mapper) -> Mapper:
        async def fn(iterable: Iterable[Any]) -> Awaitable:
            async for i in iterable:
                if iscoroutinefunction(mapper):
                    yield await mapper(i)
                else:
                    yield mapper(i)

        self._chain.append(fn)
        return self

    def flat_map(self, flat_mapper: Mapper) -> Mapper:
        async def fn(iterable: Iterable[Any]) -> Awaitable:
            async for i in iterable:
                if isinstance(i, List):
                    for j in i:
                        if iscoroutinefunction(flat_mapper):
                            yield await flat_mapper(j)
                        else:
                            yield flat_mapper(j)
                else:
                    if iscoroutinefunction(flat_mapper):
                        yield await flat_mapper(i)
                    else:
                        yield flat_mapper(i)

        self._chain.append(fn)
        return self

    # Terminals
    def _compose(self, intermediaries: List[Awaitable], iterable: Iterable[Any]) -> Awaitable:
        if len(intermediaries) == 0:
            return iterable
        if len(intermediaries) == 1:
            fn = intermediaries.pop(0)
            return fn(iterable)
        if len(intermediaries) > 1:
            fn = intermediaries.pop(0)
            return self._compose(intermediaries, fn(iterable))

    async def collect(self) -> AsyncIterable[Optional[Any]]:
        async for n in self._compose(self._chain, self._iterable):
            yield n

    async def reduce(self, identity: Union[T, U], accumulator: Accumulator) -> Union[T, U]:
        iterable = self._compose(self._chain, self._iterable)
        async for n in iterable:
            identity = accumulator(identity, n)
        return identity


def stream(iterable: Iterable[T]):
    return Stream(iterable)

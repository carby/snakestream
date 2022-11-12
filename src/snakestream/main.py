from inspect import iscoroutinefunction
from typing import TypeVar, Callable, Optional, Iterable, AsyncIterable, List, Any, Awaitable

T = TypeVar('T')
U = TypeVar('U')
Predicate = Callable[[T], bool]
Filter = Callable[[T], T]
Mapper = Callable[[T], Optional[U]]
Chainable = Callable[[Optional[Any]], Optional[Any]]


class StreamInterrupt(Exception):
    pass


class Stream:
    def __init__(self, iterable: Iterable[Any]) -> None:
        self._iterable: Iterable[Any] = iterable
        self._chain: List[Chainable] = []

    def filter(self, predicate: Predicate) -> Filter:
        if iscoroutinefunction(predicate):
            async def fn(x: T) -> T:
                if await predicate(x):
                    return x
                raise StreamInterrupt
        else:
            async def fn(x: T) -> T:
                if predicate(x):
                    return x
                raise StreamInterrupt
        self._chain.append(fn)
        return self

    def map(self, mapper: Mapper) -> Mapper:
        if iscoroutinefunction(mapper):
            async def fn(x: T) -> U:
                return await mapper(x)
        else:
            async def fn(x: T) -> U:
                return mapper(x)
        self._chain.append(fn)
        return self

    def _compose(self, *funcs: Chainable) -> Awaitable:
        async def apply(x):
            for func in funcs:
                x = await func(x)
            return x
        return apply

    async def collect(self) -> AsyncIterable[Optional[Any]]:
        composition = self._compose(*self._chain)
        for n in self._iterable:
            try:
                yield await composition(n)
            except StreamInterrupt:
                next


def stream(iterable: Iterable[T]):
    return Stream(iterable)


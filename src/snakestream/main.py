from enum import Enum
from inspect import iscoroutinefunction
from typing import TypeVar, Callable, Optional, Iterable, AsyncIterable, List, Any, Awaitable, Union, Dict

T = TypeVar('T')
U = TypeVar('U')

Predicate = Callable[[T], bool]
Filterer = Callable[[T], T]
Accumulator = Callable[[T], Union[T, U]]
Mapper = Callable[[T], Optional[U]]


class StreamInterrupt(Exception):
    pass


class IntermediaryType(Enum):
    FILTERER, MAPPER = range(0, 2)


class Intermediary():
    def __init__(self, fn: Callable, type: IntermediaryType) -> None:
        self.fn = fn
        self.type = type


class Stream:
    def __init__(self, iterable: Iterable[Any]) -> None:
        self._iterable: Iterable[Any] = iterable
        self._chain: List[Intermediary] = []

    # Intermediaries
    def filter(self, predicate: Predicate) -> Filterer:
        self._chain.append(Intermediary(predicate, IntermediaryType.FILTERER))
        return self

    def map(self, mapper: Mapper) -> Mapper:
        self._chain.append(Intermediary(mapper, IntermediaryType.MAPPER))
        return self

    def _compose(self, *intermediaries: Intermediary) -> Awaitable:
        async def apply(x):
            for intermediary in intermediaries:
                if intermediary.type == IntermediaryType.FILTERER:
                    if iscoroutinefunction(intermediary.fn):
                        keep = await intermediary.fn(x)
                    else:
                        keep = intermediary.fn(x)
                    if not keep:
                        raise StreamInterrupt
                elif intermediary.type == IntermediaryType.MAPPER:
                    if iscoroutinefunction(intermediary.fn):
                        x = await intermediary.fn(x)
                    else:
                        x = intermediary.fn(x)
                else:
                    raise RuntimeError('Unknown intermediary type')
            return x
        return apply

    # Terminals
    async def reduce(self, identity: Union[T, U], accumulator: Accumulator) -> Union[T, U]:
        composition = self._compose(*self._chain)
        for n in self._iterable:
            try:
                value = await composition(n)
            except StreamInterrupt:
                next
            identity = accumulator(identity, value)
        return identity

    async def collect(self) -> AsyncIterable[Optional[Any]]:
        composition = self._compose(*self._chain)
        for n in self._iterable:
            try:
                yield await composition(n)
            except StreamInterrupt:
                next


def stream(iterable: Iterable[T]):
    return Stream(iterable)

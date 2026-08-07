from typing import TYPE_CHECKING, TypeVar
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Callable, Generator, Iterable

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover

T = TypeVar('T')
R = TypeVar('R')

Predicate = Callable[[T], bool | Awaitable[bool]]

# Intermediaries
Filterer = Callable[[T], T]
Mapper = Callable[[T], R | None]
FlatMapper = Callable[[Iterable | AsyncIterable | Generator | AsyncGenerator], 'Stream']
Comparator = Callable[[T, T], bool | Awaitable[bool]]
Consumer = Callable[[T], T]
CloseHandler = Callable[[], None]

# Terminals
Accumulator = Callable[[T, T | R], T | R]

from typing import TYPE_CHECKING, Callable, Optional, TypeVar, Union
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Generator, Iterable

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover

T = TypeVar('T')
R = TypeVar('R')

Predicate = Callable[[T], Union[bool, Awaitable[bool]]]

# Intermediaries
Filterer = Callable[[T], T]
Mapper = Callable[[T], Optional[R]]
FlatMapper = Callable[[Union[Iterable, AsyncIterable, Generator, AsyncGenerator]], 'Stream']
Comparator = Callable[[T, T], Union[bool, Awaitable[bool]]]
Consumer = Callable[[T], T]
CloseHandler = Callable[[], None]

# Terminals
Accumulator = Callable[[T, Union[T, R]], Union[T, R]]

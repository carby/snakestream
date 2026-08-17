from typing import TYPE_CHECKING, TypeVar
from collections.abc import Awaitable, Callable

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover

T = TypeVar("T")
R = TypeVar("R")

Predicate = Callable[[T], bool | Awaitable[bool]]

# Intermediaries
Filterer = Callable[[T], T]
Mapper = Callable[[T], R | None]
FlatMapper = Callable[[T], "Stream[R]"]
Comparator = Callable[[T, T], int | Awaitable[int]]
Consumer = Callable[[T], T]
CloseHandler = Callable[[], None]

# Terminals
Accumulator = Callable[[T, T | R], T | R]
BinaryOperator = Callable[[T, T], T | Awaitable[T]]
Supplier = Callable[[], R | Awaitable[R]]
BiConsumer = Callable[[R, T], None | Awaitable[None]]

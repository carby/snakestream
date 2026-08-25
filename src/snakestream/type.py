from typing import TYPE_CHECKING, Any, Protocol, TypeVar
from collections.abc import AsyncIterator, Awaitable, Callable

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover

T = TypeVar("T")
R = TypeVar("R")
A = TypeVar("A")

# An async source, whatever kind: the async generators source normalization
# builds, and the bare AsyncIterables accepted untouched. Bound rather than
# fixed to AsyncGenerator so a helper handed one kind gives that same kind
# back, and its callers don't have to widen in sympathy.
_Aiter = TypeVar("_Aiter", bound=AsyncIterator[Any])

# Sink protocol: the state passed through begin(), keyed by the originating
# operation object so a sink can look up its own shared state.
StateMap = dict[Any, Any]

Predicate = Callable[[T], bool | Awaitable[bool]]

# Intermediaries
Mapper = Callable[[T], R | None | Awaitable[R | None]]
FlatMapper = Callable[[T], "Stream[R]"]
Comparator = Callable[[T, T], int | Awaitable[int]]
# The awaitable arm of Comparator, for the merge-sort path that reaches it
# only after sort() has established the comparator returns awaitables.
AsyncComparator = Callable[[T, T], Awaitable[int]]
Consumer = Callable[[T], None | Awaitable[None]]
CloseHandler = Callable[[], None]

# Terminals
Accumulator = Callable[[T, T | R], T | R | Awaitable[T | R]]
BinaryOperator = Callable[[T, T], T | Awaitable[T]]
Supplier = Callable[[], R | Awaitable[R]]
BiConsumer = Callable[[R, T], None | Awaitable[None]]
NumberMapper = Callable[[T], int | float | Awaitable[int | float]]

# Collector protocol
Finisher = Callable[[A], R | Awaitable[R]]
Combiner = Callable[[A, A], A | Awaitable[A]]


class _SupportsAdd(Protocol):
    def add(self, item: Any) -> Any: ...


_C = TypeVar("_C", bound=_SupportsAdd)

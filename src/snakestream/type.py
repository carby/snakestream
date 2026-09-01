from typing import TYPE_CHECKING, Any, Protocol, TypeVar
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping

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
Mapper = Callable[[T], R | Awaitable[R]]
FlatMapper = Callable[[T], "Stream[R]"]
Comparator = Callable[[T, T], int | Awaitable[int]]
# The awaitable arm of Comparator, for the merge-sort path that reaches it
# only after sort() has established the comparator returns awaitables.
AsyncComparator = Callable[[T, T], Awaitable[int]]
# Produces an ordering key for one element, not a comparison sign - the
# argument to comparing().
KeyExtractor = Callable[[T], Any | Awaitable[Any]]
# The extractor-plus-comparator pairing comparing()/then_comparing() build
# when given a key_comparator (add-comparator-segments, Decision 6): the
# extractor keeps its own per-element gather (sync or async), and the
# comparator supplies the ordering applied to the resulting keys. The
# extractor is None for a bare comparator segment, where the comparator
# orders elements directly rather than an extracted key.
KeyExtractorComparator = tuple[KeyExtractor | None, Comparator]
Consumer = Callable[[T], Awaitable[None] | None]
CloseHandler = Callable[[], None]

# Terminals
Accumulator = Callable[[T, T | R], T | R | Awaitable[T | R]]
BinaryOperator = Callable[[T, T], T | Awaitable[T]]
Supplier = Callable[[], R | Awaitable[R]]
BiConsumer = Callable[[R, T], Awaitable[None] | None]
NumberMapper = Callable[[T], int | float | Awaitable[int | float]]

# Collector protocol
Finisher = Callable[[A], R | Awaitable[R]]
Combiner = Callable[[A, A], A | Awaitable[A]]


class _SupportsAdd(Protocol):
    def add(self, item: Any) -> Any: ...


_C = TypeVar("_C", bound=_SupportsAdd)

# The container typevar for the caller-supplied *mapping* forms - to_map()'s
# map_supplier and grouping_by()'s map_factory. Separate from _C, which is
# bound to _SupportsAdd: a mapping is written by key rather than by add(), so
# neither bound serves the other.
_M = TypeVar("_M", bound=MutableMapping[Any, Any])

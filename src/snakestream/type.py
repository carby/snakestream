from typing import TYPE_CHECKING, Any, Protocol, TypeVar
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover

# T, R, A, Aiter, C and M stay TypeVars rather than PEP 695 scoped parameters:
# each is imported by more than one module (eight of ten import at least T),
# and PEP 695 has no syntax for a shared, named type variable - only aliases
# (`type X[T] = ...`) and scope-private parameters (`class Foo[T]`, `def f[T]`).
# C and M in particular carry bounds (_SupportsAdd, MutableMapping[Any, Any])
# used at 3 and 5 sites respectively; inlining either TypeVar would repeat its
# bound at every use site instead of stating it once.
T = TypeVar("T")
R = TypeVar("R")
A = TypeVar("A")

# An async source, whatever kind: the async generators source normalization
# builds, and the bare AsyncIterables accepted untouched. Bound rather than
# fixed to AsyncGenerator so a helper handed one kind gives that same kind
# back, and its callers don't have to widen in sympathy.
Aiter = TypeVar("Aiter", bound=AsyncIterator[Any])

# Sink protocol: the state passed through begin(), keyed by the originating
# operation object so a sink can look up its own shared state. Takes no
# parameters, so a plain assignment reads as well as a `type` statement would.
StateMap = dict[Any, Any]

type Predicate[T] = Callable[[T], bool | Awaitable[bool]]

# Intermediaries
type Mapper[T, R] = Callable[[T], R | Awaitable[R]]
type FlatMapper[T, R] = Callable[[T], Stream[R]]
type Comparator[T] = Callable[[T, T], int | Awaitable[int]]
# The awaitable arm of Comparator, for the merge-sort path that reaches it
# only after sort() has established the comparator returns awaitables.
type AsyncComparator[T] = Callable[[T, T], Awaitable[int]]
# Produces an ordering key for one element, not a comparison sign - the
# argument to comparing().
type KeyExtractor[T] = Callable[[T], Any | Awaitable[Any]]
# The extractor-plus-comparator pairing comparing()/then_comparing() build
# when given a key_comparator (add-comparator-segments, Decision 6): the
# extractor keeps its own per-element gather (sync or async), and the
# comparator supplies the ordering applied to the resulting keys. The
# extractor is None for a bare comparator segment, where the comparator
# orders elements directly rather than an extracted key.
type KeyExtractorComparator = tuple[KeyExtractor | None, Comparator]
type Consumer[T] = Callable[[T], Awaitable[None] | None]
type CloseHandler = Callable[[], None]

# Terminals
type Accumulator[T, R] = Callable[[T, T | R], T | R | Awaitable[T | R]]
type BinaryOperator[T] = Callable[[T, T], T | Awaitable[T]]
type Supplier[R] = Callable[[], R | Awaitable[R]]
type BiConsumer[R, T] = Callable[[R, T], Awaitable[None] | None]
type NumberMapper[T] = Callable[[T], int | float | Awaitable[int | float]]

# Collector protocol
type Finisher[A, R] = Callable[[A], R | Awaitable[R]]
type Combiner[A] = Callable[[A, A], A | Awaitable[A]]


class _SupportsAdd(Protocol):
    def add(self, item: Any) -> Any: ...


C = TypeVar("C", bound=_SupportsAdd)

# The container typevar for the caller-supplied *mapping* forms - to_map()'s
# map_supplier and grouping_by()'s map_factory. Separate from C, which is
# bound to _SupportsAdd: a mapping is written by key rather than by add(), so
# neither bound serves the other.
M = TypeVar("M", bound=MutableMapping[Any, Any])

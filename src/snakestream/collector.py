"""The collector protocol: Collector, the supplier/accumulator/combiner/
finisher quadruple mirroring Java's Collector<T,A,R>; CollectorSink, which
adapts one to the sink protocol; and StreamingCollector, the one collect()
argument that is not a Collector. The factories that build Collectors live in
collectors.py, which imports from here - never the other way round."""

from __future__ import annotations

from enum import Enum, auto
from inspect import isawaitable
from typing import Any, Generic, cast
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable

from snakestream.execution import maybe_aclosing
from snakestream.callable_dispatch import AsyncDispatch
from snakestream.sink import TerminalSink
from snakestream.type import (
    A,
    R,
    T,
    BiConsumer,
    Combiner,
    Finisher,
    Supplier,
)


class Characteristics(Enum):
    """Mirrors Java's `Collector.Characteristics`. Ships one member,
    `UNORDERED`, though the enum is shaped so `IDENTITY_FINISH` and
    `CONCURRENT` could join later without changing what `UNORDERED` means.

    `IDENTITY_FINISH` is left out because it is already observable as
    `Collector.finisher is None` - defining it too would give one fact two
    statements that can disagree. `CONCURRENT` describes accumulating into
    one shared container from independently reduced partitions; snakestream
    has no execution mode that produces independent partitions (`combiner` is
    accepted for signature parity and never invoked), so nothing could read
    it. Real partitioned execution belongs to the roadmap's Later, and that is
    where `CONCURRENT` belongs too.

    `UNORDERED` is a declaration a collector makes about itself - that any two
    orderings of the same elements collect to an equal result - rather than an
    instruction to the pipeline. Stream.collect() reads it, and it is the only
    reader: under RACING it decides whether the executor owes the collector a
    reorder barrier before delivery. Declaring it never changes the value a
    correct collector produces; it removes the head-of-line blocking and the
    reorder buffer that producing it in encounter order would cost. Under
    SEQUENTIAL it has no effect at all.

    Equal means `==` on the collected result, as that result's own type
    defines it, and nothing stronger. A collector declaring `UNORDERED` makes
    no promise whatever about the *iteration order* of what it produces - only
    that two orderings of the same elements compare equal. Java says the same
    thing from the other side: the collection operation "does not commit to
    preserving the encounter order of input elements", which is a statement
    about what is promised, not about what is detectable.

    The stricter reading - that no observable property of the result may
    differ - is not the rule, and cannot be: a CPython `set` built from the
    same members in two orders compares equal while iterating differently, so
    the strict reading would disqualify `to_set()`, the one collector Java
    documents as unordered, and leave the characteristic with no declarer at
    all."""

    UNORDERED = auto()


# Shared empty default for Collector.characteristics: a frozenset() call in
# the signature trips ruff's B008 (mutable-looking default), and naming it at
# module scope - the same move collectors.py makes for _TO_LIST - lets a
# reader rule out the mutable-default bug without a trip to the docstring.
_NO_CHARACTERISTICS: frozenset[Characteristics] = frozenset()


class Collector(Generic[T, A, R]):
    """Java-style `Collector<T,A,R>`: `supplier()` creates a fresh
    accumulation container, `accumulator(container, element)` mutates it per
    element - its return value is ignored - and `finisher(container)`
    converts the finished container to the result (the container itself, if
    `finisher` is omitted). `combiner` is accepted for signature parity with
    Java and never invoked: a collection always folds over one composed
    stream, sequential or parallel, with no independently accumulated
    partitions to merge - the same posture `Stream.collect(supplier,
    accumulator, combiner)` already has. `Stream.reduce()` is *not* a
    precedent: it has two overloads and no combiner at all, and growing one
    is sequenced behind real parallelism and spliterator() rather than added
    inert, so that both combiners start meaning something at once (roadmap
    **Later**).

    Every part may be sync or async. A `Collector` holds these four callables
    plus one immutable datum, `characteristics`: a `frozenset` of
    `Characteristics` declaring traits of the collector. It is data, not a
    callable, so it is neither invoked nor awaited and the sync-or-async rule
    the four callables carry does not apply to it. A `Collector` has no other
    per-collection state of its own, so one instance is safe to reuse across
    streams and across concurrent collections."""

    __slots__ = ("accumulator", "characteristics", "combiner", "finisher", "supplier")

    def __init__(
        self,
        supplier: Supplier[A],
        accumulator: BiConsumer[A, T],
        combiner: Combiner[A] | None = None,
        finisher: Finisher[A, R] | None = None,
        characteristics: Iterable[Characteristics] = _NO_CHARACTERISTICS,
    ) -> None:
        self.supplier = supplier
        self.accumulator = accumulator
        self.combiner = combiner
        self.finisher = finisher
        # Appended as the fifth parameter, after finisher, so every existing
        # positional Collector(...) call - in this library and in user code -
        # stays valid. Normalized to a frozenset regardless of what iterable
        # is passed: a Collector is spec'd reusable across concurrent
        # collections, so a mutable characteristics set would be its first
        # piece of mutable shared state.
        self.characteristics = frozenset(characteristics)


class CollectorSink(AsyncDispatch, TerminalSink[T]):
    """Adapts any Collector to the sink protocol: supplier -> container
    creation, accumulator -> accept(), finisher -> _finish(). The one
    AsyncDispatch triple here classifies the accumulator itself; a collector
    whose accumulator internally dispatches further user callables (a mapper,
    a comparator, ...) carries that classification state on its own
    supplier-made container instead, since this sink - like the Collector -
    is shared across collections."""

    def __init__(self, collector: Collector[Any, Any, Any]) -> None:
        super().__init__()
        self._collector = collector
        self._init_dispatch(collector.accumulator)

    def _create_container(self) -> Any:
        return self._collector.supplier()

    async def accept(self, element: Any) -> None:
        r = self._fn(self._container, element)
        if self._is_async:
            await cast("Awaitable[None]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                await r

    def _finish(self, container: Any) -> Any:
        finisher = self._collector.finisher
        return container if finisher is None else finisher(container)


class StreamingCollector:
    """The one collect() argument that is not a Collector: wraps a
    `(composition) -> AsyncGenerator` callable for a lazy, streaming result.
    Composed through the generator bridge rather than driven to a terminal
    sink, since a supplier/accumulator/finisher triple can only produce a
    value once the source is exhausted, and this one must not wait for
    that."""

    __slots__ = ("_fn",)

    def __init__(self, fn: Callable[[AsyncGenerator[Any, None]], AsyncGenerator[Any, None]]) -> None:
        self._fn = fn

    def __call__(self, composition: AsyncGenerator[Any, None]) -> AsyncGenerator[Any, None]:
        return self._fn(composition)


async def _stream(composition: AsyncGenerator) -> AsyncGenerator[Any, None]:
    # maybe_aclosing, not aclosing: to_generator() also accepts a plain
    # AsyncIterable with no aclose() (a custom __anext__-only iterator)
    async with maybe_aclosing(composition) as src:
        async for n in src:
            yield n


to_generator = StreamingCollector(_stream)

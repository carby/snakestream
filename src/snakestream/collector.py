"""The collector protocol: Collector, the supplier/accumulator/combiner/
finisher quadruple mirroring Java's Collector<T,A,R>; _CollectorSink, which
adapts one to the sink protocol; and StreamingCollector, the one collect()
argument that is not a Collector. The factories that build Collectors live in
collectors.py, which imports from here - never the other way round."""

from __future__ import annotations

from inspect import isawaitable
from typing import Any, Generic, cast
from collections.abc import AsyncGenerator, Awaitable, Callable

from snakestream.execution import _maybe_aclosing
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


class Collector(Generic[T, A, R]):
    """Java-style `Collector<T,A,R>`: `supplier()` creates a fresh
    accumulation container, `accumulator(container, element)` mutates it per
    element - its return value is ignored - and `finisher(container)`
    converts the finished container to the result (the container itself, if
    `finisher` is omitted). `combiner` is accepted for signature parity with
    Java and never invoked: a collection always folds over one composed
    stream, sequential or parallel, with no independently accumulated
    partitions to merge - the same posture `Stream.collect(supplier,
    accumulator, combiner)` and `reduce()`'s `combiner` already have.

    Every part may be sync or async. A `Collector` holds only these four
    callables, no per-collection state of its own, so one instance is safe to
    reuse across streams and across concurrent collections."""

    __slots__ = ("supplier", "accumulator", "combiner", "finisher")

    def __init__(
        self,
        supplier: Supplier[A],
        accumulator: BiConsumer[A, T],
        combiner: Combiner[A] | None = None,
        finisher: Finisher[A, R] | None = None,
    ) -> None:
        self.supplier = supplier
        self.accumulator = accumulator
        self.combiner = combiner
        self.finisher = finisher


class _CollectorSink(AsyncDispatch, TerminalSink[T]):
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
    # _maybe_aclosing, not aclosing: to_generator() also accepts a plain
    # AsyncIterable with no aclose() (a custom __anext__-only iterator)
    async with _maybe_aclosing(composition) as src:
        async for n in src:
            yield n


to_generator = StreamingCollector(_stream)

"""One Op plus one Sink per intermediate operation - filter, map, peek,
sorted, flat_map, distinct, limit, skip, unordered - built on the Op/Sink
protocol sink.py defines. No execution logic lives here: how a chain of these
gets driven, sequentially or racing, is execution.py's job."""

from __future__ import annotations

from contextlib import aclosing
from inspect import isawaitable
from typing import Any, cast
from collections.abc import Awaitable

from snakestream.callable_dispatch import AsyncDispatch
from snakestream.sink import (
    Box,
    IntermediateSink,
    Op,
    Ordering,
    Sink,
    StatefulOp,
    StatefulSink,
    StatelessOp,
)
from snakestream.sort import sort
from snakestream.type import (
    T,
    Comparator,
    Consumer,
    FlatMapper,
    Mapper,
    Predicate,
    StateMap,
)


class _FilterSink(AsyncDispatch, IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], predicate: Predicate) -> None:
        super().__init__(downstream)
        self._init_dispatch(predicate)

    async def accept(self, element: Any) -> None:
        keep = self._fn(element)
        if self._is_async:
            keep = await cast("Awaitable[bool]", keep)
        elif not self._checked:
            self._checked = True
            if isawaitable(keep):
                self._is_async = True
                keep = await keep
        if keep:
            await self.downstream.accept(element)


class _FilterOp(StatelessOp):
    _sink_cls = _FilterSink


class _MapSink(AsyncDispatch, IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], mapper: Mapper) -> None:
        super().__init__(downstream)
        self._init_dispatch(mapper)

    async def accept(self, element: Any) -> None:
        r = self._fn(element)
        if self._is_async:
            r = await cast("Awaitable[Any]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                r = await r
        await self.downstream.accept(r)


class _MapOp(StatelessOp):
    _sink_cls = _MapSink


class _PeekSink(AsyncDispatch, IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], consumer: Consumer) -> None:
        super().__init__(downstream)
        self._init_dispatch(consumer)

    async def accept(self, element: Any) -> None:
        r = self._fn(element)
        if self._is_async:
            await cast("Awaitable[None]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                await r
        await self.downstream.accept(element)


class _PeekOp(StatelessOp):
    _sink_cls = _PeekSink


class _SortedSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], comparator: Comparator | None, reverse: bool) -> None:
        super().__init__(downstream)
        self._comparator = comparator
        self._reverse = reverse
        self._buffer: list[Any] = []

    async def accept(self, element: Any) -> None:
        self._buffer.append(element)

    async def end(self) -> None:
        cache = self._buffer
        if self._comparator is not None:
            # sort() owns the choice between Timsort and merge_sort; which one
            # a comparator allows is sort.py's question, not this sink's.
            cache = await sort(cache, self._comparator)
        else:
            cache.sort()
        items = reversed(cache) if self._reverse else cache
        for item in items:
            await self.downstream.accept(item)
            # the whole buffer is flushed in one go, with no driving loop in
            # between to notice cancellation - so check it here, the same way
            # _FlatMapSink does between the elements of one inner stream
            if self.downstream.cancellation_requested():
                break
        await super().end()


class _SortedOp(StatelessOp):
    _sink_cls = _SortedSink
    # a sort imposes an encounter order on its output whether or not its input
    # had one, so ordering is restored downstream of it - Java's SortedOps
    # contributes IS_ORDERED for the same reason
    ordering = Ordering.SET


class _UnorderedOp(Op):
    """The one op with no sink: link() hands back the downstream untouched, so
    an _UnorderedOp in a chain costs nothing per element and cannot observe,
    transform, reorder, drop or duplicate anything. Java's unordered() is the
    same shape - a StatelessOp whose opWrapSink(flags, sink) returns sink.

    It exists purely to occupy a position in the chain and declare a
    characteristic there, which is what makes ordering positional: everything
    queued before it is unaffected, everything after it is not."""

    ordering = Ordering.CLEAR

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return downstream


class _FlatMapSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], flat_mapper: FlatMapper) -> None:
        super().__init__(downstream)
        self._flat_mapper = flat_mapper

    async def accept(self, element: Any) -> None:
        async with aclosing(self._flat_mapper(element).iterator()) as inner:
            async for j in inner:
                await self.downstream.accept(j)
                if self.downstream.cancellation_requested():
                    break


class _FlatMapOp(StatelessOp):
    _sink_cls = _FlatMapSink


class _DistinctSink(StatefulSink[T]):
    async def accept(self, element: Any) -> None:
        if element in self._state:
            return
        self._state.add(element)
        await self.downstream.accept(element)


class _DistinctOp(StatefulOp):
    _sink_cls = _DistinctSink
    order_sensitive = True

    def make_shared_state(self) -> set:
        return set()


class _LimitSink(StatefulSink[T]):
    def __init__(self, downstream: Sink[Any], op: Op, max_size: int) -> None:
        super().__init__(downstream, op)
        self._max_size = max_size
        self._cancelled = False

    async def begin(self, state_map: StateMap) -> None:
        # super() first: StatefulSink.begin() is what resolves self._state.
        # Settling the flag here rather than only in accept() is what lets a
        # limit(0) - or a branch whose shared counter is already full - report
        # cancellation before the driving loop issues its first pull.
        await super().begin(state_map)
        self._cancelled = self._state.value >= self._max_size

    async def accept(self, element: Any) -> None:
        if self._state.value >= self._max_size:
            self._cancelled = True
            return
        # reserve the slot before pushing downstream: a genuinely async
        # downstream can cede control, so checking and reserving must be
        # atomic (no await between them) to stay correct across racing
        # branches sharing self._state
        self._state.value += 1
        if self._state.value >= self._max_size:
            self._cancelled = True
        await self.downstream.accept(element)

    def cancellation_requested(self) -> bool:
        return self._cancelled or super().cancellation_requested()


class _LimitOp(StatefulOp):
    _sink_cls = _LimitSink
    order_sensitive = True

    def make_shared_state(self) -> Box:
        return Box(0)


class _SkipSink(StatefulSink[T]):
    def __init__(self, downstream: Sink[Any], op: Op, n: int) -> None:
        super().__init__(downstream, op)
        self._n = n

    async def accept(self, element: Any) -> None:
        if self._state.value < self._n:
            self._state.value += 1
            return
        await self.downstream.accept(element)


class _SkipOp(StatefulOp):
    _sink_cls = _SkipSink
    order_sensitive = True

    def make_shared_state(self) -> Box:
        return Box(0)

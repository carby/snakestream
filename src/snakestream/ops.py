"""One Op plus one Sink per intermediate operation - filter, map, peek,
sorted, flat_map, distinct, limit, skip, unordered - built on the Op/Sink
protocol sink.py defines. No execution logic lives here: how a chain of these
gets driven, sequentially or racing, is execution.py's job."""

from __future__ import annotations

import threading

from contextlib import aclosing
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any, cast
from collections.abc import Awaitable

from snakestream.callable_dispatch import AsyncDispatch, is_async_callable
from snakestream.ordering import Ordering
from snakestream.sink import (
    IntermediateSink,
    Op,
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


class _SinglePureCallableOp(StatelessOp):
    """A StatelessOp wrapping exactly one user callable at _args[0]
    (FilterOp/MapOp/PeekOp), classified once here rather than once per sink.

    Under fork/join, execution._run_element() builds a fresh sink chain per
    element - one op.link() call per element, not once per composition -
    so an ordinary StatelessOp.link() would leave AsyncDispatch._init_dispatch()
    re-running is_async_callable() on every element, violating
    callable-dispatch's "Awaitability is classified once per composition"
    requirement (measured: 1001 calls for 500 elements through map+filter,
    against 3 under the sequential executor). Awaitability is a pure function
    of the callable, and the callable is fixed for the Op's lifetime - Op
    instances are themselves reused across every composition
    (pipeline-composition) - so classifying once here, at construction, meets
    the "once per composition" bar with room to spare rather than exactly."""

    def __init__(self, fn: Any) -> None:
        super().__init__(fn)
        self._is_async = is_async_callable(fn)

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return self._sink_cls(downstream, *self._args, self._is_async)


class _FilterSink(AsyncDispatch, IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], predicate: Predicate, is_async: bool | None = None) -> None:
        super().__init__(downstream)
        self._init_dispatch(predicate, is_async)

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


class FilterOp(_SinglePureCallableOp):
    _sink_cls = _FilterSink


class _MapSink(AsyncDispatch, IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], mapper: Mapper, is_async: bool | None = None) -> None:
        super().__init__(downstream)
        self._init_dispatch(mapper, is_async)

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


class MapOp(_SinglePureCallableOp):
    _sink_cls = _MapSink


class _PeekSink(AsyncDispatch, IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], consumer: Consumer, is_async: bool | None = None) -> None:
        super().__init__(downstream)
        self._init_dispatch(consumer, is_async)

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


class PeekOp(_SinglePureCallableOp):
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
            # sort() owns the choice between Timsort and _merge_sort; which one
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


class SortedOp(StatelessOp):
    _sink_cls = _SortedSink
    # a sort imposes an encounter order on its output whether or not its input
    # had one, so ordering is restored downstream of it - Java's SortedOps
    # contributes IS_ORDERED for the same reason
    ordering = Ordering.SET


class UnorderedOp(Op):
    """The one op with no sink: link() hands back the downstream untouched, so
    an UnorderedOp in a chain costs nothing per element and cannot observe,
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


class FlatMapOp(StatelessOp):
    _sink_cls = _FlatMapSink


@dataclass(slots=True)
class _GuardedCounter:
    """LimitOp/SkipOp's shared state: a counter plus the OS-thread lock its
    read-modify-write needs when several sinks built from the same op share
    it. Under RACING that check-then-increment was atomic for free - one
    event loop, no await between the two - but under fork/join each sink
    sharing this counter runs its batch's chain on its own thread, so the
    same compound operation is a genuine data race without a real lock.
    Kept out of Box (sink.py), which collectors also build per composition
    and never share across threads - the lock would be dead weight there."""

    value: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


class _GuardedSet:
    """DistinctOp's shared state: a set plus the lock its check-then-add
    needs for the same reason _GuardedCounter's increment does."""

    __slots__ = ("_lock", "_seen")

    def __init__(self) -> None:
        self._seen: set = set()
        self._lock = threading.Lock()

    def add_if_absent(self, element: Any) -> bool:
        with self._lock:
            if element in self._seen:
                return False
            self._seen.add(element)
            return True


class _DistinctSink(StatefulSink[T]):
    async def accept(self, element: Any) -> None:
        if not self._state.add_if_absent(element):
            return
        await self.downstream.accept(element)


class DistinctOp(StatefulOp):
    _sink_cls = _DistinctSink
    order_sensitive = True

    def make_shared_state(self) -> _GuardedSet:
        return _GuardedSet()


class _LimitSink(StatefulSink[T]):
    def __init__(self, downstream: Sink[Any], op: Op, max_size: int) -> None:
        super().__init__(downstream, op)
        self._max_size = max_size
        self._cancelled = False

    async def begin(self, state_map: StateMap) -> None:
        # super() first: StatefulSink.begin() is what resolves self._state.
        # Settling the flag here rather than only in accept() is what lets a
        # limit(0) - or a branch whose shared counter is already full - report
        # cancellation before the driving loop issues its first pull. Reads
        # under the lock: another sink sharing this counter may be mutating
        # it on its own thread right now, under fork/join.
        await super().begin(state_map)
        with self._state.lock:
            self._cancelled = self._state.value >= self._max_size

    async def accept(self, element: Any) -> None:
        # reserve the slot before pushing downstream: a genuinely async
        # downstream can cede control, so checking and reserving must be
        # atomic - under a real OS-thread lock now, not just cooperative
        # scheduling, since a sink sharing self._state may run on another
        # thread entirely under fork/join
        with self._state.lock:
            if self._state.value >= self._max_size:
                self._cancelled = True
                return
            self._state.value += 1
            if self._state.value >= self._max_size:
                self._cancelled = True
        await self.downstream.accept(element)

    def cancellation_requested(self) -> bool:
        return self._cancelled or super().cancellation_requested()


class LimitOp(StatefulOp):
    _sink_cls = _LimitSink
    order_sensitive = True

    def make_shared_state(self) -> _GuardedCounter:
        return _GuardedCounter(0)


class _SkipSink(StatefulSink[T]):
    def __init__(self, downstream: Sink[Any], op: Op, n: int) -> None:
        super().__init__(downstream, op)
        self._n = n

    async def accept(self, element: Any) -> None:
        with self._state.lock:
            if self._state.value < self._n:
                self._state.value += 1
                return
        await self.downstream.accept(element)


class SkipOp(StatefulOp):
    _sink_cls = _SkipSink
    order_sensitive = True

    def make_shared_state(self) -> _GuardedCounter:
        return _GuardedCounter(0)

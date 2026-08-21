from __future__ import annotations

from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Any, cast, overload
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator

from snakestream.base_stream import BaseStream
from snakestream.callable_dispatch import _maybe_await
from snakestream.collector import Collector, StreamingCollector, _CollectorSink, to_list
from snakestream.exception import StreamBuildException
from snakestream.ops import (
    _DistinctOp,
    _FilterOp,
    _FlatMapOp,
    _LimitOp,
    _MapOp,
    _PeekOp,
    _SkipOp,
    _SortedOp,
)
from snakestream.sink import _UNSET
from snakestream.terminals import (
    _CountSink,
    _FindSink,
    _ForEachSink,
    _MatchSink,
    _MinMaxSink,
    _MutableReductionSink,
    _ReduceSink,
)
from snakestream.type import (
    R,
    T,
    Accumulator,
    BiConsumer,
    BinaryOperator,
    Comparator,
    Consumer,
    FlatMapper,
    Mapper,
    Predicate,
    Supplier,
)


if TYPE_CHECKING:
    from snakestream.stream_builder import StreamBuilder


PROCESSES: int = 4


async def _concat(a: Stream, b: Stream) -> AsyncGenerator:
    async for i in a._compose():
        yield i
    async for j in b._compose():
        yield j


class Stream(BaseStream[T]):
    @staticmethod
    def of(*args: T) -> Stream[T]:
        if len(args) == 1:
            return Stream(args[0])
        return Stream(list(args))

    @staticmethod
    def empty() -> Stream[Any]:
        return Stream([])

    @staticmethod
    def concat(a: Stream[T], b: Stream[T]) -> Stream[T]:
        new_stream = _concat(a, b)
        return Stream(new_stream)

    @staticmethod
    def builder() -> StreamBuilder:
        from snakestream.stream_builder import StreamBuilder

        return StreamBuilder()

    @staticmethod
    def iterate(seed: T, nxt: Callable[[T], T]) -> Stream[T]:
        def _make_iterator(seed: T, nxt: Callable[[T], T]) -> Generator[T, None, None]:
            yield seed
            while True:
                seed = nxt(seed)
                yield seed

        return Stream.of(_make_iterator(seed, nxt))

    # Intermediaries
    def filter(self, predicate: Predicate[T]) -> Stream[T]:
        return cast("Stream[T]", self._derive(_FilterOp(predicate)))

    def map(self, mapper: Mapper[T, R]) -> Stream[R]:
        return cast("Stream[R]", self._derive(_MapOp(mapper)))

    def flat_map(self, flat_mapper: FlatMapper[T, R]) -> Stream[R]:
        # Pre-call rejection, not a dispatch site: flat_mapper must return a
        # Stream synchronously, so an async def here is always a caller
        # mistake. This is unrelated to _maybe_await's post-call awaiting.
        if iscoroutinefunction(flat_mapper):
            raise StreamBuildException("flat_map() does not support coroutines")

        return cast("Stream[R]", self._derive(_FlatMapOp(flat_mapper)))

    def sorted(self, comparator: Comparator[T] | None = None, reverse=False) -> Stream[T]:
        return cast("Stream[T]", self._derive(_SortedOp(comparator, reverse)))

    def distinct(self) -> Stream[T]:
        return cast("Stream[T]", self._derive(_DistinctOp()))

    def peek(self, consumer: Consumer[T]) -> Stream[T]:
        return cast("Stream[T]", self._derive(_PeekOp(consumer)))

    def limit(self, max_size: int) -> Stream[T]:
        return cast("Stream[T]", self._derive(_LimitOp(max_size)))

    def skip(self, n: int) -> Stream[T]:
        return cast("Stream[T]", self._derive(_SkipOp(n)))

    # Terminals
    @overload
    def collect(self, collector: Collector[T, Any, R]) -> Coroutine[Any, Any, R]: ...

    @overload
    def collect(self, collector: StreamingCollector) -> AsyncGenerator[Any, None]: ...

    @overload
    def collect(
        self, supplier: Supplier[R], accumulator: BiConsumer[R, T], combiner: BiConsumer[R, R]
    ) -> Coroutine[Any, Any, R]: ...

    def collect(self, *args: Any) -> Any:
        self._check_not_consumed()
        if len(args) == 1:
            (collector,) = args
            if isinstance(collector, Collector):
                return self._drive_to(_CollectorSink(collector))
            if isinstance(collector, StreamingCollector):
                return collector(self._compose())
            raise StreamBuildException(
                "collect() requires a Collector (see snakestream.collector.Collector), "
                "or to_generator for a lazy, streaming result"
            )
        # 3-arg mutable reduction: supplier/accumulator, sync or async, are
        # dispatched via _maybe_await like every other user-supplied
        # callable. combiner is accepted for signature parity with Java's
        # Stream.collect(Supplier, BiConsumer, BiConsumer) but is never
        # invoked: collect() always folds over a single composed
        # AsyncGenerator, sequential or parallel, with no independently
        # accumulated partitions to merge - the same posture reduce()
        # already has under .parallel().
        supplier, accumulator, _combiner = args
        return self._collect_mutable(supplier, accumulator)

    async def _collect_mutable(self, supplier: Supplier[R], accumulator: BiConsumer[R, T]) -> R:
        # The supplier runs once per composition, so _maybe_await is the right
        # dispatch here; the per-element accumulator is specialized in the sink.
        container = await _maybe_await(supplier)
        return cast(R, await self._drive_to(_MutableReductionSink(container, accumulator)))

    @overload
    async def reduce(self, identity: T | R, accumulator: Accumulator[T, R]) -> T | R: ...

    @overload
    async def reduce(self, accumulator: BinaryOperator[T]) -> T | None: ...

    async def reduce(self, identity: Any = _UNSET, accumulator: Any = _UNSET) -> Any:
        if accumulator is _UNSET:
            # Called as reduce(accumulator): the single positional arg is the
            # accumulator, and the identity is seeded from the stream itself.
            identity, accumulator = _UNSET, identity
        return await self._drive_to(_ReduceSink(identity, accumulator))

    async def for_each(self, consumer: Consumer[T]) -> None:
        return await self._drive_to(_ForEachSink(consumer))

    async def for_each_ordered(self, consumer: Consumer[T]) -> None:
        return await self._drive_to_sequential(_ForEachSink(consumer))

    async def to_array(self) -> list[T]:
        # collect() runs _check_not_consumed() itself
        return await self.collect(to_list)

    async def find_first(self) -> T | None:
        return await self._drive_to(_FindSink())

    async def find_any(self) -> T | None:
        return await self._drive_to(_FindSink())

    async def max(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=False)

    async def min(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=True)

    async def _min_max(self, comparator: Comparator[T], asc: bool) -> T | None:
        return await self._drive_to(_MinMaxSink(comparator, asc))

    async def _match(self, predicate: Predicate[T], short_circuit_on: bool, default: bool) -> bool:
        return await self._drive_to(_MatchSink(predicate, short_circuit_on, default))

    async def all_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=False, default=True)

    async def none_match(self, predicate: Predicate[T]) -> bool:
        return not await self._match(predicate, short_circuit_on=True, default=False)

    async def any_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=True, default=False)

    async def count(self) -> int:
        return await self._drive_to(_CountSink())

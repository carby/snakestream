from __future__ import annotations

from contextlib import aclosing
from inspect import isawaitable, iscoroutinefunction
from typing import TYPE_CHECKING, Any, cast, overload
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine, Generator

from snakestream.base_stream import BaseStream
from snakestream.callable_dispatch import _maybe_await, is_async_callable
from snakestream.collector import to_list
from snakestream.exception import StreamBuildException
from snakestream.sink import IntermediateSink, Sink
from snakestream.sort import check_comparator_result_type, merge_sort
from snakestream.type import (
    R,
    T,
    Accumulator,
    BiConsumer,
    BinaryOperator,
    CloseHandler,
    Comparator,
    Consumer,
    FlatMapper,
    Mapper,
    Predicate,
    StateMap,
    Supplier,
)


if TYPE_CHECKING:
    from snakestream.stream_builder import StreamBuilder


PROCESSES: int = 4
_UNSET = object()


async def _concat(a: Stream, b: Stream) -> AsyncGenerator:
    async for i in a._compose():
        yield i
    async for j in b._compose():
        yield j


class _FilterSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], predicate: Predicate) -> None:
        super().__init__(downstream)
        self._predicate = predicate
        self._is_async = is_async_callable(predicate)
        self._checked = False

    async def accept(self, element: Any) -> None:
        keep = self._predicate(element)
        if self._is_async:
            keep = await cast("Awaitable[bool]", keep)
        elif not self._checked:
            self._checked = True
            if isawaitable(keep):
                self._is_async = True
                keep = await keep
        if keep:
            await self.downstream.accept(element)


class _FilterOp:
    def __init__(self, predicate: Predicate) -> None:
        self._predicate = predicate

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return _FilterSink(downstream, self._predicate)


class _MapSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], mapper: Mapper) -> None:
        super().__init__(downstream)
        self._mapper = mapper
        self._is_async = is_async_callable(mapper)
        self._checked = False

    async def accept(self, element: Any) -> None:
        r = self._mapper(element)
        if self._is_async:
            r = await cast("Awaitable[Any]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                r = await r
        await self.downstream.accept(r)


class _MapOp:
    def __init__(self, mapper: Mapper) -> None:
        self._mapper = mapper

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return _MapSink(downstream, self._mapper)


class _PeekSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], consumer: Consumer) -> None:
        super().__init__(downstream)
        self._consumer = consumer
        self._is_async = is_async_callable(consumer)
        self._checked = False

    async def accept(self, element: Any) -> None:
        r = self._consumer(element)
        if self._is_async:
            await cast("Awaitable[None]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                await r
        await self.downstream.accept(element)


class _PeekOp:
    def __init__(self, consumer: Consumer) -> None:
        self._consumer = consumer

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return _PeekSink(downstream, self._consumer)


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
            # Always merge_sort here rather than list.sort()+cmp_to_key: the
            # comparator may be an async-__call__ object, which needs an await
            # merge_sort's _merge already does. Trades away Timsort's speed for
            # sync comparators; see the add-maybe-await-helper design doc.
            cache = await merge_sort(cache, self._comparator)
        else:
            cache.sort()
        items = reversed(cache) if self._reverse else cache
        for item in items:
            await self.downstream.accept(item)
        await super().end()


class _SortedOp:
    def __init__(self, comparator: Comparator | None, reverse: bool) -> None:
        self._comparator = comparator
        self._reverse = reverse

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return _SortedSink(downstream, self._comparator, self._reverse)


class _FlatMapSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], flat_mapper: FlatMapper) -> None:
        super().__init__(downstream)
        self._flat_mapper = flat_mapper

    async def accept(self, element: Any) -> None:
        async with aclosing(self._flat_mapper(element)._compose()) as inner:
            async for j in inner:
                await self.downstream.accept(j)
                if self.downstream.cancellation_requested():
                    break


class _FlatMapOp:
    def __init__(self, flat_mapper: FlatMapper) -> None:
        self._flat_mapper = flat_mapper

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return _FlatMapSink(downstream, self._flat_mapper)


class _DistinctSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], op: _DistinctOp) -> None:
        super().__init__(downstream)
        self._op = op
        self._seen: set = set()

    async def begin(self, state_map: StateMap) -> None:
        self._seen = state_map[self._op] if self._op in state_map else set()
        await super().begin(state_map)

    async def accept(self, element: Any) -> None:
        if element in self._seen:
            return
        self._seen.add(element)
        await self.downstream.accept(element)


class _DistinctOp:
    def make_shared_state(self) -> set:
        return set()

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return _DistinctSink(downstream, self)


class _LimitSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], op: _LimitOp, max_size: int) -> None:
        super().__init__(downstream)
        self._op = op
        self._max_size = max_size
        self._count: list[int] = [0]
        self._cancelled = False

    async def begin(self, state_map: StateMap) -> None:
        self._count = state_map[self._op] if self._op in state_map else [0]
        await super().begin(state_map)

    async def accept(self, element: Any) -> None:
        if self._count[0] >= self._max_size:
            self._cancelled = True
            return
        # reserve the slot before pushing downstream: a genuinely async
        # downstream can cede control, so checking and reserving must be
        # atomic (no await between them) to stay correct across racing
        # branches sharing self._count
        self._count[0] += 1
        if self._count[0] >= self._max_size:
            self._cancelled = True
        await self.downstream.accept(element)

    def cancellation_requested(self) -> bool:
        return self._cancelled or super().cancellation_requested()


class _LimitOp:
    def __init__(self, max_size: int) -> None:
        self._max_size = max_size

    def make_shared_state(self) -> list[int]:
        return [0]

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return _LimitSink(downstream, self, self._max_size)


class _SkipSink(IntermediateSink[T]):
    def __init__(self, downstream: Sink[Any], op: _SkipOp, n: int) -> None:
        super().__init__(downstream)
        self._op = op
        self._n = n
        self._skipped: list[int] = [0]

    async def begin(self, state_map: StateMap) -> None:
        self._skipped = state_map[self._op] if self._op in state_map else [0]
        await super().begin(state_map)

    async def accept(self, element: Any) -> None:
        if self._skipped[0] < self._n:
            self._skipped[0] += 1
            return
        await self.downstream.accept(element)


class _SkipOp:
    def __init__(self, n: int) -> None:
        self._n = n

    def make_shared_state(self) -> list[int]:
        return [0]

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return _SkipSink(downstream, self, self._n)


class Stream(BaseStream[T]):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        super().__init__(source, close_handlers)

    @staticmethod
    def of(*args: T) -> Stream[T]:
        if len(args) == 1:
            return Stream(args[0])
        return Stream(list(args))

    @staticmethod
    def empty() -> Stream[Any]:
        return Stream([])

    @staticmethod
    async def concat(a: Stream[T], b: Stream[T]) -> Stream[T]:
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
    def collect(self, collector: Callable[[AsyncGenerator[T, None]], R]) -> R: ...

    @overload
    def collect(
        self, supplier: Supplier[R], accumulator: BiConsumer[R, T], combiner: BiConsumer[R, R]
    ) -> Coroutine[Any, Any, R]: ...

    def collect(self, *args: Any) -> Any:
        self._check_not_consumed()
        if len(args) == 1:
            (collector,) = args
            return collector(self._compose())
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
        container = await _maybe_await(supplier)
        is_async = is_async_callable(accumulator)
        checked = False
        async for n in self._compose():
            r = accumulator(container, n)
            if is_async:
                await cast("Awaitable[None]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    await r
        return container

    @overload
    async def reduce(self, identity: T | R, accumulator: Accumulator[T, R]) -> T | R: ...

    @overload
    async def reduce(self, accumulator: BinaryOperator[T]) -> T | None: ...

    async def reduce(self, identity: Any = _UNSET, accumulator: Any = _UNSET) -> Any:
        self._check_not_consumed()
        if accumulator is _UNSET:
            # Called as reduce(accumulator): the single positional arg is the
            # accumulator, and the identity is seeded from the stream itself.
            identity, accumulator = _UNSET, identity

        composed = self._compose()
        if identity is _UNSET:
            try:
                identity = await anext(composed)
            except StopAsyncIteration:
                return None

        is_async = is_async_callable(accumulator)
        checked = False
        async for n in composed:
            r = accumulator(identity, n)
            if is_async:
                r = await cast("Awaitable[Any]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            identity = r
        return identity

    async def for_each(self, consumer: Consumer[T]) -> None:
        self._check_not_consumed()
        is_async = is_async_callable(consumer)
        checked = False
        async for n in self._compose():
            r = consumer(n)
            if is_async:
                await cast("Awaitable[None]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    await r
        return None

    async def for_each_ordered(self, consumer: Consumer[T]) -> None:
        self._check_not_consumed()
        is_async = is_async_callable(consumer)
        checked = False
        async for n in self._drive(self._chain[:], self._stream):
            r = consumer(n)
            if is_async:
                await cast("Awaitable[None]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    await r
        return None

    async def to_array(self) -> list[T]:
        self._check_not_consumed()
        return await self.collect(to_list)

    async def find_first(self) -> T | None:
        self._check_not_consumed()
        async for n in self._compose():
            return n
        return None

    async def find_any(self) -> T | None:
        self._check_not_consumed()
        async for n in self._compose():
            return n

    async def max(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=False)

    async def min(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=True)

    async def _min_max(self, comparator: Comparator[T], asc: bool) -> T | None:
        self._check_not_consumed()

        is_async = is_async_callable(comparator)
        checked = False

        async def compare(a: T, b: T) -> int:
            nonlocal is_async, checked
            sign = comparator(a, b)
            if is_async:
                sign = await cast("Awaitable[int]", sign)
            elif not checked:
                checked = True
                if isawaitable(sign):
                    is_async = True
                    sign = await sign
            sign = cast(int, sign)
            check_comparator_result_type(sign)
            return sign

        found = cast(T, _UNSET)
        async for n in self._compose():
            if found is _UNSET:
                found = n
                continue

            # comparator(n, found): negative if n orders before found, positive
            # if after. found (the earlier element) is kept on a tie.
            sign = await compare(n, found)
            if asc:
                is_new_extreme = sign < 0
            else:
                is_new_extreme = sign > 0
            if is_new_extreme:
                found = n
        return None if found is _UNSET else found

    async def _match(self, predicate: Predicate[T], short_circuit_on: bool, default: bool) -> bool:
        self._check_not_consumed()
        is_async = is_async_callable(predicate)
        checked = False
        async for n in self._compose():
            r = predicate(n)
            if is_async:
                r = await cast("Awaitable[bool]", r)
            elif not checked:
                checked = True
                if isawaitable(r):
                    is_async = True
                    r = await r
            if bool(r) is short_circuit_on:
                return short_circuit_on
        return default

    async def all_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=False, default=True)

    async def none_match(self, predicate: Predicate[T]) -> bool:
        return not await self._match(predicate, short_circuit_on=True, default=False)

    async def any_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=True, default=False)

    async def count(self) -> int:
        self._check_not_consumed()
        c = 0
        async for _ in self._compose():
            c += 1
        return c

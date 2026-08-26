from __future__ import annotations

import sys
from inspect import isawaitable, iscoroutinefunction
from typing import TYPE_CHECKING, Any, Generic, cast, overload
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Coroutine, Iterable

from snakestream.callable_dispatch import _maybe_await, is_async_callable
from snakestream.collector import Collector, StreamingCollector, _CollectorSink
from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException, StreamBuildException
from snakestream.execution import PROCESSES as PROCESSES, RACING, SEQUENTIAL, Executor
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
from snakestream.sink import _UNSET, Op, TerminalSink
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
    CloseHandler,
    Comparator,
    Consumer,
    FlatMapper,
    Mapper,
    Predicate,
    Supplier,
)


if TYPE_CHECKING:
    from snakestream.stream_builder import StreamBuilder


async def _normalize(source: Any) -> AsyncGenerator:
    # The scalar set, and the complete set of exceptions to the spreading
    # below. It stays first in the ladder so a bytearray never reaches the
    # Iterable branch. The three binary types are here together on purpose:
    # whether a buffer of bytes is immutable, mutable or a view over another
    # buffer should not change how many elements it produces.
    if isinstance(source, (dict, str, bytes, bytearray, memoryview)):
        yield source
    elif isinstance(source, Iterable):
        for i in source:
            yield i
    elif hasattr(source, "__next__"):
        # A bare sync iterator, implementing only __next__. This one stays a
        # hasattr where the branch above became an ABC check: Iterator's
        # __subclasshook__ requires *both* __iter__ and __next__, so an object
        # with only __next__ is neither Iterable nor Iterator, and
        # isinstance(source, Iterator) here would reintroduce the bug fixed at
        # 3554cc1. It can't be driven with `for`, and StopIteration must not
        # escape: PEP 479 turns one raised inside an async generator into
        # RuntimeError. Only the next() call is guarded, so a StopIteration
        # thrown in at the yield still propagates to the caller rather than
        # silently ending the stream.
        while True:
            try:
                i = next(source)
            except StopIteration:
                return
            yield i
    else:
        yield source


def _accept(source: Any) -> AsyncGenerator | None:
    # one question, not two: AsyncGenerator is a subclass of AsyncIterable, so
    # the narrower check could never be the deciding one. Everything accepted
    # here is passed through untouched, so the consuming side must not assume
    # more than __aiter__ (see execution._guarded).
    if isinstance(source, AsyncIterable):
        return source
    return None


async def _concat(a: Stream, b: Stream) -> AsyncGenerator:
    async for i in a._compose():
        yield i
    async for j in b._compose():
        yield j


class Stream(Generic[T]):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        self._source: AsyncGenerator[T, None] = _accept(source) or _normalize(source)
        self._chain: list[Op] = []
        self._close_handlers: list[CloseHandler] = [] if close_handlers is None else close_handlers
        self._ordered: bool = True
        self._consumed: bool = False
        self._executor: Executor = SEQUENTIAL

    def _check_not_consumed(self) -> None:
        if self._consumed:
            raise IllegalStateException("this stream has already been extended into a new instance")

    def _derive(self, chain: list[Op], executor: Executor) -> Stream[Any]:
        self._check_not_consumed()
        new_stream = type(self)(self._source, self._close_handlers)
        new_stream._chain = chain
        new_stream._ordered = self._ordered
        new_stream._executor = executor
        self._consumed = True
        return new_stream

    def _extend(self, op: Op) -> Stream[Any]:
        """This stream's chain plus one more op, under the same executor.
        The chain-extension rule lives here and nowhere else; _derive() runs
        the consumed check, so this deliberately does not."""
        return self._derive(self._chain + [op], self._executor)

    def _compose(self) -> AsyncGenerator[T, None]:
        """The chain as a generator, under this stream's executor."""
        return self._executor.elements(self._chain, self._source)

    async def _evaluate(self, terminal: TerminalSink[Any], executor: Executor | None = None) -> Any:
        """The chain driven into a terminal sink. The one place a stream's
        execution mode is consulted; a terminal that needs encounter order
        regardless of the stream's mode passes SEQUENTIAL itself."""
        self._check_not_consumed()
        return await (executor or self._executor).value(self._chain, self._source, terminal)

    def _derive_executor(self, executor: Executor) -> Stream[T]:
        """A mode switch: a new stream over the SAME source and the SAME queued
        chain, differing only in its executor, consuming this one.

        It must not compose. Composing here is what made `.parallel()`
        position-dependent — ops queued before the switch were frozen under the
        old mode — where Java's `parallel()` sets a flag on the source stage and
        so governs the whole pipeline wherever it appears.

        It must not assign onto self and return self either, however tempting:
        pipeline-immutability requires the receiver be invalidated, and an
        in-place flip would leave it usable."""
        return cast("Stream[T]", self._derive(self._chain, executor))

    def sequential(self) -> Stream[T]:
        """This pipeline under SEQUENTIAL; see _derive_executor()."""
        return self._derive_executor(SEQUENTIAL)

    def parallel(self) -> Stream[T]:
        """This pipeline under RACING; see _derive_executor()."""
        return self._derive_executor(RACING)

    def iterator(self) -> AsyncGenerator[T, None]:
        self._check_not_consumed()
        return self._compose()

    def unordered(self) -> Stream[T]:
        """Mutates and returns self, unlike the eight derive-and-consume
        intermediate ops - deliberate, per the stream-ordering spec."""
        self._ordered = False
        return self

    def is_ordered(self) -> bool:
        return self._ordered

    def on_close(self, close_handler: CloseHandler) -> Stream[T]:
        """Mutates and returns self, unlike the eight derive-and-consume
        intermediate ops - deliberate, per pipeline-immutability spec line 58."""
        self._close_handlers.append(close_handler)
        return self

    def close(self) -> None:
        exceptions: list[Exception] = []
        for close_handler in self._close_handlers:
            try:
                close_handler()
            except Exception as e:
                exceptions.append(e)
        if exceptions:
            first = exceptions[0]
            if sys.version_info >= (3, 11):
                for later in exceptions[1:]:
                    first.add_note(f"close() also raised: {later!r}")
            raise first

    def is_parallel(self) -> bool:
        return self._executor.is_parallel

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
        return Stream(new_stream, a._close_handlers + b._close_handlers)

    @staticmethod
    def builder() -> StreamBuilder:
        from snakestream.stream_builder import StreamBuilder

        return StreamBuilder()

    @staticmethod
    def iterate(seed: T, nxt: Mapper[T, T]) -> Stream[T]:
        async def _make_iterator(seed: T, nxt: Mapper[T, T]) -> AsyncGenerator[T, None]:
            is_async = is_async_callable(nxt)
            checked = False
            yield seed
            while True:
                r = nxt(seed)
                if is_async:
                    r = await cast("Awaitable[T]", r)
                elif not checked:
                    checked = True
                    if isawaitable(r):
                        is_async = True
                        r = await r
                seed = cast(T, r)
                yield seed

        return Stream.of(_make_iterator(seed, nxt))

    # Intermediaries
    def filter(self, predicate: Predicate[T]) -> Stream[T]:
        return self._extend(_FilterOp(predicate))

    def map(self, mapper: Mapper[T, R]) -> Stream[R]:
        return self._extend(_MapOp(mapper))

    def flat_map(self, flat_mapper: FlatMapper[T, R]) -> Stream[R]:
        # Pre-call rejection, not a dispatch site: flat_mapper must return a
        # Stream synchronously, so an async def here is always a caller
        # mistake. This is unrelated to _maybe_await's post-call awaiting.
        if iscoroutinefunction(flat_mapper):
            raise StreamBuildException("flat_map() does not support coroutines")

        return self._extend(_FlatMapOp(flat_mapper))

    def sorted(self, comparator: Comparator[T] | None = None, reverse: bool = False) -> Stream[T]:
        return self._extend(_SortedOp(comparator, reverse))

    def distinct(self) -> Stream[T]:
        return self._extend(_DistinctOp())

    def peek(self, consumer: Consumer[T]) -> Stream[T]:
        return self._extend(_PeekOp(consumer))

    def limit(self, max_size: int) -> Stream[T]:
        return self._extend(_LimitOp(max_size))

    def skip(self, n: int) -> Stream[T]:
        return self._extend(_SkipOp(n))

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
                return self._evaluate(_CollectorSink(collector))
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
        return cast(R, await self._evaluate(_MutableReductionSink(container, accumulator)))

    @overload
    async def reduce(self, identity: T | R, accumulator: Accumulator[T, R]) -> T | R: ...

    @overload
    async def reduce(self, accumulator: BinaryOperator[T]) -> T | None: ...

    async def reduce(self, identity: Any = _UNSET, accumulator: Any = _UNSET) -> Any:
        if accumulator is _UNSET:
            # Called as reduce(accumulator): the single positional arg is the
            # accumulator, and the identity is seeded from the stream itself.
            identity, accumulator = _UNSET, identity
        return await self._evaluate(_ReduceSink(identity, accumulator))

    async def for_each(self, consumer: Consumer[T]) -> None:
        return await self._evaluate(_ForEachSink(consumer))

    async def for_each_ordered(self, consumer: Consumer[T]) -> None:
        return await self._evaluate(_ForEachSink(consumer), SEQUENTIAL)

    async def to_array(self) -> list[T]:
        # collect() runs _check_not_consumed() itself
        return await self.collect(to_list())

    async def find_first(self) -> T | None:
        # ordered means encounter order regardless of executor, so this one
        # names SEQUENTIAL itself instead of following self._executor
        if not self.is_ordered():
            return await self.find_any()
        return await self._evaluate(_FindSink(), SEQUENTIAL)

    async def find_any(self) -> T | None:
        return await self._evaluate(_FindSink())

    async def max(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=False)

    async def min(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=True)

    async def _min_max(self, comparator: Comparator[T], asc: bool) -> T | None:
        return await self._evaluate(_MinMaxSink(comparator, asc))

    async def _match(self, predicate: Predicate[T], short_circuit_on: bool, default: bool) -> bool:
        return await self._evaluate(_MatchSink(predicate, short_circuit_on, default))

    async def all_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=False, default=True)

    async def none_match(self, predicate: Predicate[T]) -> bool:
        return not await self._match(predicate, short_circuit_on=True, default=False)

    async def any_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=True, default=False)

    async def count(self) -> int:
        return await self._evaluate(_CountSink())

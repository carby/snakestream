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
    _UnorderedOp,
)
from snakestream.sink import _UNSET, Op, TerminalSink, is_ordered
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


async def _concat(a: AsyncGenerator, b: AsyncGenerator) -> AsyncGenerator:
    async for i in a:
        yield i
    async for j in b:
        yield j


class Stream(Generic[T]):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        self._source: AsyncGenerator[T, None] = _accept(source) or _normalize(source)
        self._chain: list[Op] = []
        self._close_handlers: list[CloseHandler] = [] if close_handlers is None else close_handlers
        self._consumed: bool = False
        self._executor: Executor = SEQUENTIAL

    def _check_not_consumed(self) -> None:
        if self._consumed:
            raise IllegalStateException("this stream has already been extended into a new instance")

    def _derive(self, op: Op | None = None) -> Stream[Any]:
        """A new stream over the same source, carrying this stream's chain plus
        `op`, under the same executor, consuming this one. The
        chain-extension rule lives here and nowhere else. Called with no op it
        is a plain copy, which is what a mode switch derives from."""
        self._check_not_consumed()
        new_stream = type(self)(self._source, self._close_handlers)
        new_stream._chain = [*self._chain, op] if op is not None else self._chain
        new_stream._executor = self._executor
        self._consumed = True
        return new_stream

    async def _evaluate(self, terminal: TerminalSink[Any], executor: Executor | None = None) -> Any:
        """The chain driven into a terminal sink. The one place a stream's
        execution mode is consulted; a terminal that needs encounter order
        regardless of the stream's mode passes SEQUENTIAL itself."""
        self._check_not_consumed()
        return await (executor or self._executor).value(self._chain, self._source, terminal)

    def sequential(self) -> Stream[T]:
        """This pipeline under SEQUENTIAL: a new stream over the SAME source and
        the SAME queued chain, differing only in its executor, consuming this
        one. The chain carrying over unchanged is also what carries the ordering
        characteristic over - _is_ordered() folds it from there, so there is no
        ordering state for this to copy.

        A mode switch must not compose - _derive() does not, and composing here
        is what made `.parallel()` position-dependent, freezing ops queued
        before the switch under the old mode, where Java's `parallel()` sets a
        flag on the source stage and so governs the whole pipeline wherever it
        appears.

        It must not assign onto self and return self either, however tempting -
        and the body below is one line away from doing exactly that:
        pipeline-immutability requires the receiver be invalidated, and an
        in-place flip would leave it usable."""
        derived = self._derive()
        derived._executor = SEQUENTIAL
        return derived

    def parallel(self) -> Stream[T]:
        """This pipeline under RACING; see sequential(), which carries the rules
        both mode switches obey."""
        derived = self._derive()
        derived._executor = RACING
        return derived

    def iterator(self) -> AsyncGenerator[T, None]:
        self._check_not_consumed()
        return self._executor.elements(self._chain, self._source)

    def unordered(self) -> Stream[T]:
        """Queues an op that clears encounter order for everything after it,
        and nothing else - see _UnorderedOp, which links to no sink at all.
        Being an op is what makes this positional: Java's unordered() is a
        pipeline stage for the same reason, the deliberate opposite of its
        parallel(), which sets a flag on the source stage so as *not* to be."""
        return self._derive(_UnorderedOp())

    def _is_ordered(self) -> bool:
        """Folded from the chain, never stored. Java's combineOpFlags() folds
        the same three-valued answer down its stage list; here the fold is the
        whole of it, because there is one characteristic rather than five.

        Private because Java exposes no ordering accessor: BaseStream offers
        isParallel() and nothing else, and ORDERED lives in the package-private
        StreamOpFlag. A caller influences ordering through unordered() and
        sorted(), and observes it through what the order-sensitive terminals do.

        The fold itself lives in sink.py, where execution.py can reach it too;
        this method is what keeps the characteristic off the public surface."""
        return is_ordered(self._chain)

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
            except Exception as e:  # noqa: PERF203
                # PERF203 objects to try/except inside a loop; here that is the
                # loop's contract. close() invokes *every* registered handler
                # (stream-close-handling spec), so a raising handler must be
                # caught per iteration rather than aborting the rest.
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
        new_stream = _concat(a.iterator(), b.iterator())
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
        return self._derive(_FilterOp(predicate))

    def map(self, mapper: Mapper[T, R]) -> Stream[R]:
        return self._derive(_MapOp(mapper))

    def flat_map(self, flat_mapper: FlatMapper[T, R]) -> Stream[R]:
        # Pre-call rejection, not a dispatch site: flat_mapper must return a
        # Stream synchronously, so an async def here is always a caller
        # mistake. This is unrelated to _maybe_await's post-call awaiting.
        if iscoroutinefunction(flat_mapper):
            raise StreamBuildException("flat_map() does not support coroutines")

        return self._derive(_FlatMapOp(flat_mapper))

    def sorted(self, comparator: Comparator[T] | None = None, reverse: bool = False) -> Stream[T]:
        return self._derive(_SortedOp(comparator, reverse))

    def distinct(self) -> Stream[T]:
        return self._derive(_DistinctOp())

    def peek(self, consumer: Consumer[T]) -> Stream[T]:
        return self._derive(_PeekOp(consumer))

    def limit(self, max_size: int) -> Stream[T]:
        return self._derive(_LimitOp(max_size))

    def skip(self, n: int) -> Stream[T]:
        return self._derive(_SkipOp(n))

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
                return collector(self.iterator())
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
        """Encounter order costs the racing executor, so it is only paid when
        the pipeline is ordered; an unordered one runs under whatever executor
        the stream carries and is then just for_each(). Java splits the same
        way - ForEachOps.OfRef.evaluateParallel() picks ForEachOrderedTask or
        plain ForEachTask on whether ORDERED is known upstream - and it is what
        the javadoc's "if the stream has a defined encounter order" means."""
        executor = SEQUENTIAL if self._is_ordered() else None
        return await self._evaluate(_ForEachSink(consumer), executor)

    async def to_array(self) -> list[T]:
        # collect() runs _check_not_consumed() itself
        return await self.collect(to_list())

    async def find_first(self) -> T | None:
        # encounter order regardless of executor *and* regardless of ordering,
        # so this one names SEQUENTIAL itself instead of following
        # self._executor, and does not branch. Java does not relax findFirst()
        # on an unordered stream either: FindOp.mustFindFirst is fixed when the
        # op is constructed and FindTask does its leftmost scan whenever it is
        # set, never consulting upstream ORDERED. The javadoc permits returning
        # any element there; the implementation declines to. find_any() is
        # where a caller who wants the race goes.
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

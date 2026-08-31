from __future__ import annotations

import sys
from inspect import isawaitable, iscoroutinefunction
from typing import TYPE_CHECKING, Any, Generic, cast, overload
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Coroutine, Iterable

from snakestream.callable_dispatch import _maybe_await, is_async_callable
from snakestream.collector import Characteristics, Collector, StreamingCollector, _CollectorSink
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

    def _derive(self, op: Op | None = None, executor: Executor | None = None) -> Stream[Any]:
        """A new stream over the same source, carrying this stream's chain plus
        `op`, under `executor`, consuming this one. Both derivation rules live
        here and nowhere else. Called with no op it is a plain copy, which is
        what a mode switch derives from - and on that no-op path the chain
        passes through by identity rather than being copied, safe only because
        the receiver is consumed on the way out and chains are only ever
        extended by copy. Called with no executor the receiver's carries
        over."""
        self._check_not_consumed()
        new_stream = type(self)(self._source, self._close_handlers)
        new_stream._chain = [*self._chain, op] if op is not None else self._chain
        new_stream._executor = executor or self._executor
        self._consumed = True
        return new_stream

    async def _evaluate(self, terminal: TerminalSink[Any], observes_order: bool, executor: Executor | None = None) -> Any:
        """The chain driven into a terminal sink. The one place a stream's
        execution mode is consulted; a terminal that needs encounter order
        regardless of the stream's mode passes SEQUENTIAL itself.

        `observes_order` is required rather than defaulted because it is a
        claim about the terminal, and only the terminal can make it. A default
        would let a new terminal inherit an answer nobody chose - silently
        buying a reorder barrier it does not need, or silently going without
        one it does. It is the same posture find_first() takes with its
        executor, on the other axis."""
        self._check_not_consumed()
        return await (executor or self._executor).value(self._chain, self._source, terminal, observes_order)

    def sequential(self) -> Stream[T]:
        """This pipeline under SEQUENTIAL.

        A mode switch must not compose - _derive() does not, and composing here
        is what made `.parallel()` position-dependent, freezing ops queued
        before the switch under the old mode, where Java's `parallel()` sets a
        flag on the source stage and so governs the whole pipeline wherever it
        appears.

        It must not assign onto self and return self either, however tempting -
        pipeline-immutability requires the receiver be invalidated, and an
        in-place flip would leave it usable."""
        return self._derive(executor=SEQUENTIAL)

    def parallel(self) -> Stream[T]:
        """This pipeline under RACING; see sequential(), which carries the rules
        both mode switches obey.

        An ordered pipeline still delivers in encounter order: every op races
        and only the handing over is reordered. unordered() opts out of that
        and of the barrier an order-sensitive op needs; see its docstring."""
        return self._derive(executor=RACING)

    def iterator(self) -> AsyncGenerator[T, None]:
        self._check_not_consumed()
        # hands raw elements to the caller, so the order they arrive in is
        # definitionally observable - there is no way for this one to say no.
        # collect(to_generator) and Stream.concat() compose through here and
        # inherit the answer.
        return self._executor.elements(self._chain, self._source, True)

    def unordered(self) -> Stream[T]:
        """Queues an op that clears encounter order for everything after it,
        and nothing else - see _UnorderedOp, which links to no sink at all.
        Being an op is what makes this positional: Java's unordered() is a
        pipeline stage for the same reason, the deliberate opposite of its
        parallel(), which sets a flag on the source stage so as *not* to be.

        Under RACING this is the performance lever, and it is the primary way
        to buy concurrency back. An ordered racing pipeline holds a finished
        element until every earlier one has been released - for an operation
        that reads position, and for delivery to a terminal that observes
        order. Clearing the characteristic removes both."""
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
        """Every element of `a` then every element of `b`, carrying forward what
        both operands knew about themselves.

        Java's one sentence is the whole contract: the result "is ordered if
        both of the input streams are ordered, and parallel if either of the
        input streams is parallel". The two halves arrive by different
        mechanisms, and the asymmetry is the same one stream-ordering already
        documents rather than a new one - mode is a value on the stream and so
        is assigned, ordering is positional and so has to occupy a position.
        That is what the unordered() call below is: a stage this concatenation
        introduces on the caller's behalf, not a stage the caller wrote. It is
        also the only mechanism available, pipeline-immutability requiring that
        the ordering characteristic not be carried as state beside the chain.

        Both operands are consumed. concat() links their pipelines into the
        result, so they are superseded exactly as a receiver is superseded by an
        intermediate op called on it - and Java's AbstractPipeline marks them
        the same way. Leaving them live was a silent wrong answer rather than a
        lenient one: an operand and the concatenation draw on one source, so
        draining the operand afterwards removed elements from the
        concatenation's output with no signal at all.

        The result is a plain `Stream` even when both operands share a subclass.
        `type(a)` and `type(b)` may differ with no principled tie-break, and a
        subclass constructor may want arguments concat() has no way to supply;
        Java returns an internal type for the same reason. See the stream-concat
        capability, which specifies this as a decision rather than leaving the
        next reader to guess it was one."""
        # eager: the argument expressions run here, so an already-extended
        # operand raises at call time rather than at the first pull.
        new_stream = _concat(a.iterator(), b.iterator())
        concatenated = Stream(new_stream, a._close_handlers + b._close_handlers)
        concatenated._executor = RACING if a.is_parallel() or b.is_parallel() else SEQUENTIAL
        if not (a._is_ordered() and b._is_ordered()):
            concatenated = concatenated.unordered()
        a._consumed = b._consumed = True
        return concatenated

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
                # the collector answers for itself: UNORDERED is the declaration
                # that any ordering of the same elements collects to an equal
                # result, which is exactly the question the barrier asks.
                observes_order = Characteristics.UNORDERED not in collector.characteristics
                return self._evaluate(_CollectorSink(collector), observes_order)
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
        # an arbitrary user accumulator folding into an arbitrary container:
        # nothing here says the result is order-independent, so it is not
        # assumed to be. The Collector form has UNORDERED to say otherwise;
        # this form has no way to.
        return cast(R, await self._evaluate(_MutableReductionSink(container, accumulator), True))

    @overload
    async def reduce(self, identity: T | R, accumulator: Accumulator[T, R]) -> T | R: ...

    @overload
    async def reduce(self, accumulator: BinaryOperator[T]) -> T | None: ...

    async def reduce(self, identity: Any = _UNSET, accumulator: Any = _UNSET) -> Any:
        if accumulator is _UNSET:
            # Called as reduce(accumulator): the single positional arg is the
            # accumulator, and the identity is seeded from the stream itself.
            identity, accumulator = _UNSET, identity
        # the accumulator is not required to be associative or commutative
        # here, so the fold is over encounter order or it is over nothing
        return await self._evaluate(_ReduceSink(identity, accumulator), True)

    async def for_each(self, consumer: Consumer[T]) -> None:
        # explicitly order-blind, as Java's forEach() is: for_each_ordered() is
        # the one that promises encounter order, and this is what it costs less
        # than
        return await self._evaluate(_ForEachSink(consumer), False)

    async def for_each_ordered(self, consumer: Consumer[T]) -> None:
        """Encounter order costs the racing executor, so it is only paid when
        the pipeline is ordered; an unordered one runs under whatever executor
        the stream carries and is then just for_each(). Java splits the same
        way - ForEachOps.OfRef.evaluateParallel() picks ForEachOrderedTask or
        plain ForEachTask on whether ORDERED is known upstream - and it is what
        the javadoc's "if the stream has a defined encounter order" means."""
        executor = SEQUENTIAL if self._is_ordered() else None
        # True on both branches, and free on both: SEQUENTIAL ignores it, and
        # the branch that does not name SEQUENTIAL is the unordered one, where
        # the pipeline carries no requirement for a barrier to restore
        return await self._evaluate(_ForEachSink(consumer), True, executor)

    async def to_array(self) -> list[T]:
        # collect() runs _check_not_consumed() itself, and to_list() declares no
        # characteristics, so this observes encounter order through it
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
        return await self._evaluate(_FindSink(), True, SEQUENTIAL)

    async def find_any(self) -> T | None:
        # the whole point of it: any element will do, so no barrier is owed
        return await self._evaluate(_FindSink(), False)

    async def max(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=False)

    async def min(self, comparator: Comparator[T]) -> T | None:
        return await self._min_max(comparator, asc=True)

    async def _min_max(self, comparator: Comparator[T], asc: bool) -> T | None:
        # the *value* is the same in any order, but which of two equal-comparing
        # distinguishable elements is returned is not, and comparator-contract
        # requires the first in encounter order. Hence True, not False: this is
        # the one place a fold's identity depends on delivery order. It buys the
        # cheapest split there is - at len(chain), so every op still races and
        # only the handing over is ordered - and unordered() releases it, which
        # is where a caller who would rather have the concurrency goes.
        return await self._evaluate(_MinMaxSink(comparator, asc), True)

    async def _match(self, predicate: Predicate[T], short_circuit_on: bool, default: bool) -> bool:
        # a predicate over the whole stream has one answer whatever the order
        return await self._evaluate(_MatchSink(predicate, short_circuit_on, default), False)

    async def all_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=False, default=True)

    async def none_match(self, predicate: Predicate[T]) -> bool:
        return not await self._match(predicate, short_circuit_on=True, default=False)

    async def any_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=True, default=False)

    async def count(self) -> int:
        return await self._evaluate(_CountSink(), False)

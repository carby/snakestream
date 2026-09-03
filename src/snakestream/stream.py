from __future__ import annotations

import sys
from copy import copy
from inspect import isawaitable, iscoroutinefunction
from typing import TYPE_CHECKING, Any, Generic, cast, overload
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Coroutine, Iterable

from snakestream.callable_dispatch import is_async_callable
from snakestream.collector import Characteristics, Collector, CollectorSink, StreamingCollector
from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException, StreamBuildException
from snakestream.execution import RACING, SEQUENTIAL, Executor
from snakestream.ops import (
    DistinctOp,
    FilterOp,
    FlatMapOp,
    LimitOp,
    MapOp,
    PeekOp,
    SkipOp,
    SortedOp,
    UnorderedOp,
)
from snakestream.ordering import OrderDemand, is_ordered
from snakestream.sink import UNSET, Op, TerminalSink
from snakestream.terminals import (
    CountSink,
    FindSink,
    ForEachSink,
    MatchSink,
    MinMaxSink,
    ReduceSink,
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

    # --- Python's data model ------------------------------------------------
    #
    # Which protocols a Stream satisfies is decided almost entirely by being
    # async-first: every terminal here is a coroutine, and most of Python's
    # data model demands a value synchronously. What is implemented below is
    # the part that does not - the async iteration hook, the two lifecycle
    # protocols, and one operator. __len__, __iter__, __contains__,
    # __getitem__, __reversed__ and __eq__ are deliberately absent; see the
    # python-data-model capability, which records that as a decision.
    #
    # __getitem__ is the one that could have worked - s[10:20] is lazy and
    # returns a Stream - and is excluded on a mechanical hazard rather than on
    # taste: Python synthesizes an iterator from __getitem__ when __iter__ is
    # absent, so defining it would make `for x in stream` appear to work,
    # calling stream[0], receiving a Stream, and looping forever. Anyone adding
    # it must add __iter__ raising in the same change, never after.

    def __aiter__(self) -> AsyncGenerator[T, None]:
        """`async for element in stream`, equivalent to iterating iterator().

        Delegates rather than reimplements, so the stream-iterator capability
        governs it whole: composition without pulling, the caller driving, the
        non-destructive composition that leaves this instance usable, and the
        declaration that arrival order is observable - so an ordered racing
        stream yields in encounter order here exactly as it does there."""
        return self.iterator()

    def __enter__(self) -> Stream[T]:
        """`with stream as s:`, so the AutoClose equivalent needs no wrapper.

        Java's BaseStream extends AutoCloseable and its streams sit in
        try-with-resources directly; ours has needed contextlib.closing(),
        which is a wrapper standing in for two methods. closing() still works
        and is still what CLAUDE.md's older examples use."""
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Closes, and suppresses nothing - returning None lets an exception
        from the body propagate. Every stream-close-handling rule applies
        unchanged, because this calls close() rather than restating it."""
        self.close()

    def __repr__(self) -> str:
        """Type, queued chain and execution mode, pulling nothing.

        The source is deliberately absent: it is an AsyncGenerator whose own
        repr says nothing a reader wants and can be arbitrarily noisy. Must not
        raise in any state - a debugger or an exception formatter may render a
        stream that has been extended or consumed."""
        mode = "parallel" if self._executor.is_parallel else "sequential"
        return f"<{type(self).__name__} [{', '.join(map(repr, self._chain))}] {mode}>"

    def __bool__(self) -> bool:
        """Raises. There is no correct synchronous answer.

        Whether a stream is empty can only be found by consuming it, and
        consumption is asynchronous - so without this, object.__bool__ applies
        and every Stream is truthy, an empty one included. `if stream:` then
        answers a question the caller plainly meant to ask, and answers it
        wrong, silently, every time.

        This is the one place the library refuses something Python allows on
        every other object. A loud refusal beats a silent wrong answer, and the
        message has to name the async alternative or the caller is no better
        off than the wrong True left them.

        The precedent being broken is worth naming, because it is CPython's
        own: a generator, an async generator, map, filter, zip and a bare
        iterator all define neither __bool__ nor __len__, so an empty one and
        an exhausted one are alike truthy. range is the exception that states
        the rule - it is the one lazy builtin that knows its size without
        pulling, and the one that answers honestly. We side instead with numpy
        and pandas, which raise rather than let bool() mislead.

        Shape is what earns the deviation, not asyncness. Nobody writing
        `if gen:` believes they asked about contents; a generator advertises
        itself as a one-shot cursor. A Stream presents as a collection -
        of(), count(), to_list(), collect() - so the collection reflex fires
        and the wrong True is believed. filter() alone would justify this in a
        synchronous port: being async is why the answer cannot be given, being
        collection-shaped is why it must not be given wrong."""
        raise TypeError(
            "a Stream has no truth value: whether it is empty can only be "
            "answered by consuming it, which is asynchronous. Await "
            "count(), any_match(...) or find_any() instead."
        )

    def __add__(self, other: Any) -> Stream[Any]:
        """`a + b` is Stream.concat(a, b).

        The one member of this group with no Java counterpart, and a deliberate
        expansion rather than a parity fix. concat() stays the contract: this
        delegates and adds nothing, so everything the stream-concat capability
        decides - elements and their order, laziness, close handlers, execution
        mode, ordering, concrete type, and the invalidation of both operands -
        is decided there and not here.

        A non-Stream operand gets NotImplemented rather than being coerced, so
        Python raises its own TypeError and `a + [1, 2]` never quietly becomes
        a concatenation."""
        if not isinstance(other, Stream):
            return NotImplemented
        return Stream.concat(self, other)

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
        extended by copy. Called with no executor the receiver's carries over.

        The next stage is *copied*, not constructed. Constructing it re-entered
        a subclass's __init__ once per stage - five times for a three-op
        pipeline plus a mode switch - so a subclass wrapping an I/O resource,
        which is the use case CLAUDE.md documents, acquired one resource per
        stage and kept the last. It also silently required every subclass to
        accept (source, close_handlers) positionally, with an already-normalized
        AsyncGenerator first, which is not how anyone would write that subclass:
        `DsnStream(dsn)` raised TypeError on its first intermediate op.

        Java has neither problem because its derived stages are an internal
        type holding no resource, and Stream is an interface nobody subclasses.
        This library went the other way on purpose - type(self) was here to
        preserve subclass identity across derivation - and once identity is the
        requirement, copying is the only way to have it without construction.

        copy.copy shares _source, _close_handlers and any subclass attributes
        by reference and carries _consumed as False, which is exactly what the
        four assignments below and the receiver's own invalidation expect. It
        also honours a subclass's __copy__, which is a feature: a subclass with
        genuinely per-stage state has one place to say so. Stream itself defines
        none, so the default applies."""
        self._check_not_consumed()
        new_stream = copy(self)
        new_stream._chain = [*self._chain, op] if op is not None else self._chain
        new_stream._executor = executor or self._executor
        self._consumed = True
        return new_stream

    async def _evaluate(self, terminal: TerminalSink[Any], demand: OrderDemand) -> Any:
        """The chain driven into a terminal sink. The one place a stream's
        execution mode is consulted, and it always consults the stream's: no
        terminal names an executor for itself any more.

        `demand` is required rather than defaulted because it is a claim about
        the terminal, and only the terminal can make it. A default would let a
        new terminal inherit an answer nobody chose - silently buying a reorder
        barrier it does not need, or silently going without one it does.

        It is an OrderDemand rather than a bool because that was the whole of
        what an executor argument here was ever used for. find_first() passed
        SEQUENTIAL to get encounter order unconditionally, which forfeited the
        caller's mode to express a demand; ALWAYS expresses the demand and
        keeps the mode."""
        self._check_not_consumed()
        return await self._executor.value(self._chain, self._source, terminal, demand)

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
        return self._executor.elements(self._chain, self._source, OrderDemand.IF_ORDERED)

    def unordered(self) -> Stream[T]:
        """Queues an op that clears encounter order for everything after it,
        and nothing else - see UnorderedOp, which links to no sink at all.
        Being an op is what makes this positional: Java's unordered() is a
        pipeline stage for the same reason, the deliberate opposite of its
        parallel(), which sets a flag on the source stage so as *not* to be.

        Under RACING this is the performance lever, and it is the primary way
        to buy concurrency back. An ordered racing pipeline holds a finished
        element until every earlier one has been released - for an operation
        that reads position, and for delivery to a terminal that observes
        order. Clearing the characteristic removes both."""
        return self._derive(UnorderedOp())

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
        return self._derive(FilterOp(predicate))

    def map(self, mapper: Mapper[T, R]) -> Stream[R]:
        return self._derive(MapOp(mapper))

    def flat_map(self, flat_mapper: FlatMapper[T, R]) -> Stream[R]:
        # Pre-call rejection, not a dispatch site: flat_mapper must return a
        # Stream synchronously, so an async def here is always a caller
        # mistake. This is unrelated to maybe_await's post-call awaiting.
        if iscoroutinefunction(flat_mapper):
            raise StreamBuildException("flat_map() does not support coroutines")

        return self._derive(FlatMapOp(flat_mapper))

    def sorted(self, comparator: Comparator[T] | None = None, reverse: bool = False) -> Stream[T]:
        return self._derive(SortedOp(comparator, reverse))

    def distinct(self) -> Stream[T]:
        return self._derive(DistinctOp())

    def peek(self, consumer: Consumer[T]) -> Stream[T]:
        return self._derive(PeekOp(consumer))

    def limit(self, max_size: int) -> Stream[T]:
        return self._derive(LimitOp(max_size))

    def skip(self, n: int) -> Stream[T]:
        return self._derive(SkipOp(n))

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
                demand = OrderDemand.NONE if Characteristics.UNORDERED in collector.characteristics else OrderDemand.IF_ORDERED
                return self._evaluate(CollectorSink(collector), demand)
            if isinstance(collector, StreamingCollector):
                return collector(self.iterator())
            raise StreamBuildException(
                "collect() requires a Collector (see snakestream.collector.Collector), "
                "or to_generator for a lazy, streaming result"
            )
        # 3-arg mutable reduction: supplier/accumulator, sync or async, are
        # exactly a Collector's supplier/accumulator. combiner is accepted for
        # signature parity with Java's Stream.collect(Supplier, BiConsumer,
        # BiConsumer) but is never invoked: collect() always folds over a
        # single composed AsyncGenerator, sequential or parallel, with no
        # independently accumulated partitions to merge - the same posture
        # reduce() already has under .parallel().
        supplier, accumulator, combiner = args
        collector = Collector(supplier, accumulator, combiner)
        # an arbitrary user accumulator folding into an arbitrary container:
        # nothing here says the result is order-independent, so it is not
        # assumed to be. The Collector form has UNORDERED to say otherwise;
        # this form declares no characteristics, so it stays IF_ORDERED by
        # the same derivation the single-argument branch above uses.
        return self._evaluate(CollectorSink(collector), OrderDemand.IF_ORDERED)

    @overload
    async def reduce(self, identity: T | R, accumulator: Accumulator[T, R]) -> T | R: ...

    @overload
    async def reduce(self, accumulator: BinaryOperator[T]) -> T | None: ...

    async def reduce(self, identity: Any = UNSET, accumulator: Any = UNSET) -> Any:
        if accumulator is UNSET:
            # Called as reduce(accumulator): the single positional arg is the
            # accumulator, and the identity is seeded from the stream itself.
            identity, accumulator = UNSET, identity
        # the accumulator is not required to be associative or commutative
        # here, so the fold is over encounter order or it is over nothing
        return await self._evaluate(ReduceSink(identity, accumulator), OrderDemand.IF_ORDERED)

    async def for_each(self, consumer: Consumer[T]) -> None:
        # explicitly order-blind, as Java's forEach() is: for_each_ordered() is
        # the one that promises encounter order, and this is what it costs less
        # than
        return await self._evaluate(ForEachSink(consumer), OrderDemand.NONE)

    async def for_each_ordered(self, consumer: Consumer[T]) -> None:
        """for_each() that observes encounter order - the whole difference
        between the two, and the only thing this declares.

        It asks for order rather than for an executor. split_point() releases
        the demand on an unordered pipeline, which is the javadoc's "if the
        stream has a defined encounter order" caveat and the same condition
        ForEachOps.OfRef.evaluateParallel() reads when it picks between
        ForEachOrderedTask and plain ForEachTask.

        Naming SEQUENTIAL here, as this once did, went a step further than Java
        does: ForEachOrderedTask is itself a CountedCompleter over the
        fork-join pool, so Java's ordered path stays parallel and only its
        *delivery* is ordered. The barrier is that shape. Every op still races;
        an op queued upstream is therefore not ordered by this call, and a side
        effect that needs to be belongs in `consumer`."""
        return await self._evaluate(ForEachSink(consumer), OrderDemand.IF_ORDERED)

    async def to_array(self) -> list[T]:
        # collect() runs _check_not_consumed() itself, and to_list() declares no
        # characteristics, so this observes encounter order through it
        return await self.collect(to_list())

    async def find_first(self) -> T | None:
        # encounter order regardless of executor *and* regardless of ordering,
        # which is a demand rather than an executor: ALWAYS is the only value
        # that survives unordered(), and the chain still races under whatever
        # mode the caller declared. Java does not relax findFirst() on an
        # unordered stream either, and does not go sequential for it:
        # FindOp.mustFindFirst is fixed when the op is constructed, and
        # FindTask does its leftmost scan across the fork-join branches
        # whenever it is set, never consulting upstream ORDERED. The javadoc
        # permits returning any element there; the implementation declines to.
        # find_any() is where a caller who wants the race goes -- not for the
        # concurrency, which this keeps, but for the answer.
        return await self._evaluate(FindSink(), OrderDemand.ALWAYS)

    async def find_any(self) -> T | None:
        # the whole point of it: any element will do, so no barrier is owed
        return await self._evaluate(FindSink(), OrderDemand.NONE)

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
        return await self._evaluate(MinMaxSink(comparator, asc), OrderDemand.IF_ORDERED)

    async def _match(self, predicate: Predicate[T], short_circuit_on: bool, default: bool) -> bool:
        # a predicate over the whole stream has one answer whatever the order
        return await self._evaluate(MatchSink(predicate, short_circuit_on, default), OrderDemand.NONE)

    async def all_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=False, default=True)

    async def none_match(self, predicate: Predicate[T]) -> bool:
        return not await self._match(predicate, short_circuit_on=True, default=False)

    async def any_match(self, predicate: Predicate[T]) -> bool:
        return await self._match(predicate, short_circuit_on=True, default=False)

    async def count(self) -> int:
        return await self._evaluate(CountSink(), OrderDemand.NONE)

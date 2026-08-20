from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, cast
from collections.abc import AsyncGenerator, AsyncIterable

from snakestream.exception import IllegalStateException
from snakestream.sink import GeneratorBridgeSink, Op, Sink, TerminalSink
from snakestream.type import T, CloseHandler, StateMap

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover
    from snakestream.parallel_stream import ParallelStream  # pragma: no cover


async def _normalize(source: Any) -> AsyncGenerator:
    if isinstance(source, (dict, str, bytes)):
        yield source
    elif hasattr(source, "__iter__"):
        for i in source:
            yield i
    elif hasattr(source, "__next__"):
        # A bare sync iterator, implementing only __next__. It can't be driven
        # with `for`, and StopIteration must not escape: PEP 479 turns one
        # raised inside an async generator into RuntimeError. Only the next()
        # call is guarded, so a StopIteration thrown in at the yield still
        # propagates to the caller rather than silently ending the stream.
        while True:
            try:
                i = next(source)
            except StopIteration:
                return
            yield i
    else:
        yield source


def _accept(source: Any) -> AsyncGenerator | None:
    if isinstance(source, AsyncGenerator) or isinstance(source, AsyncIterable):
        return source
    return None


class _maybe_aclosing:
    """Like contextlib.aclosing(), but a no-op on __aexit__ if the wrapped
    object has no aclose() — some accepted sources (e.g. a bare async
    iterator implementing only __anext__) don't."""

    def __init__(self, thing: AsyncGenerator) -> None:
        self._thing = thing

    async def __aenter__(self) -> AsyncGenerator:
        return self._thing

    async def __aexit__(self, *exc_info: Any) -> None:
        if hasattr(self._thing, "aclose"):
            await self._thing.aclose()


def _wrap_sink(intermediaries: list[Op], terminal: Sink[Any]) -> Sink[Any]:
    """Link a chain of ops onto a terminal sink, innermost last, and return the
    head. Java's AbstractPipeline.wrapSink() does exactly this."""
    sink = terminal
    for op in reversed(intermediaries):
        sink = op.link(sink)
    return sink


async def _copy_into(head: Sink[Any], src: AsyncGenerator, state_map: StateMap) -> None:
    """Push every element of a source into a wrapped sink, honouring
    cancellation. Java's AbstractPipeline.copyInto() does exactly this."""
    await head.begin(state_map)
    # a chain can already be cancelled before it has seen anything
    # (limit(0)); pulling even one element would run every upstream
    # op on a value nobody wants
    if not head.cancellation_requested():
        async for item in src:
            await head.accept(item)
            if head.cancellation_requested():
                break
    await head.end()


class BaseStream(Generic[T]):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        self._stream: AsyncGenerator[T, None] = _accept(source) or _normalize(source)
        self._chain: list[Op] = []
        self._close_handlers: list[CloseHandler] = [] if close_handlers is None else close_handlers
        self._ordered: bool = True
        self._consumed: bool = False

    def _check_not_consumed(self) -> None:
        if self._consumed:
            raise IllegalStateException("this stream has already been extended into a new instance or terminally consumed")

    def _derive(self, op: Op) -> BaseStream[Any]:
        self._check_not_consumed()
        new_stream = type(self)(self._stream, self._close_handlers)
        new_stream._chain = self._chain + [op]
        new_stream._ordered = self._ordered
        self._consumed = True
        return new_stream

    async def _drive(
        self,
        chain: list[Op],
        source: AsyncGenerator,
        state_map: StateMap | None = None,
    ) -> AsyncGenerator[T, None]:
        if state_map is None:
            state_map = {}
        bridge: GeneratorBridgeSink = GeneratorBridgeSink()
        head = _wrap_sink(chain, bridge)
        async with _maybe_aclosing(source) as src:
            await head.begin(state_map)
            # same pre-first-pull guard as _copy_into(), which carries the
            # reasoning; this loop cannot share it because it has to yield
            if not head.cancellation_requested():
                async for item in src:
                    await head.accept(item)
                    if bridge.buffer:
                        for out in bridge.buffer:
                            yield out
                        bridge.buffer.clear()
                    if head.cancellation_requested():
                        break
            await head.end()
            if bridge.buffer:
                for out in bridge.buffer:
                    yield out
                bridge.buffer.clear()

    async def _drive_to(self, terminal: TerminalSink[Any]) -> Any:
        """Drive the chain into a terminal sink and return its result.

        The dispatching form: ParallelStream overrides it. A terminal that
        needs encounter order regardless of the stream's mode calls
        _drive_to_sequential() directly instead."""
        return await self._drive_to_sequential(terminal)

    async def _drive_to_sequential(self, terminal: TerminalSink[Any]) -> Any:
        """Push source -> head -> terminal in a single ordered pass, with
        nothing buffered on the way: the last intermediate sink pushes straight
        into the terminal. Never overridden, so it stays ordered on a
        ParallelStream too."""
        self._check_not_consumed()
        head = _wrap_sink(self._chain, terminal)
        async with _maybe_aclosing(self._stream) as src:
            await _copy_into(head, src, {})
        return terminal.result()

    def _compose(self) -> AsyncGenerator[T, None]:
        """Build the chain into a lazily-evaluated generator.

        The dispatching form, and the seam where execution mode is decided:
        ParallelStream overrides it to fan the same chain out into a race.
        _drive() cannot be that seam - _parallel() calls it once per racing
        branch, so overriding it would make each branch fan out again."""
        return self._drive(self._chain, self._stream)

    def _handoff(self, cls: type[BaseStream[Any]]) -> Any:
        """Compose the current chain into a fresh generator and hand it to a
        new stream of the given class, consuming this one. The mode switches
        differ only by that class, so they share this body; each keeps its own
        local import, since hoisting both here would import parallel_stream on
        a sequential() call."""
        self._check_not_consumed()
        new_source = self._compose()
        new_stream = cls(new_source, self._close_handlers)
        new_stream._ordered = self._ordered
        self._consumed = True
        return new_stream

    def sequential(self) -> Stream[T]:
        from .stream import Stream

        return cast("Stream[T]", self._handoff(Stream))

    def parallel(self) -> ParallelStream[T]:
        from .parallel_stream import ParallelStream

        return cast("ParallelStream[T]", self._handoff(ParallelStream))

    def iterator(self) -> AsyncGenerator[T, None]:
        self._check_not_consumed()
        return self._compose()

    def unordered(self) -> BaseStream[T]:
        self._ordered = False
        return self

    def is_ordered(self) -> bool:
        return self._ordered

    def on_close(self, close_handler: CloseHandler) -> BaseStream[T]:
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
            raise exceptions[0]

    def is_parallel(self) -> bool:
        return False

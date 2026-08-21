from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, cast
from collections.abc import AsyncGenerator, AsyncIterable

from snakestream.exception import IllegalStateException
from snakestream.execution import RACING, SEQUENTIAL, Executor, _wrap_sink as _wrap_sink
from snakestream.sink import Op, TerminalSink
from snakestream.type import T, CloseHandler

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover


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


class BaseStream(Generic[T]):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        self._stream: AsyncGenerator[T, None] = _accept(source) or _normalize(source)
        self._chain: list[Op] = []
        self._close_handlers: list[CloseHandler] = [] if close_handlers is None else close_handlers
        self._ordered: bool = True
        self._consumed: bool = False
        self._executor: Executor = SEQUENTIAL

    def _check_not_consumed(self) -> None:
        if self._consumed:
            raise IllegalStateException("this stream has already been extended into a new instance or terminally consumed")

    def _derive(self, op: Op) -> BaseStream[Any]:
        self._check_not_consumed()
        new_stream = type(self)(self._stream, self._close_handlers)
        new_stream._chain = self._chain + [op]
        new_stream._ordered = self._ordered
        new_stream._executor = self._executor
        self._consumed = True
        return new_stream

    def _compose(self) -> AsyncGenerator[T, None]:
        """The chain as a generator, under this stream's executor."""
        return self._executor.elements(self._chain, self._stream)

    async def _evaluate(self, terminal: TerminalSink[Any]) -> Any:
        """The chain driven into a terminal sink, under this stream's executor.
        The one place a stream's execution mode is consulted; a terminal that
        needs encounter order regardless of mode names SEQUENTIAL itself."""
        self._check_not_consumed()
        return await self._executor.value(self._chain, self._stream, terminal)

    def _derive_executor(self, executor: Executor) -> Any:
        """A mode switch: a new stream over the SAME source and the SAME queued
        chain, differing only in its executor, consuming this one.

        It must not compose. Composing here is what made `.parallel()`
        position-dependent — ops queued before the switch were frozen under the
        old mode — where Java's `parallel()` sets a flag on the source stage and
        so governs the whole pipeline wherever it appears.

        It must not assign onto self and return self either, however tempting:
        pipeline-immutability requires the receiver be invalidated, and an
        in-place flip would leave it usable."""
        self._check_not_consumed()
        new_stream = type(self)(self._stream, self._close_handlers)
        new_stream._chain = self._chain
        new_stream._ordered = self._ordered
        new_stream._executor = executor
        self._consumed = True
        return new_stream

    def sequential(self) -> Stream[T]:
        return cast("Stream[T]", self._derive_executor(SEQUENTIAL))

    def parallel(self) -> Stream[T]:
        return cast("Stream[T]", self._derive_executor(RACING))

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
        return self._executor.is_parallel

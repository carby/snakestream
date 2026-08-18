from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic
from collections.abc import AsyncGenerator, AsyncIterable

from snakestream.exception import IllegalStateException
from snakestream.sink import GeneratorBridgeSink, Sink
from snakestream.type import T, CloseHandler, StateMap

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover
    from snakestream.parallel_stream import ParallelStream  # pragma: no cover


async def _normalize(source: Any) -> AsyncGenerator:
    if isinstance(source, (dict, str, bytes)):
        yield source
    elif hasattr(source, "__iter__") or hasattr(source, "__next__"):
        for i in source:
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


class BaseStream(Generic[T]):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        self._stream: AsyncGenerator[T, None] = _accept(source) or _normalize(source)
        self._chain: list[Any] = []
        self._close_handlers: list[CloseHandler] = [] if close_handlers is None else close_handlers
        self._ordered: bool = True
        self._consumed: bool = False

    def _check_not_consumed(self) -> None:
        if self._consumed:
            raise IllegalStateException("this stream has already been extended into a new instance or terminally consumed")

    def _derive(self, op: Any) -> BaseStream[Any]:
        self._check_not_consumed()
        new_stream = type(self)(self._stream, self._close_handlers)
        new_stream._chain = self._chain + [op]
        new_stream._ordered = self._ordered
        self._consumed = True
        return new_stream

    def _sequential(self, intermediaries: list[Any], terminal: Sink[Any]) -> Sink[Any]:
        sink = terminal
        for op in reversed(intermediaries):
            sink = op.link(sink)
        return sink

    async def _drive(
        self,
        chain: list[Any],
        source: AsyncGenerator,
        state_map: StateMap | None = None,
    ) -> AsyncGenerator[T, None]:
        if state_map is None:
            state_map = {}
        bridge: GeneratorBridgeSink = GeneratorBridgeSink()
        head = self._sequential(chain, bridge)
        async with _maybe_aclosing(source) as src:
            await head.begin(state_map)
            async for item in src:
                await head.accept(item)
                for out in bridge.drain():
                    yield out
                if head.cancellation_requested():
                    break
            await head.end()
            for out in bridge.drain():
                yield out

    def _compose(self) -> AsyncGenerator[T, None]:
        return self._drive(self._chain[:], self._stream)

    def sequential(self) -> Stream[T]:
        from .stream import Stream

        self._check_not_consumed()
        new_source = self._compose()
        new_stream = Stream(new_source, self._close_handlers)
        new_stream._ordered = self._ordered
        self._consumed = True
        return new_stream

    def parallel(self) -> ParallelStream[T]:
        from .parallel_stream import ParallelStream

        self._check_not_consumed()
        new_source = self._compose()
        new_stream = ParallelStream(new_source, self._close_handlers)
        new_stream._ordered = self._ordered
        self._consumed = True
        return new_stream

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

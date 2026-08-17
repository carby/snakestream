from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic
from collections.abc import AsyncGenerator, AsyncIterable, Callable

from snakestream.type import T, CloseHandler

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


class BaseStream(Generic[T]):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        self._stream: AsyncGenerator[T, None] = _accept(source) or _normalize(source)
        self._chain: list[Callable] = []
        self._close_handlers: list[CloseHandler] = close_handlers or []
        self._ordered: bool = True

    def _sequential(
        self,
        intermediaries: list[Callable],
        iterable: AsyncGenerator,
        state_map: dict[Callable, Any] | None = None,
    ) -> AsyncGenerator:
        for fn in intermediaries:
            state = state_map.get(fn) if state_map is not None else None
            iterable = fn(iterable, state) if state is not None else fn(iterable)
        return iterable

    def _compose(self) -> AsyncGenerator[T, None]:
        return self._sequential(self._chain[:], self._stream)

    def sequential(self) -> Stream[T]:
        from .stream import Stream

        new_source = self._compose()
        new_stream = Stream(new_source, self._close_handlers)
        new_stream._ordered = self._ordered
        return new_stream

    def parallel(self) -> ParallelStream[T]:
        from .parallel_stream import ParallelStream

        new_source = self._compose()
        new_stream = ParallelStream(new_source, self._close_handlers)
        new_stream._ordered = self._ordered
        return new_stream

    def iterator(self) -> AsyncGenerator[T, None]:
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
        for close_handler in self._close_handlers:
            close_handler()

    def is_parallel(self) -> bool:
        return False

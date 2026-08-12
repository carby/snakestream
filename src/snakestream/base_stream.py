from __future__ import annotations

from typing import TYPE_CHECKING, Any
from collections.abc import AsyncGenerator, AsyncIterable, Callable

from snakestream.type import CloseHandler

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover


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


class BaseStream:
    def __init__(self, source: Any) -> None:
        self._stream = _accept(source) or _normalize(source)
        self._chain: list[Callable] = []
        self._close_handlers = []

    def _sequential(
        self,
        intermediaries: list[Callable],
        iterable: AsyncGenerator,
        state_map: dict[Callable, Any] | None = None,
    ) -> AsyncGenerator:
        if len(intermediaries) == 0:
            return iterable
        fn = intermediaries.pop(0)
        state = state_map.get(fn) if state_map is not None else None
        next_iterable = fn(iterable, state) if state is not None else fn(iterable)
        if len(intermediaries) == 0:
            return next_iterable
        return self._sequential(intermediaries, next_iterable, state_map)

    def _compose(self) -> AsyncGenerator:
        return self._sequential(self._chain[:], self._stream)

    def sequential(self) -> Stream:
        from .stream import Stream

        new_source = self._compose()
        return Stream(new_source, self._close_handlers)

    def parallel(self) -> Stream:
        from .parallel_stream import ParallelStream

        new_source = self._compose()
        return ParallelStream(new_source, self._close_handlers)

    def on_close(self, close_handler: CloseHandler) -> BaseStream:
        self._close_handlers.append(close_handler)
        return self

    def close(self) -> None:
        for close_handler in self._close_handlers:
            close_handler()

    def is_parallel(self) -> bool:
        return False

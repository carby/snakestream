from typing import TYPE_CHECKING, Any, AsyncGenerator, AsyncIterable, Callable, List, Optional

from snakestream.type import CloseHandler

if TYPE_CHECKING:
    from snakestream.stream import Stream  # pragma: no cover


async def _normalize(source: Any) -> AsyncGenerator:
    if isinstance(source, dict):
        yield source
    elif hasattr(source, '__iter__') or hasattr(source, '__next__'):
        for i in source:
            yield i
    else:
        yield source


def _accept(source: Any) -> Optional[AsyncGenerator]:
    if isinstance(source, AsyncGenerator) or isinstance(source, AsyncIterable):
        return source
    return None


class BaseStream():
    def __init__(self, source: Any) -> None:
        self._stream = _accept(source) or _normalize(source)
        self._chain: List[Callable] = []
        self._close_handlers = []

    def _sequential(self, intermediaries: List[Callable], iterable: AsyncGenerator) -> AsyncGenerator:
        if len(intermediaries) == 0:
            return iterable
        if len(intermediaries) == 1:
            fn = intermediaries.pop(0)
            return fn(iterable)
        fn = intermediaries.pop(0)
        return self._sequential(intermediaries, fn(iterable))

    def _compose(self) -> AsyncGenerator:
        return self._sequential(self._chain, self._stream)

    def sequential(self) -> 'Stream':
        from .stream import Stream
        new_source = self._compose()
        return Stream(new_source, self._close_handlers)

    def parallel(self) -> 'Stream':
        from .parallel_stream import ParallelStream
        new_source = self._compose()
        return ParallelStream(new_source, self._close_handlers)

    def on_close(self, close_handler: CloseHandler) -> 'Stream':
        self._close_handlers.append(close_handler)
        return self

    def close(self) -> None:
        for close_handler in self._close_handlers:
            close_handler()

    def is_parallel(self) -> bool:
        return False

from __future__ import annotations

import asyncio
from typing import Any
from collections.abc import AsyncGenerator, Callable
from snakestream.stream import PROCESSES, Stream
from snakestream.type import CloseHandler


class ParallelStream(Stream):
    def __init__(self, source: Any, close_handlers: list[CloseHandler] | None = None) -> None:
        super().__init__(source)
        self._close_handlers = close_handlers or []

    def _compose(self) -> AsyncGenerator:
        return self._parallel(self._chain, self._stream)

    async def _parallel(
        self, intermediaries: list[Callable], iterable: AsyncGenerator, processes: int = PROCESSES
    ) -> AsyncGenerator:
        async_iterators = [self._sequential(intermediaries[:], iterable) for n in range(processes)]
        tasks: list[asyncio.Task[Any] | None] = [asyncio.ensure_future(n.__anext__()) for n in async_iterators]

        try:
            while any([n is not None for n in tasks]):
                waitlist: list[asyncio.Task[Any]] = [t for t in tasks if t is not None]
                done, _ = await asyncio.wait(waitlist, return_when=asyncio.FIRST_COMPLETED)

                for task in done:
                    task_idx = tasks.index(task)
                    try:
                        result = task.result()
                        tasks[task_idx] = asyncio.ensure_future(async_iterators[task_idx].__anext__())
                        yield result
                    except StopAsyncIteration:
                        tasks[task_idx] = None
        finally:
            # if we're leaving early (e.g. a task raised), make sure no other
            # in-flight task is left uncancelled or its exception unretrieved
            pending = [t for t in tasks if t is not None]
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    def is_parallel(self) -> bool:
        return True

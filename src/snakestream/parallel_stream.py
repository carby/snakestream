import asyncio
from typing import Any, AsyncGenerator, Callable, List, Optional
from snakestream.stream import PROCESSES, Stream
from snakestream.type import CloseHandler


class ParallelStream(Stream):
    def __init__(self, source: Any, close_handlers: Optional[List[CloseHandler]] = None) -> None:
        super().__init__(source)
        self._close_handlers = close_handlers or []

    def _compose(self) -> AsyncGenerator:
        return self._parallel(self._chain, self._stream)

    async def _parallel(
        self,
        intermediaries: List[Callable],
        iterable: AsyncGenerator,
        processes: int = PROCESSES
    ) -> AsyncGenerator:
        async_iterators = [self._sequential(intermediaries[:], iterable) for n in range(processes)]
        tasks = [asyncio.ensure_future(n.__anext__()) for n in async_iterators]

        while any([n is not None for n in tasks]):

            waitlist = filter(lambda n: n is not None, tasks)
            done, _ = await asyncio.wait(waitlist, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                task_idx = tasks.index(task)
                try:
                    result = tasks[task_idx].result()
                    tasks[task_idx] = asyncio.ensure_future(async_iterators[task_idx].__anext__())
                    yield result
                except StopAsyncIteration:
                    tasks[task_idx] = None

    def is_parallel(self) -> bool:
        return True

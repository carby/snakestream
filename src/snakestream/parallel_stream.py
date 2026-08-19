from __future__ import annotations

import asyncio
from typing import Any
from collections.abc import AsyncGenerator
from snakestream.base_stream import _maybe_aclosing
from snakestream.sink import Op, TerminalSink
from snakestream.stream import PROCESSES, Stream
from snakestream.terminals import _FindSink
from snakestream.type import T, StateMap


async def _guarded(source: AsyncGenerator, lock: asyncio.Lock) -> AsyncGenerator:
    try:
        while True:
            async with lock:
                try:
                    item = await source.__anext__()
                except StopAsyncIteration:
                    return
            yield item
    finally:
        async with lock:
            await source.aclose()


class ParallelStream(Stream[T]):
    def _compose(self) -> AsyncGenerator:
        return self._parallel(self._chain, self._stream)

    async def _parallel(
        self, intermediaries: list[Op], iterable: AsyncGenerator, processes: int = PROCESSES
    ) -> AsyncGenerator:
        state_map: StateMap = {}
        for op in intermediaries:
            state = op.make_shared_state()
            if state is not None:
                state_map[op] = state
        lock = asyncio.Lock()
        async_iterators = [self._drive(intermediaries, _guarded(iterable, lock), state_map) for n in range(processes)]
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

    async def _drive_to(self, terminal: TerminalSink[Any]) -> Any:
        """The terminal sits outside the race, accumulating what the branches
        produce: each branch has its own sink chain, so there is no single
        chain to link the terminal onto. Cancellation therefore reaches only
        this loop - an in-flight branch's own sinks never see it - which is a
        missed optimization, not a correctness gap: _parallel()'s finally
        block cancels and gathers the pending tasks on the way out."""
        self._check_not_consumed()
        await terminal.begin({})
        if not terminal.cancellation_requested():
            async with _maybe_aclosing(self._compose()) as src:
                async for n in src:
                    await terminal.accept(n)
                    if terminal.cancellation_requested():
                        break
        await terminal.end()
        return terminal.result()

    async def find_first(self) -> T | None:
        if not self.is_ordered():
            return await self.find_any()
        return await self._drive_to_sequential(_FindSink())

"""How a composed chain actually runs. Four primitives do the work:
stream_through() (push in, pull out, lazily), race_through() (N branches
racing one shared source), feed_through() (fused push straight to a
terminal, nothing buffered) and drain() (any generator into a terminal).
Two Executor values sit on top: Sequential.elements() and Racing.elements()
each pick a primitive; Sequential.value() is the one asymmetry in the
protocol, overriding the generic drain(elements(...), terminal) with
feed_through() because composing-then-draining measured far more
expensive per element (see its own docstring for the figures)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, ClassVar
from collections.abc import AsyncGenerator, AsyncIterator

from snakestream.sink import GeneratorBridgeSink, Op, Sink, TerminalSink
from snakestream.type import StateMap, T

# How many branches the racing executor fans a chain out across. Bound into
# RACING below at import time, which is where it was always effectively bound:
# the old _parallel() took it as a default argument value.
PROCESSES: int = 4


@asynccontextmanager
async def _maybe_aclosing(thing: AsyncGenerator) -> AsyncIterator[AsyncGenerator]:
    """Like contextlib.aclosing(), but a no-op on exit if the wrapped object
    has no aclose() — some accepted sources (e.g. a bare async iterator
    implementing only __anext__) don't. The finally is load-bearing: the
    source must be closed on the way out of a body that raised or broke
    early (limit, find_any, any_match), not just one that ran to
    exhaustion."""
    try:
        yield thing
    finally:
        if hasattr(thing, "aclose"):
            await thing.aclose()


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


async def _guarded(source: AsyncGenerator, lock: asyncio.Lock) -> AsyncGenerator:
    """One branch's view of a source shared with other branches: every pull and
    the final close happen under the shared lock."""
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


# --- the execution primitives -------------------------------------------
#
# Two things a pipeline can produce, and two ways to run it, but not a
# symmetric 2x2: feed_through() is a fused fast path that exists only because
# it measured more than twice as fast as composing and then draining (see
# Sequential.value). Each function has exactly one meaning, and none of them
# needs a stream instance.


async def stream_through(
    chain: list[Op],
    source: AsyncGenerator,
    state_map: StateMap | None = None,
) -> AsyncGenerator[T, None]:
    """Push the chain, pull the results: one worker, elements out lazily.
    Java's StreamSpliterators.WrappingSpliterator adapts push to pull the same
    way, buffering what the sink emits until the caller asks for it."""
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


async def race_through(chain: list[Op], source: AsyncGenerator, workers: int) -> AsyncGenerator:
    """The same chain, run by `workers` branches racing over one shared source.
    Ordering is not preserved: elements are yielded as branches finish them."""
    state_map: StateMap = {}
    for op in chain:
        state = op.make_shared_state()
        if state is not None:
            state_map[op] = state
    lock = asyncio.Lock()
    branches = [stream_through(chain, _guarded(source, lock), state_map) for _ in range(workers)]
    # the in-flight __anext__() per branch, keyed by task so a completed one
    # maps back to its branch in O(1); it doubles as the waitlist and as the
    # "any branch still running" test, so nothing here is scanned or rebuilt
    # per element. A branch that raised StopAsyncIteration is simply not
    # re-armed, which is what drains this dict to empty.
    in_flight: dict[asyncio.Task[Any], int] = {
        asyncio.ensure_future(branch.__anext__()): idx for idx, branch in enumerate(branches)
    }

    try:
        while in_flight:
            done, _ = await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                branch = in_flight.pop(task)
                try:
                    result = task.result()
                except StopAsyncIteration:
                    continue
                in_flight[asyncio.ensure_future(branches[branch].__anext__())] = branch
                yield result
    finally:
        # if we're leaving early (e.g. a task raised), make sure no other
        # in-flight task is left uncancelled or its exception unretrieved
        pending = list(in_flight)
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


async def feed_through(chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any]) -> Any:
    """Push source -> head -> terminal in a single ordered pass, with nothing
    buffered on the way: the last intermediate sink pushes straight into the
    terminal, so no generator sits between them."""
    head = _wrap_sink(chain, terminal)
    async with _maybe_aclosing(source) as src:
        await _copy_into(head, src, {})
    return terminal.result()


async def drain(elements: AsyncGenerator, terminal: TerminalSink[Any]) -> Any:
    """Accumulate an already-composed generator into a terminal sink. The
    terminal sits outside whatever produced `elements`, so cancellation reaches
    only this loop."""
    async with _maybe_aclosing(elements) as src:
        await _copy_into(terminal, src, {})
    return terminal.result()


# --- the executors ------------------------------------------------------


class Executor(ABC):
    """How a stream runs, as a value rather than as the stream's type. Two
    operations: one producing the chain's elements as a generator, one driving
    the chain into a terminal sink."""

    is_parallel: ClassVar[bool]

    @abstractmethod
    def elements(self, chain: list[Op], source: AsyncGenerator) -> AsyncGenerator: ...

    async def value(self, chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any]) -> Any:
        """The general form: compose, then drain into the terminal. Correct for
        any executor; Racing uses it unchanged."""
        return await drain(self.elements(chain, source), terminal)


class Sequential(Executor):
    is_parallel = False

    def elements(self, chain: list[Op], source: AsyncGenerator) -> AsyncGenerator:
        return stream_through(chain, source)

    async def value(self, chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any]) -> Any:
        """Overrides the general form with the fused push, which is the one
        asymmetry in this protocol and is here on measurement, not taste:
        composing and then draining costs +125% per element on count() and
        +112% on reduce() (Python 3.14.5, 20,000 elements, no intermediate
        chain, best of 5). Removing the generator between the last sink and the
        terminal removes an accept, a buffer append, a truthiness check, a
        yield across the async-generator boundary and a list clear, per
        element. Results are identical to the general form."""
        return await feed_through(chain, source, terminal)


class Racing(Executor):
    is_parallel = True

    __slots__ = ("workers",)

    def __init__(self, workers: int) -> None:
        self.workers = workers

    def elements(self, chain: list[Op], source: AsyncGenerator) -> AsyncGenerator:
        return race_through(chain, source, self.workers)

    # value() is inherited: each racing branch owns its own sink chain, so
    # there is no single chain to fuse a terminal onto. The general form is
    # the only form available here, which is why it is the base.


SEQUENTIAL = Sequential()
RACING = Racing(PROCESSES)

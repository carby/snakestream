"""Java's AbstractPipeline, literally: wrap_sink() and _copy_into() are ports of
AbstractPipeline.wrapSink() and AbstractPipeline.copyInto(). Three shapes drive
a chain into elements or a terminal: stream_through() (push in, pull out,
lazily — one worker, one sink chain), feed_through() (fused push straight into
a terminal, nothing buffered between the last sink and it) and drain(), which
closes the loop the other way, accumulating an already-composed generator into
a terminal sink.

Two things a pipeline can produce, and two ways to run it, but not a symmetric
2x2: feed_through() is a fused fast path that exists only because it measured
more than twice as fast as composing and then draining (see execution.py's
_Sequential.value for the figures) — not a symmetric alternative to
stream_through() plus drain(). Each function has exactly one meaning, and none
of them needs a stream instance."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from collections.abc import AsyncGenerator, AsyncIterator

from snakestream.sink import GeneratorBridgeSink, Op, Sink, TerminalSink
from snakestream.type import Aiter, StateMap, T


@asynccontextmanager
async def maybe_aclosing(thing: Aiter) -> AsyncIterator[Aiter]:
    """Like contextlib.aclosing(), but a no-op on exit if the wrapped object
    has no aclose() — some accepted sources (e.g. a bare async iterator
    implementing only __anext__) have no aclose(). The finally is
    load-bearing: the source must be closed on the way out of a body that
    raised or broke early (limit, find_any, any_match), not just one that ran
    to exhaustion."""
    try:
        yield thing
    finally:
        # getattr rather than hasattr so the widened annotation still
        # type-checks; narrowing to isinstance(thing, AsyncGenerator) would
        # type-check too but would stop closing a duck-typed closeable that
        # is not a full generator.
        aclose = getattr(thing, "aclose", None)
        if aclose is not None:
            await aclose()


def wrap_sink(intermediaries: list[Op], terminal: Sink[Any]) -> Sink[Any]:
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


async def stream_through(
    chain: list[Op],
    source: AsyncGenerator,
    state_map: StateMap | None = None,
) -> AsyncGenerator[T]:
    """Push the chain, pull the results: one worker, elements out lazily.
    Java's StreamSpliterators.WrappingSpliterator adapts push to pull the same
    way, buffering what the sink emits until the caller asks for it."""
    if state_map is None:
        state_map = {}
    bridge: GeneratorBridgeSink = GeneratorBridgeSink()
    head = wrap_sink(chain, bridge)
    async with maybe_aclosing(source) as src:
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


async def feed_through(chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any]) -> Any:
    """Push source -> head -> terminal in a single ordered pass, with nothing
    buffered on the way: the last intermediate sink pushes straight into the
    terminal, so no generator sits between them."""
    head = wrap_sink(chain, terminal)
    async with maybe_aclosing(source) as src:
        await _copy_into(head, src, {})
    return terminal.result()


async def drain(elements: AsyncGenerator, terminal: TerminalSink[Any]) -> Any:
    """Accumulate an already-composed generator into a terminal sink. The
    terminal sits outside whatever produced `elements`, so cancellation reaches
    only this loop."""
    async with maybe_aclosing(elements) as src:
        await _copy_into(terminal, src, {})
    return terminal.result()

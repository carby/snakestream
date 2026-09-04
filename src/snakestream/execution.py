"""How a composed chain actually runs.

Two shapes drive a chain into elements or a terminal: _stream_through() (push
in, pull out, lazily — one worker, one sink chain) and _feed_through() (fused
push straight into a terminal, nothing buffered between the last sink and it).
_drain() closes the loop the other way, accumulating an already-composed
generator into a terminal sink.

_fork_join_through() is where parallel execution actually happens: a
Spliterator-decomposed source, run batch by batch, each batch's chain on its
own worker thread via asyncio.to_thread(). Contiguous batches never scramble
encounter order the way the old racing executor's branches did, so there is no
merge to restore it at — split_point() (ordering.py) still finds the one place
a stateful op (sorted/distinct/limit/skip) needs a global view rather than a
batch's worth, and the chain still splits there, but what runs at the split is
a single ordinary pass over the concatenated batch output, not a reorder
buffer. See design.md (fork-join-executor-and-spliterator) for the two
declines this shape supports without one: round-level dispatch stays ordered
(_fork_join_ordered_batches) only when something downstream needs it, and
drops to a completion-ordered sliding window (_fork_join_unordered_batches)
otherwise, so an order-blind short-circuiting terminal is never held back by
an unrelated slow batch elsewhere in the same round.

Two Executor values sit on top: _Sequential.elements() and _ForkJoin.elements()
each pick a primitive; _Sequential.value() is the one asymmetry in the
protocol, overriding the generic _drain(elements(...), terminal) with
_feed_through() because composing-then-draining measured far more
expensive per element (see its own docstring for the figures)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, ClassVar
from collections.abc import AsyncGenerator, AsyncIterator

from snakestream.ordering import OrderDemand, is_ordered, split_point
from snakestream.sink import GeneratorBridgeSink, Op, Sink, TerminalSink
from snakestream.spliterator import BATCH_SIZE, batch
from snakestream.type import Aiter, StateMap, T


# How many worker threads the fork-join executor fans a chain's batches out
# across. Bound into FORK_JOIN below at import time. Named WORKERS, not
# PROCESSES: the old name was kept against the possibility that real
# parallelism would arrive as a process pool - it arrived as threads, so the
# name is now simply wrong (design.md, fork-join-executor-and-spliterator,
# decision 4). Renamed rather than aliased: anything still importing
# PROCESSES from here breaks loudly.
WORKERS: int = 4


async def _maybe_aclose(thing: AsyncIterator) -> None:
    """Close an async source, if it is one of the closeable ones — some
    accepted sources (e.g. a bare async iterator implementing only __anext__)
    have no aclose(). Split out of maybe_aclosing() below so every closer asks
    the same question in the same words."""
    # getattr rather than hasattr so the widened annotation still type-checks;
    # narrowing to isinstance(thing, AsyncGenerator) would type-check too but
    # would stop closing a duck-typed closeable that is not a full generator.
    aclose = getattr(thing, "aclose", None)
    if aclose is not None:
        await aclose()


@asynccontextmanager
async def maybe_aclosing(thing: Aiter) -> AsyncIterator[Aiter]:
    """Like contextlib.aclosing(), but a no-op on exit if the wrapped object
    has no aclose(). The finally is load-bearing: the source must be closed on
    the way out of a body that raised or broke early (limit, find_any,
    any_match), not just one that ran to exhaustion."""
    try:
        yield thing
    finally:
        await _maybe_aclose(thing)


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


# --- the execution primitives -------------------------------------------
#
# Two things a pipeline can produce, and two ways to run it, but not a
# symmetric 2x2: _feed_through() is a fused fast path that exists only because
# it measured more than twice as fast as composing and then draining (see
# _Sequential.value). Each function has exactly one meaning, and none of them
# needs a stream instance.


async def _stream_through(
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
    head = _wrap_sink(chain, bridge)
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


async def _feed_through(chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any]) -> Any:
    """Push source -> head -> terminal in a single ordered pass, with nothing
    buffered on the way: the last intermediate sink pushes straight into the
    terminal, so no generator sits between them."""
    head = _wrap_sink(chain, terminal)
    async with maybe_aclosing(source) as src:
        await _copy_into(head, src, {})
    return terminal.result()


async def _drain(elements: AsyncGenerator, terminal: TerminalSink[Any]) -> Any:
    """Accumulate an already-composed generator into a terminal sink. The
    terminal sits outside whatever produced `elements`, so cancellation reaches
    only this loop."""
    async with maybe_aclosing(elements) as src:
        await _copy_into(terminal, src, {})
    return terminal.result()


# --- fork/join: the parallel executor -----------------------------------
#
# Contiguous batches never destroy encounter order, so nothing here restores
# it — there was no reorder barrier under RACING for this to be an analogue
# of, RACING itself no longer exists. What split_point() still finds is a
# different problem entirely: a stateful op (sorted/distinct/limit/skip) that
# needs a *global* view no per-batch chain can give it. See design.md
# (fork-join-executor-and-spliterator) for both halves of the argument.

# A short-circuiting terminal (limit(), find_any(), a `.limit()` barrier
# downstream) should not have to wait out a full BATCH_SIZE-per-worker pull
# just to discover it already has enough. The first round pulls this many
# per worker instead - 4, one per worker (design.md decision 1's "made
# concrete" addendum): _pull_round() already multiplies by `workers` once,
# so a first-round size meant as the round's *total* would double-count it
# (this was 16, meant as a total but read as per-worker, giving 64 rather
# than 16 - caught by test_racing_encounter_order.py's own read-ahead
# assertions). Later rounds grow to spliterator.BATCH_SIZE, the single
# steady-state bound task 2.3 (fork-join-executor-and-spliterator) asks for.
# A starting point, not a measurement — task 7.2 is where this gets one.
_FIRST_BATCH_SIZE = 4


async def _run_element(chain: list[Op], item: Any, state_map: StateMap) -> list[Any]:
    """One batch element's whole chain, pushed through a sink built fresh for
    it alone. Called under gather() so every element in a batch races
    concurrently on the worker's own event loop — this is where the I/O
    concurrency RACING bought is preserved, not lost, under fork/join.

    A fresh bridge per element rather than one shared across the batch is
    what makes that safe: gather() only orders its *return values*, not the
    order in which its coroutines run or complete, so a bridge shared across
    concurrently-accepting elements would accumulate in completion order.
    One bridge per element sidesteps the question entirely — each element's
    outputs are already isolated before gather() reassembles them by
    argument order, the same property that makes _run_batch_async()'s
    flatten below encounter-order-correct through flat_map's multiplication
    and filter's drops alike."""
    bridge = GeneratorBridgeSink()
    head = _wrap_sink(chain, bridge)
    await head.begin(state_map)
    if not head.cancellation_requested():
        await head.accept(item)
    await head.end()
    return bridge.buffer


async def _run_batch_async(chain: list[Op], items: list[Any], state_map: StateMap) -> list[Any]:
    """One worker's batch: every element raced via _run_element(), flattened
    back into encounter order — "every output of element 0, then element 1,
    ..." — exactly `_group_through()`'s old grouping invariant, reused here
    because the reason it existed hasn't changed: a chain's output count
    per input isn't 1:1 (filter drops, flat_map multiplies).

    On a first exception, every sibling task in this batch is cancelled and
    then awaited with return_exceptions=True before re-raising - so nothing
    is left with an unretrieved exception, and the original exception (with
    its own traceback) is what propagates, not a wrapper."""
    tasks = [asyncio.create_task(_run_element(chain, item, state_map)) for item in items]
    try:
        results = await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return [out for outputs in results for out in outputs]


def _run_batch_sync(chain: list[Op], items: list[Any], state_map: StateMap) -> list[Any]:
    """asyncio.to_thread()'s callable — a fresh event loop for this batch
    alone, since the shared upstream source can't cross threads but a batch
    is already a plain materialised list by the time it gets here, and has
    nothing loop-bound left about it."""
    return asyncio.run(_run_batch_async(chain, items, state_map))


async def _pull_round(source: AsyncIterator, workers: int, size: int) -> list[list[Any]]:
    """Up to `workers` contiguous batches of at most `size` elements each,
    pulled in sequence on this coroutine alone — the one place a fork-join
    round touches the shared source, so there is nothing here for the two
    asyncio.Lock sites RACING needed to guard against: no other coroutine
    ever pulls from `source` concurrently with this one."""
    round_batches = []
    for _ in range(workers):
        items = await batch(source, size)
        if not items:
            break
        round_batches.append(items)
    return round_batches


async def _run_round(chain: list[Op], round_batches: list[list[Any]], state_map: StateMap) -> list[list[Any]]:
    """Every batch in a round, on its own thread via _run_batch_sync(), waited
    for together. On a first exception, every sibling task is cancelled and
    then awaited with return_exceptions=True before re-raising, so nothing is
    left with an unretrieved exception and the original exception (with its
    own traceback) is what propagates - not one this function wraps."""
    tasks = [asyncio.create_task(asyncio.to_thread(_run_batch_sync, chain, items, state_map)) for items in round_batches]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def _fork_join_ordered_batches(src: AsyncIterator, chain: list[Op], workers: int, state_map: StateMap) -> AsyncGenerator:
    """One round of up to `workers` contiguous batches at a time —
    _pull_round(), then _run_round() — yielded in batch order once the whole
    round has returned. Batch order is encounter order for free: batches are
    contiguous and pulled in sequence, so there is no merge to get wrong and
    nothing to reorder afterwards. Used whenever something downstream —
    an op needing a global view, or a terminal demanding it — needs that
    order; see _fork_join_batches()."""
    size = _FIRST_BATCH_SIZE
    while True:
        round_batches = await _pull_round(src, workers, size)
        if not round_batches:
            return

        results = await _run_round(chain, round_batches, state_map)
        for outputs in results:
            for out in outputs:
                yield out

        if len(round_batches) < workers:
            return
        # deliberately the same BATCH_SIZE Spliterator.try_split() uses, not
        # a separate constant chosen for this read-ahead bound specifically
        # (design.md decision 1: one number for both, over splitting it) -
        # steady-state in-flight is therefore workers * BATCH_SIZE, e.g.
        # 4096 at the defaults, against the old window's 16. Every reason
        # that window existed - memory held resident, latency behind a
        # straggler, wasted upstream invocations under a short-circuiting
        # terminal - still applies at this size; task 7.2 is where it gets
        # measured and, if warranted, a bound of its own.
        size = BATCH_SIZE


async def _fork_join_unordered_batches(
    src: AsyncIterator, chain: list[Op], workers: int, state_map: StateMap
) -> AsyncGenerator:
    """The order-blind twin of _fork_join_ordered_batches(): up to `workers`
    batches in flight at once, each refilled the moment an earlier one
    completes, with results yielded as soon as *any* batch returns rather
    than held for its round. This is what an order-blind, short-circuiting
    terminal (any_match(), find_any(), count(), for_each()) needs and the
    ordered form cannot give it: waiting out a whole round means waiting on
    every batch's slowest element, including ones a short-circuiting
    terminal was never going to look at. Nothing here restores order — it
    was never asked for — so this costs no index tag, window or release
    buffer; it is a sliding window of in-flight batches, not a merge."""
    in_flight: dict[asyncio.Task[list[Any]], None] = {}
    exhausted = False
    size = _FIRST_BATCH_SIZE

    async def _fill() -> None:
        nonlocal exhausted
        while not exhausted and len(in_flight) < workers:
            items = await batch(src, size)
            if not items:
                exhausted = True
                return
            task = asyncio.create_task(asyncio.to_thread(_run_batch_sync, chain, items, state_map))
            in_flight[task] = None

    try:
        await _fill()
        while in_flight:
            done, _ = await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                del in_flight[task]
                for out in task.result():
                    yield out
            size = BATCH_SIZE
            await _fill()
    except BaseException:
        for task in in_flight:
            task.cancel()
        await asyncio.gather(*in_flight, return_exceptions=True)
        raise


async def _fork_join_batches(chain: list[Op], source: AsyncGenerator, workers: int, ordered: bool) -> AsyncGenerator:
    """The fork-join primitive proper, dispatching to the ordered or
    order-blind form. One state map for the whole call either way, built once
    here and shared into every batch regardless of which round or window slot
    it lands in — the same requirement RACING's state_map met, now honoured by
    ops.py's threading.Lock-guarded containers instead of asyncio's
    single-event-loop cooperative scheduling (see design.md, decision 8).

    aiter(source) once, here — not inside batch() — for the same reason
    _race_through() called it exactly once on `shared`: source may be a bare
    AsyncIterable whose __aiter__() returns a fresh iterator each call rather
    than self (stream-execution-model's source-acceptance requirement covers
    exactly this shape), and anext() requires an iterator, not merely an
    iterable. One conversion up front, reused by every batch() pull."""
    state_map: StateMap = {}
    for op in chain:
        state = op.make_shared_state()
        if state is not None:
            state_map[op] = state

    async with maybe_aclosing(aiter(source)) as src:
        through = _fork_join_ordered_batches if ordered else _fork_join_unordered_batches
        async for out in through(src, chain, workers, state_map):
            yield out


async def _fork_join_through(
    chain: list[Op],
    source: AsyncGenerator,
    workers: int,
    demand: OrderDemand,
    ordered_in: bool = True,
) -> AsyncGenerator:
    """The same chain, run by `workers` workers over contiguous batches of one
    shared source. split_point() is reused unmodified (design.md decision 3):
    it still finds the one op that needs a global view rather than a batch's
    worth, and the chain still splits there — but there is no reorder barrier
    to run afterwards, because fork/join's batches never scramble order in
    the first place. The barrier op runs a single ordinary pass over the
    concatenated, already-ordered batch output, and everything after it
    resumes fork/join afresh, exactly as _run_ordered_tail() resumed
    _race_through() for the ops downstream of RACING's barrier.

    `ordered_in` carries the pipeline's ordering characteristic across a
    resumed tail, the same seed is_ordered() and split_point() need it for
    under RACING.

    split is None means nothing downstream needs order at all — no op, no
    terminal — so the whole chain runs order-blind (_fork_join_unordered_
    batches, via _fork_join_batches(..., ordered=False)): an order-blind,
    short-circuiting terminal gets results as batches complete rather than
    waiting out a round behind an unrelated slow element."""
    split = split_point(chain, demand, ordered_in)
    if split is None:
        async for out in _fork_join_batches(chain, source, workers, ordered=False):
            yield out
        return

    head, tail = chain[:split], chain[split:]
    # an empty head means the barrier is the chain's first op: nothing to
    # fork/join yet, so skip straight to the single ordered pass rather than
    # dispatching pure passthrough batches to worker threads for no reason
    ordered = _fork_join_batches(head, source, workers, ordered=True) if head else source
    barrier, rest = tail[:1], tail[1:]
    if not rest:
        async for out in _stream_through(barrier, ordered):
            yield out
        return
    async for out in _fork_join_through(rest, _stream_through(barrier, ordered), workers, demand, is_ordered(barrier)):
        yield out


# --- the executors ------------------------------------------------------


class Executor(ABC):
    """How a stream runs, as a value rather than as the stream's type. Two
    operations: one producing the chain's elements as a generator, one driving
    the chain into a terminal sink.

    Both take `demand`, the consumer's declaration of what it asks of
    encounter order. It is a second axis alongside which executor a terminal
    names: the executor decides *how* the chain runs, this decides whether the
    executor owes it encounter order. elements()' consumer can always tell - it
    hands out raw elements - so its callers pass IF_ORDERED; a terminal answers
    for itself, and most of them do not care.

    It sits on the protocol rather than being read off the terminal sink
    because elements() has no terminal sink to read. It is an OrderDemand
    rather than a bool because find_first() asks unconditionally, which a bool
    cannot distinguish from asking where the pipeline happens to be ordered -
    see OrderDemand."""

    is_parallel: ClassVar[bool]

    @abstractmethod
    def elements(self, chain: list[Op], source: AsyncGenerator, demand: OrderDemand) -> AsyncGenerator: ...

    async def value(self, chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any], demand: OrderDemand) -> Any:
        """The general form: compose, then _drain into the terminal. Correct for
        any executor; _ForkJoin uses it unchanged."""
        return await _drain(self.elements(chain, source, demand), terminal)


class _Sequential(Executor):
    is_parallel = False

    # demand is accepted and ignored throughout: a single ordered pass
    # delivers in encounter order whether or not anyone is looking. The
    # parameter is on the protocol because the *racing* executor needs it, and
    # a caller must be able to state the demand without knowing which executor
    # will read it.

    def elements(self, chain: list[Op], source: AsyncGenerator, demand: OrderDemand) -> AsyncGenerator:
        return _stream_through(chain, source)

    async def value(self, chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any], demand: OrderDemand) -> Any:
        """Overrides the general form with the fused push, which is the one
        asymmetry in this protocol and is here on measurement, not taste:
        composing and then draining costs +125% per element on count() and
        +112% on reduce() (Python 3.14.5, 20,000 elements, no intermediate
        chain, best of 5). Removing the generator between the last sink and the
        terminal removes an accept, a buffer append, a truthiness check, a
        yield across the async-generator boundary and a list clear, per
        element. Results are identical to the general form."""
        return await _feed_through(chain, source, terminal)


class _ForkJoin(Executor):
    is_parallel = True

    __slots__ = ("workers",)

    def __init__(self, workers: int) -> None:
        self.workers = workers

    def elements(self, chain: list[Op], source: AsyncGenerator, demand: OrderDemand) -> AsyncGenerator:
        return _fork_join_through(chain, source, self.workers, demand)

    # value() is inherited: a batch's chain is built fresh per element
    # (_run_element()), not shared across a single composed chain a terminal
    # could be fused onto, so there is no single chain to fuse it with. See
    # stream-execution-model, this change's delta.


SEQUENTIAL = _Sequential()
FORK_JOIN = _ForkJoin(WORKERS)

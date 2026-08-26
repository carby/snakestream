"""How a composed chain actually runs. Four primitives do the work:
stream_through() (push in, pull out, lazily), race_through() (N branches
racing one shared source), feed_through() (fused push straight to a
terminal, nothing buffered) and drain() (any generator into a terminal).
race_through() has a second gear: where the chain contains an operation whose
answer depends on an element's position and the pipeline is ordered there, it
splits the chain at that operation, races everything upstream and reorders at
the merge so the rest runs as one ordered pass — see _split_point() and
_release_in_order().
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
from collections.abc import AsyncGenerator, AsyncIterator, Iterator

from snakestream.sink import GeneratorBridgeSink, Op, Ordering, Sink, TerminalSink, is_ordered
from snakestream.type import StateMap, T, _Aiter

# How many branches the racing executor fans a chain out across. Bound into
# RACING below at import time, which is where it was always effectively bound:
# the old _parallel() took it as a default argument value.
PROCESSES: int = 4

# How far ahead of the last released group a branch may pull, in source
# elements, when the racing executor is honouring encounter order. Ordering
# means holding a finished element until every earlier one has been released,
# and without a bound one slow first element draws the whole source into
# memory; this is the analogue of the leaf partitioning that bounds Java's
# fork-join, which the one-shared-source design here otherwise lacks.
#
# 16 = 4 * PROCESSES, picked off the read-ahead/latency curve (Python 3.14.5,
# 4 workers, 400 elements, one 50ms element at the head among 1ms ones, best
# of 5, drained through .distinct()):
#
#   W:     1      2      4      8     16     32     64    128
#       630ms  330ms  193ms  193ms  178ms  188ms  165ms  152ms
#
# The knee is at the worker count: below it the branches starve waiting on the
# merge and the pipeline serialises (W=1 is 4x the cost of W=4). Past it the
# curve is a slow 20% tail down to an effectively unbounded window, which is
# the wrong 20% to buy: the same number bounds the over-pull upstream of a
# short-circuiting op, so W=128 would run .peek(fn).limit(3)'s fn up to 128
# times to gain 15% on a pipeline that drains in full. 16 sits past the knee
# with 16 groups resident at most.
#
# Deliberately not exported. PROCESSES names a real Java-side concept and is
# spec'd; this names an implementation bound with no Java counterpart, and the
# tuning lever the spec gives a caller is unordered(). Revisit on a concrete
# report, not on taste.
_READ_AHEAD: int = 16


async def _maybe_aclose(thing: AsyncIterator) -> None:
    """Close an async source, if it is one of the closeable ones — some
    accepted sources (e.g. a bare async iterator implementing only __anext__)
    have no aclose(). Split out of _maybe_aclosing() below so that _guarded(),
    which has to close under a lock it cannot hold across a context manager's
    exit, still asks the same question in the same words."""
    # getattr rather than hasattr so the widened annotation still type-checks;
    # narrowing to isinstance(thing, AsyncGenerator) would type-check too but
    # would stop closing a duck-typed closeable that is not a full generator.
    aclose = getattr(thing, "aclose", None)
    if aclose is not None:
        await aclose()


@asynccontextmanager
async def _maybe_aclosing(thing: _Aiter) -> AsyncIterator[_Aiter]:
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


class _Window:
    """The bounded read-ahead shared between _guarded() and the reorder merge.

    `assigned` is the next source index to hand out, `released` the first index
    the merge has not yet released. A branch may pull only while the gap is
    under _READ_AHEAD; the merge bumps `released` and sets `event` on every
    release, waking whoever was held back.

    One object, not two counters and a condition variable, because the two
    numbers are only ever read together and the invariant between them is the
    whole point."""

    __slots__ = ("assigned", "event", "released")

    def __init__(self) -> None:
        self.assigned = 0
        self.released = 0
        self.event = asyncio.Event()

    def full(self) -> bool:
        return self.assigned - self.released >= _READ_AHEAD

    def release_one(self) -> None:
        self.released += 1
        self.event.set()


async def _guarded(source: AsyncIterator, lock: asyncio.Lock, window: _Window | None = None) -> AsyncGenerator:
    """One branch's view of a source shared with other branches: every pull and
    the final close happen under the shared lock. The source is already an
    iterator (race_through() calls aiter() once for all branches) and is only
    closed if it is closeable, so this accepts every source the sequential path
    does — not just the async generators _normalize() builds.

    With a window, each element is handed on as `(index, element)` and the
    read-ahead bound is enforced here. Both belong here for the same reason:
    this is the last point at which pull order still *is* encounter order, and
    it is already the only place a pull happens, so bounding it costs no new
    synchronisation point. Without a window — every pipeline that needs no
    ordering barrier — neither runs and the loop is what it always was."""
    try:
        while True:
            if window is None:
                async with lock:
                    try:
                        item = await anext(source)
                    except StopAsyncIteration:
                        return
                yield item
                continue
            while True:
                # wait *outside* the lock: holding it here would stall every
                # other branch's pull, including the one holding the group the
                # merge is waiting for, which is the deadlock this avoids
                while window.full():
                    window.event.clear()
                    await window.event.wait()
                async with lock:
                    # another branch may have taken the last slot while this
                    # one was waiting for the lock, so ask again before pulling
                    if window.full():
                        continue
                    try:
                        item = await anext(source)
                    except StopAsyncIteration:
                        return
                    index = window.assigned
                    window.assigned += 1
                break
            yield index, item
    finally:
        async with lock:
            await _maybe_aclose(source)


def _split_point(chain: list[Op]) -> int | None:
    """The index of the first operation that has to see the whole stream in
    encounter order, or None when there is none and the chain can race
    end-to-end.

    Two clauses, per the racing-encounter-order capability:

    - an op that SETs the ordering characteristic — `sorted()` — splits
      wherever it sits, regardless of the characteristic upstream of it. A sort
      claims its output is ordered, so it must see the whole stream to make
      that claim true. `.unordered().sorted()` is unordered at the sort's own
      position and the second clause alone would leave it in the raced head,
      sorting each branch's subset; Java's SortedOps contributes IS_ORDERED for
      the same reason, read from the other side.
    - an order_sensitive op — limit, skip, distinct — at a position where the
      fold reports the pipeline ordered. Where it does not, the caller has said
      any answer will do and the cheap order-blind path is correct.

    The first hit wins: there is at most one barrier per composition, and
    everything downstream of it already arrives in order."""
    for i, op in enumerate(chain):
        if op.ordering is Ordering.SET or (op.order_sensitive and is_ordered(chain, i)):
            return i
    return None


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


async def group_through(
    chain: list[Op],
    source: AsyncGenerator,
    state_map: StateMap,
) -> AsyncGenerator[tuple[int | None, list[Any]], None]:
    """stream_through()'s group-yielding twin, for a branch upstream of an
    ordering barrier: instead of yielding elements one at a time it yields
    `(index, outputs)` — everything the chain emitted in response to the source
    element carrying that index.

    Grouping rather than tagging is what keeps every sink in the chain
    untouched. The head chain does not preserve one output per input — filter
    drops, flat_map multiplies — so a per-element tag has no answer for either,
    while the group always does: encounter order for this chain's output is
    exactly "every output of group 0, then group 1, ...". The bridge's buffer
    is already flushed once per accept(), and that flush point *is* the group.

    A group is yielded even when it is empty, because the merge advances on
    consecutive indices and a dropped element must not leave a hole. Whatever
    end() emits is yielded last under index None, ordered after every real
    group — a buffering head op flushing at end() has no source position, and
    the end of the stream is where its output belongs."""
    bridge: GeneratorBridgeSink = GeneratorBridgeSink()
    head = _wrap_sink(chain, bridge)
    async with _maybe_aclosing(source) as src:
        await head.begin(state_map)
        # same pre-first-pull guard as _copy_into(), which carries the reasoning
        if not head.cancellation_requested():
            async for index, item in src:
                await head.accept(item)
                outputs = bridge.buffer.copy()
                bridge.buffer.clear()
                yield index, outputs
                if head.cancellation_requested():
                    break
        await head.end()
        if bridge.buffer:
            yield None, bridge.buffer.copy()
            bridge.buffer.clear()


def _releasable(pending: dict[int, list[Any]], window: _Window) -> Iterator[Any]:
    """Everything the merge can let go of now: the outputs of every group from
    the first unreleased index up to the first gap, with the window widened by
    one per group. Sync, because deciding what is releasable involves no
    awaiting — only the yielding of it does, and that is the caller's."""
    while window.released in pending:
        yield from pending.pop(window.released)
        window.release_one()


async def _release_in_order(
    branches: list[AsyncGenerator],
    window: _Window,
) -> AsyncGenerator:
    """The reorder barrier: the same FIRST_COMPLETED merge race_through() runs,
    with a buffer in front of the yield. Groups land in whatever order the
    branches finish them; this holds each one until every earlier index has
    gone out, so what leaves is the head chain's output in encounter order.

    Releasing is also what unblocks the source: every index released widens the
    read-ahead window by one, which is the only thing that ever does."""
    in_flight: dict[asyncio.Task[Any], int] = {asyncio.create_task(anext(branch)): idx for idx, branch in enumerate(branches)}
    pending: dict[int, list[Any]] = {}
    # what the branches emitted from end(), which sorts after every real group
    trailing: list[list[Any]] = []

    try:
        while in_flight:
            done, _ = await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                branch = in_flight.pop(task)
                try:
                    index, outputs = task.result()
                except StopAsyncIteration:
                    continue
                in_flight[asyncio.create_task(anext(branches[branch]))] = branch
                if index is None:
                    trailing.append(outputs)
                    continue
                pending[index] = outputs
                for out in _releasable(pending, window):
                    yield out
        for outputs in trailing:
            for out in outputs:
                yield out
    finally:
        # same clean-up as race_through()'s, plus closing the branches
        # themselves: a branch parked on the window has a finally of its own to
        # run - the shared source's close - and cancelling its in-flight
        # anext() alone would leave that to the garbage collector
        leftover = list(in_flight)
        for t in leftover:
            t.cancel()
        await asyncio.gather(*leftover, return_exceptions=True)
        for branch in branches:
            await branch.aclose()


def _resume_point(tail: list[Op]) -> int | None:
    """Where the ordered tail may start racing again: one past the first op
    that clears the encounter-order characteristic, or None when nothing in
    the tail clears it.

    Without this the barrier would cost the caller every drop of concurrency
    downstream of it, including where they have said in as many words that
    they no longer want ordering: `.sorted(c).unordered().map(fetch)` splits at
    the sort, and running the whole tail in one pass would serialise a fetch
    that unordered() exists to release. It would also leave unordered() after a
    barrier with no observable at all, and that observable is what pins
    sorted()'s restoration of the characteristic.

    Only an explicit clear resumes the race, not merely the absence of anything
    downstream that reads position. Racing an order-blind *suffix* — the map in
    `.limit(n).map(fetch)` — would scramble the pipeline's delivered order and
    so needs an answer to what an ordered racing pipeline promises its
    terminal, which is a larger question than this one; the roadmap carries it.

    The resumed portion goes back through race_through(), so a tail that clears
    and later sorts again splits again. The recursion is bounded by the chain
    being finite and each level consuming at least one op.

    A clear with nothing after it does not resume: `.limit(5).unordered()` has
    no work left to race, and racing an empty chain would only scramble the
    delivery order to buy nothing."""
    for i, op in enumerate(tail):
        if op.ordering is Ordering.CLEAR and i + 1 < len(tail):
            return i + 1
    return None


async def _run_ordered_tail(
    tail: list[Op],
    ordered: AsyncGenerator,
    state_map: StateMap,
    workers: int,
) -> AsyncGenerator:
    """Everything from the barrier onward, over the reordered stream: one
    ordered pass, up to any point the caller clears the characteristic again,
    from which it races afresh (see _resume_point())."""
    resume = _resume_point(tail)
    if resume is None:
        async for out in stream_through(tail, ordered, state_map):
            yield out
        return
    async for out in race_through(tail[resume:], stream_through(tail[:resume], ordered, state_map), workers):
        yield out


async def race_through(chain: list[Op], source: AsyncGenerator, workers: int) -> AsyncGenerator:
    """The same chain, run by `workers` branches racing over one shared source.
    Elements are yielded as branches finish them, so encounter order is not
    preserved — unless the chain contains an operation that needs it (see
    _split_point()), in which case the chain is split there: the head races as
    ever, _release_in_order() restores encounter order at the merge, and the
    tail runs as one ordered pass over that. There is still one executor; the
    split is internal and nothing outside this function knows of it."""
    state_map: StateMap = {}
    for op in chain:
        state = op.make_shared_state()
        if state is not None:
            state_map[op] = state
    lock = asyncio.Lock()
    # aiter() once, here, and not inside _guarded(): _guarded() runs once per
    # branch, so a source whose __aiter__ hands back a fresh iterator each call
    # would give every branch its own copy and yield the elements `workers`
    # times over. One iterator, shared under the lock, is what racing means.
    shared = aiter(source)

    split = _split_point(chain)
    if split is not None:
        # race the head, restore encounter order at the merge, hand the rest
        # to the tail. One state map for the whole chain either way: head ops
        # share theirs across branches, tail ops are built once and so share
        # it with nobody, which comes to the same thing.
        window = _Window()
        head = [group_through(chain[:split], _guarded(shared, lock, window), state_map) for _ in range(workers)]
        async for out in _run_ordered_tail(chain[split:], _release_in_order(head, window), state_map, workers):
            yield out
        return

    branches = [stream_through(chain, _guarded(shared, lock), state_map) for _ in range(workers)]
    # the in-flight anext() per branch, keyed by task so a completed one
    # maps back to its branch in O(1); it doubles as the waitlist and as the
    # "any branch still running" test, so nothing here is scanned or rebuilt
    # per element. A branch that raised StopAsyncIteration is simply not
    # re-armed, which is what drains this dict to empty.
    in_flight: dict[asyncio.Task[Any], int] = {asyncio.create_task(anext(branch)): idx for idx, branch in enumerate(branches)}

    try:
        while in_flight:
            done, _ = await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                branch = in_flight.pop(task)
                try:
                    result = task.result()
                except StopAsyncIteration:
                    continue
                in_flight[asyncio.create_task(anext(branches[branch]))] = branch
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

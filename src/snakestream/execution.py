"""How a composed chain actually runs. Four primitives do the work:
stream_through() (push in, pull out, lazily), race_through() (N branches
racing one shared source), feed_through() (fused push straight to a
terminal, nothing buffered) and drain() (any generator into a terminal).
race_through() has a second gear: where encounter order has to be restored, it
splits the chain, races everything upstream of the split and reorders at the
merge — see ordering.py's _split_point() and this module's _release_in_order().
Two things ask for it. An operation whose answer depends on an element's
position splits at its own index, and only that operation runs in the ordered
pass; everything after it races again. A terminal that can tell what order
elements reach it in splits at the end of the chain, so every operation still
races and only delivery is reordered.
Both of racing's merges - the plain one and the reorder barrier - drive their
branches through _racing_branches(), which owns the in-flight anext() per
branch and its teardown. It is scaffolding around the primitives rather than a
fifth one: it decides nothing about what a pipeline produces, only that a merge
arms and tears down its branch tasks the same way whichever loop is consuming
them.
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

from snakestream.ordering import OrderDemand, is_ordered, _split_point
from snakestream.sink import GeneratorBridgeSink, Op, Sink, TerminalSink
from snakestream.type import StateMap, T, _Aiter


# How many branches the racing executor fans a chain out across. Bound into
# RACING below at import time, which is where it was always effectively bound:
# the old _parallel() took it as a default argument value.
PROCESSES: int = 4

# How far ahead of the last released group one branch may pull, in source
# elements, when the racing executor is honouring encounter order. Ordering
# means holding a finished element until every earlier one has been released,
# and without a bound one slow first element draws the whole source into
# memory; this is the analogue of the leaf partitioning that bounds Java's
# fork-join, which the one-shared-source design here otherwise lacks.
#
# Per worker, not a bare number, because the curve knees at the worker count
# and so it is the ratio that governs (Python 3.14.5, 4 workers, 400 elements,
# one 50ms element at the head among 1ms ones, best of 5, drained through
# .distinct(); the axis is the window expressed in multiples of the worker
# count, which is how it was measured):
#
#   W/worker:  0.25   0.5     1      2      4      8     16     32
#             630ms  330ms  193ms  193ms  178ms  188ms  165ms  152ms
#
# The knee is at 1.0 -- one slot per worker. Below it the branches starve
# waiting on the merge and the pipeline serialises (0.25/worker is 4x the cost
# of 1/worker). Past it the curve is a slow 20% tail down to an effectively
# unbounded window, which is the wrong 20% to buy: the same number bounds the
# over-pull upstream of a short-circuiting op, so 32/worker would run
# .peek(fn).limit(3)'s fn up to 128 times to gain 15% on a pipeline that drains
# in full. 4 sits past the knee, holding at most four groups per branch.
#
# Not exported, and spec'd that way rather than argued for here: the
# racing-encounter-order capability requires that no public name read or set
# this bound, and gives a caller unordered() and sequential() as the levers
# instead. That requirement is what makes retuning this a measurement rather
# than a compatibility question.
_IN_FLIGHT_PER_WORKER: int = 4


def _in_flight(workers: int) -> int:
    """The in-flight bound for a race across `workers` branches: elements
    pulled from the shared source but not yet released by the merge. 16 at the
    default worker count, so that is how many groups a default racing pipeline
    holds resident at most.

    A function rather than a derived constant so the derivation has one site,
    which is the seam the bound's tests read and the one a test shrinking the
    window to a single slot replaces."""
    return _IN_FLIGHT_PER_WORKER * workers


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


@asynccontextmanager
async def _racing_branches(branches: list[AsyncGenerator]) -> AsyncIterator[dict[asyncio.Task[Any], int]]:
    """The branch-task lifecycle both racing merges share: one in-flight
    anext() per branch, armed on the way in and torn down on the way out.

    What it yields is the merge's whole working set - the in-flight anext()
    per branch, keyed by task so a completed one maps back to its branch in
    O(1). It doubles as the waitlist and as the "any branch still running"
    test, so nothing in a caller's loop is scanned or rebuilt per element. A
    branch that raised StopAsyncIteration is simply not re-armed, which is
    what drains the dict to empty. Callers re-arm through it directly; only
    the arming and the teardown live here, because only those are identical
    between them - race_through() yields a completed result as it stands and
    _release_in_order() buffers it by source index, and that difference is
    the whole of what each loop is for.

    The finally is load-bearing for the same reason _maybe_aclosing()'s is,
    one function up: a merge is abandoned far more often than it is drained.
    Every short-circuiting terminal leaves through it - find_any(), the
    *_match family, a limit() that filled - and so does any branch that
    raised. A task left uncancelled there leaks, and one cancelled but never
    gathered leaves its exception unretrieved.

    Closing the branches is part of the teardown on *both* paths, which is
    the one behaviour this extraction settles rather than preserves. It was
    the barrier's alone before, on a reason that names the window: a branch
    parked on a full window has a finally of its own to run - the shared
    source's close - and cancelling its in-flight anext() does not reach a
    branch that has no anext() outstanding. That reason does not extend to
    the unwindowed path, but nothing established the converse either, and
    closing is the conservative direction: aclose() on an exhausted or
    already-closing async generator is a no-op, so a branch cannot be closed
    twice. racing-encounter-order requires the shared source be closed
    exactly as it is without a barrier, and it is now one mechanism that
    makes that true rather than two that happen to agree."""
    in_flight: dict[asyncio.Task[Any], int] = {asyncio.create_task(anext(branch)): idx for idx, branch in enumerate(branches)}
    try:
        yield in_flight
    finally:
        leftover = list(in_flight)
        for task in leftover:
            task.cancel()
        await asyncio.gather(*leftover, return_exceptions=True)
        for branch in branches:
            await branch.aclose()


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

    Three counters, each with one job. `assigned` is the next source index to
    hand out. `released` is the reorder cursor `_releasable()` walks: the first
    index the merge has not yet released. `outstanding` is occupancy: the
    number of slots claimed by `take()` and not yet returned by `release_one()`
    or `give_back()`. Occupancy cannot be derived from the other two, because a
    slot is claimed by `take()` before an index is assigned -- see design.md
    Decision 2 in take-window-slots-atomically.

    `size` is fixed at construction, from _in_flight() and the branch count, so
    a pipeline runs to completion under the bound it started with -- reading it
    per pull would let a rebind take effect part-way through a race, which is a
    state no requirement describes and nothing needs."""

    __slots__ = ("assigned", "event", "outstanding", "released", "size")

    def __init__(self, size: int) -> None:
        self.assigned = 0
        self.released = 0
        self.outstanding = 0
        self.size = size
        self.event = asyncio.Event()

    def take(self) -> bool:
        """Atomically claim a slot if one is free. Atomic because the body
        contains no `await`, so nothing can run between the check and the
        increment -- the same reason `_LimitSink.accept()`'s reserve-before-push
        is atomic."""
        if self.outstanding >= self.size:
            return False
        self.outstanding += 1
        return True

    def give_back(self) -> None:
        """Return a slot claimed by take() that will produce no group -- the
        mirror of the claim, not of release_one(): it advances no cursor."""
        self.outstanding -= 1
        self.event.set()

    def release_one(self) -> None:
        self.released += 1
        self.outstanding -= 1
        self.event.set()


async def _guarded(source: AsyncIterator, lock: asyncio.Lock, window: _Window | None = None) -> AsyncGenerator:
    """One branch's view of a source shared with other branches: every pull and
    the final close happen under the shared lock. The source is already an
    iterator (race_through() calls aiter() once for all branches) and is only
    closed if it is closeable, so this accepts every source the sequential path
    does — not just the async generators _normalize() builds.

    With a window, each element is handed on as `(index, element)` and the
    window's bound on in-flight elements is enforced here. Both belong here for
    the same reason: this is the last point at which pull order still *is*
    encounter order, and it is already the only place a pull happens, so
    bounding it costs no new synchronisation point. The slot is claimed before
    the pull, which makes the bound conservative rather than exact: it counts a
    pull about to happen as well as every element pulled and not released.
    Without a window — every pipeline that needs no ordering barrier — neither
    runs and the loop is what it always was."""
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
            # wait *outside* the lock: holding it here would stall every
            # other branch's pull, including the one holding the group the
            # merge is waiting for, which is the deadlock this avoids
            while not window.take():
                window.event.clear()
                await window.event.wait()
            async with lock:
                try:
                    item = await anext(source)
                except StopAsyncIteration:
                    # no group will ever release this slot, so return it now
                    # rather than shrink the window for the rest of the run
                    window.give_back()
                    return
                index = window.assigned
                window.assigned += 1
            yield index, item
    finally:
        async with lock:
            await _maybe_aclose(source)


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
    pending: dict[int, list[Any]] = {}
    # what the branches emitted from end(), which sorts after every real group
    trailing: list[list[Any]] = []

    async with _racing_branches(branches) as in_flight:
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


async def _run_ordered_tail(
    tail: list[Op],
    ordered: AsyncGenerator,
    state_map: StateMap,
    workers: int,
    demand: OrderDemand,
) -> AsyncGenerator:
    """Everything from the barrier onward, over the reordered stream.

    The barrier op alone runs in a single ordered pass — it is the one op in
    the tail that asked to see the whole stream in order — and everything after
    it races afresh. That the suffix may be order-blind is no longer an
    objection: an order-observing terminal gets its own barrier when the
    resumed race splits at len(), so `.limit(n).map(fetch)` gets its
    concurrency back without scrambling what the caller receives. This replaced
    an earlier rule that resumed only at an explicit unordered(), which cost
    the caller every drop of concurrency downstream of a barrier.

    `ordered_in` for the resumed race is the fold across the barrier op itself:
    sorted() SETs, limit/skip/distinct PRESERVE what the barrier restored, and
    the reordered stream arriving here is ordered by construction.

    A tail of fewer than two ops has nothing left to race — an empty one is the
    delivery-barrier case, where the reordered stream *is* the answer."""
    barrier, rest = tail[:1], tail[1:]
    if not rest:
        async for out in stream_through(barrier, ordered, state_map):
            yield out
        return
    async for out in race_through(
        rest,
        stream_through(barrier, ordered, state_map),
        workers,
        demand,
        is_ordered(barrier),
    ):
        yield out


async def race_through(
    chain: list[Op],
    source: AsyncGenerator,
    workers: int,
    demand: OrderDemand,
    ordered_in: bool = True,
) -> AsyncGenerator:
    """The same chain, run by `workers` branches racing over one shared source.
    Elements are yielded as branches finish them, so encounter order is not
    preserved — unless something needs it (see _split_point()), in which case
    the chain is split there: the head races as ever, _release_in_order()
    restores encounter order at the merge, and _run_ordered_tail() takes the
    rest.

    Two things can need it, and the split expresses both. An *operation* that
    reads position splits at its own index. The *terminal* splits at len(chain)
    when its `demand` says it can tell — every op still races and only delivery
    is reordered.

    `ordered_in` is the pipeline's ordering characteristic entering this chain,
    True for a whole pipeline and carried across the split for a resumed tail.

    There is still one executor; the split is internal and nothing outside this
    function knows of it.

    What the delivery barrier costs, and what the tail rule buys (Python
    3.14.5, 4 workers, best of 5 / 3):

      collect(to_list()) over 20,000 elements, map(x + 1) — no per-element wait,
      so this is the machinery's own cost and nothing else:

        racing, ordered delivery      10.01 us/element
        racing, unordered()            7.51 us/element   1.33x cheaper
        racing, count() (order-blind)  7.57 us/element   pays nothing, as spec'd

      the same chain over 40 elements at 10ms each — the shape racing exists
      for, where the branches have something to overlap:

        racing, ordered delivery      105.5 ms
        racing, unordered()           106.9 ms
        sequential                    420.0 ms

      that second shape says less than it appears to. Every element costs the
      same 10ms, so elements complete in the order they were pulled and the
      reorder buffer never holds one back: the barrier is free by construction
      there, not by measurement, and a uniform-latency benchmark cannot detect
      what it costs. Under *tail* latency it does cost something, by filling the
      in-flight window behind a straggler while the branches idle (200
      elements, 90% at 2ms and 10% at 50ms, 4 workers, ideal ~424 ms):

        racing, ordered delivery      545.5 ms
        racing, order-blind collector 487.2 ms   1.12x

      so the +33% on the cheap chain is charged only where per-element work is
      too cheap to race in the first place — but the barrier is not free on work
      worth racing either, once the latencies are skewed, as real IO's are. That
      is why the order-blind collectors declare UNORDERED (roadmap question 4,
      closed 2026-08-31) rather than leaving the mark to buy nothing.
      unordered() remains the lever, and remains measurably one.

      Where the ordered path's cost actually sits, if anyone sets out to
      cheapen it (2026-08-28, taken while pricing the rejected alternative in
      order-min-max-tie-breaks; 20,000 elements, map(x + 1), 4 workers, Python
      3.14.5, best of 5, all three draining into the same counting sink):

        baseline (unordered)   7.32 us/element  stream_through + plain merge
        tagged, unmerged       8.03 us/element  group_through  + plain merge      +9.7%
        reorder barrier        8.71 us/element  group_through  + _release_in_order +19%

      Two roughly equal halves, not one: tagging costs 0.71 us/element and
      reordering 0.68. group_through() is the harder to remove -- the chain
      drops and multiplies, so a per-element tag has no answer and the group is
      the invariant. It is also a whole-path number, paying off for every
      order-observing terminal at once, which is why order-min-max-tie-breaks
      declined to spend it on two.

      One shape is worth recording so it is not re-investigated: an *empty*
      chain under .parallel(). Spinning four branches and a shared source up to
      deliver a source nothing transforms costs far more than one ordered pass
      (200 elements, best of 5, us per call):

        find_first()             9.5 seq    132.7 par
        collect(to_list())      78.2 seq   2045.4 par
        count()                    -       1455.9 par

      count() declares OrderDemand.NONE, takes no split and engages no barrier,
      and still pays almost all of it -- so this is the branch-setup cost of
      racing itself, not the reorder barrier, and it has been there since
      delivery ordering landed. A fast path keyed on the barrier would fix
      nothing. The shape is a caller asking to parallelise a pipeline with
      nothing in it to parallelise.

      .parallel().limit(8).map(50ms), which the old resume rule ran in a single
      ordered pass because the suffix read no position:

        before  403.4 ms   (8 x 50ms, serial)
        after   101.7 ms   (4 branches, at the floor)"""
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

    split = _split_point(chain, demand, ordered_in)
    if split is not None:
        # race the head, restore encounter order at the merge, hand the rest
        # to the tail. One state map for the whole chain either way: head ops
        # share theirs across branches, tail ops are built once and so share
        # it with nobody, which comes to the same thing.
        window = _Window(_in_flight(workers))
        head = [group_through(chain[:split], _guarded(shared, lock, window), state_map) for _ in range(workers)]
        async for out in _run_ordered_tail(chain[split:], _release_in_order(head, window), state_map, workers, demand):
            yield out
        return

    branches = [stream_through(chain, _guarded(shared, lock), state_map) for _ in range(workers)]

    async with _racing_branches(branches) as in_flight:
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
        """The general form: compose, then drain into the terminal. Correct for
        any executor; Racing uses it unchanged."""
        return await drain(self.elements(chain, source, demand), terminal)


class Sequential(Executor):
    is_parallel = False

    # demand is accepted and ignored throughout: a single ordered pass
    # delivers in encounter order whether or not anyone is looking. The
    # parameter is on the protocol because the *racing* executor needs it, and
    # a caller must be able to state the demand without knowing which executor
    # will read it.

    def elements(self, chain: list[Op], source: AsyncGenerator, demand: OrderDemand) -> AsyncGenerator:
        return stream_through(chain, source)

    async def value(self, chain: list[Op], source: AsyncGenerator, terminal: TerminalSink[Any], demand: OrderDemand) -> Any:
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

    def elements(self, chain: list[Op], source: AsyncGenerator, demand: OrderDemand) -> AsyncGenerator:
        return race_through(chain, source, self.workers, demand)

    # value() is inherited: each racing branch owns its own sink chain, so
    # there is no single chain to fuse a terminal onto. The general form is
    # the only form available here, which is why it is the base.


SEQUENTIAL = Sequential()
RACING = Racing(PROCESSES)

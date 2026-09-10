"""fork_join_through() is where parallel execution actually happens: a
Spliterator-decomposed source, run batch by batch, each batch's chain on its
own worker thread via asyncio.to_thread(). Contiguous batches never scramble
encounter order the way the old racing executor's branches did, so there is no
merge to restore it at — split_point() (ordering.py) still finds the one place
a stateful op (sorted/distinct/limit/skip) needs a *global* view no per-batch
chain can give it, and the chain still splits there, but what runs at the
split is a single ordinary pass over the concatenated batch output, not a
reorder buffer. See design.md (fork-join-executor-and-spliterator) for the two
declines this shape supports without one: round-level dispatch stays ordered
(_fork_join_ordered_batches) only when something downstream needs it, and
drops to a completion-ordered sliding window (_fork_join_unordered_batches)
otherwise, so an order-blind short-circuiting terminal is never held back by
an unrelated slow batch elsewhere in the same round."""

from __future__ import annotations

import asyncio
from typing import Any
from collections.abc import AsyncGenerator, AsyncIterator

from snakestream.ordering import OrderDemand, is_ordered, split_point
from snakestream.pipeline import maybe_aclosing, stream_through, wrap_sink
from snakestream.sink import GeneratorBridgeSink, Op, Sink, TerminalSink
from snakestream.spliterator import BATCH_SIZE, batch
from snakestream.type import StateMap

# How many worker threads the fork-join executor fans a chain's batches out
# across. Bound into FORK_JOIN (execution.py) at import time. Named WORKERS,
# not PROCESSES: the old name was kept against the possibility that real
# parallelism would arrive as a process pool - it arrived as threads, so the
# name is now simply wrong (design.md, fork-join-executor-and-spliterator,
# decision 4). Renamed rather than aliased: anything still importing
# PROCESSES from here breaks loudly.
WORKERS: int = 4


async def _gather_or_cancel(tasks: list[asyncio.Task[Any]]) -> list[Any]:
    """gather() a batch of already-running tasks; on a first exception, cancel
    every sibling and await them with return_exceptions=True before
    re-raising, so nothing is left with an unretrieved exception and the
    original exception (with its own traceback) is what propagates, not a
    wrapper. Three sites share this exactly; a fourth
    (_fork_join_unordered_batches) cancels a live in-flight window on the way
    out of a generator rather than awaiting a completed gather, a different
    enough shape that it is not folded in here."""
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def _shared_state(chain: list[Op]) -> StateMap:
    """Build the state map fork/join shares across every batch of a call,
    regardless of which round or window slot a batch lands in - the same
    requirement RACING's state_map met, now honoured by ops.py's
    threading.Lock-guarded containers instead of asyncio's single-event-loop
    cooperative scheduling (see design.md, decision 8). Fork/join's alone: the
    sequential path never builds one, passing {} instead."""
    state_map: StateMap = {}
    for op in chain:
        state = op.make_shared_state()
        if state is not None:
            state_map[op] = state
    return state_map


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
    head = wrap_sink(chain, bridge)
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
    then awaited with return_exceptions=True before re-raising - see
    _gather_or_cancel()."""
    tasks = [asyncio.create_task(_run_element(chain, item, state_map)) for item in items]
    results = await _gather_or_cancel(tasks)
    return [out for outputs in results for out in outputs]


def _run_batch_sync(chain: list[Op], items: list[Any], state_map: StateMap) -> list[Any]:
    """asyncio.to_thread()'s callable — a fresh event loop for this batch
    alone, since the shared upstream source can't cross threads but a batch
    is already a plain materialised list by the time it gets here, and has
    nothing loop-bound left about it."""
    return asyncio.run(_run_batch_async(chain, items, state_map))


async def _accumulate_into(head: Sink[Any], items: list[Any], state_map: StateMap) -> None:
    """Like pipeline._copy_into(), but over an already-materialised batch and
    without the final end(): a partitioned terminal's peer must not be
    finished (its container, not its result, is what gets merged - see
    _run_partition_sync(), its one caller), so the caller drives
    begin()/accept() only and finishes the head once, after every peer has
    been merged into it."""
    await head.begin(state_map)
    if not head.cancellation_requested():
        for item in items:
            await head.accept(item)
            if head.cancellation_requested():
                break


def _run_partition_sync(chain: list[Op], items: list[Any], state_map: StateMap, head: TerminalSink[Any]) -> TerminalSink[Any]:
    """asyncio.to_thread()'s callable for a partitioned batch: race the
    chain per element exactly as _run_batch_sync() does - _run_batch_async()
    is unchanged and reused as-is - which is what preserves the intra-batch
    I/O concurrency fork-join's speedup on I/O-bound work depends on (a
    sequential push through the chain here regressed a slow-mapper benchmark
    by ~4x measured, before this shape was chosen). The batch's already-
    transformed outputs are then folded into a fresh peer accumulation
    sequentially: a terminal's accept() is not safe to call concurrently, but
    accumulation itself is cheap once the chain's own work is done. Returns
    the peer for the caller to merge, in batch order, on the main loop; the
    peer is never finished here (see _accumulate_into())."""

    async def _run() -> TerminalSink[Any]:
        outputs = await _run_batch_async(chain, items, state_map)
        peer = head.new_partition()
        await _accumulate_into(peer, outputs, state_map)
        return peer

    return asyncio.run(_run())


async def _run_partition_round(
    chain: list[Op], round_batches: list[list[Any]], state_map: StateMap, head: TerminalSink[Any]
) -> list[TerminalSink[Any]]:
    """Every batch in a round, partitioned on its own thread, waited for
    together - _run_round()'s shape, over _run_partition_sync() instead of
    _run_batch_sync(). Cancellation on a first exception is _gather_or_cancel()'s."""
    tasks = [
        asyncio.create_task(asyncio.to_thread(_run_partition_sync, chain, items, state_map, head)) for items in round_batches
    ]
    return await _gather_or_cancel(tasks)


async def fork_join_partitioned(chain: list[Op], source: AsyncGenerator, workers: int, head: TerminalSink[Any]) -> Any:
    """Drive a partitioning terminal directly, bypassing elements(): each
    round's batches accumulate independently, one per worker thread, and are
    merged into `head` by left fold in batch order (design decision 2,
    make-combiners-live) - regardless of unordered(), which the
    parallel-reduction spec states explicitly is not license to merge out of
    order. Contiguous, in-sequence batches are what make that sound on
    associativity alone (proposal.md, Why)."""
    state_map = _shared_state(chain)
    await head.begin(state_map)
    async with maybe_aclosing(aiter(source)) as src:
        # same pre-first-pull guard as pipeline._copy_into(): a terminal
        # cancelled before it has merged anything (none of today's
        # partitioning terminals short-circuit, but the protocol does not
        # assume none ever will) must not pull even one batch. An `async for`
        # over _rounds() alone would pull round one before this body runs, so
        # the guard stays explicit here rather than folding into the loop,
        # with a break at the end of the body standing in for _rounds()'s own
        # stop condition once cancellation happens mid-stream. Both
        # cancellation checks are therefore unreachable today - pragma'd
        # rather than left to silently erode the coverage gate - and stay
        # ready for a future short-circuiting, combiner-supplying terminal.
        if not head.cancellation_requested():  # pragma: no branch
            async for round_batches in _rounds(src, workers):
                peers = await _run_partition_round(chain, round_batches, state_map, head)
                for peer in peers:
                    await head.merge_from(peer)
                    if head.cancellation_requested():  # pragma: no cover
                        break
                if head.cancellation_requested():  # pragma: no cover
                    break
    await head.end()
    return head.result()


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


async def _rounds(source: AsyncIterator, workers: int) -> AsyncGenerator[list[list[Any]]]:
    """The round loop shared by _fork_join_ordered_batches() and
    fork_join_partitioned(): seed, pull, yield, stop on a short round, ramp.
    Each caller supplies its own genuinely different half - what it does with
    a round's results.

    Geometric ramp, not a one-step jump to the steady state: one element per
    worker in round one, x8 per refill thereafter, capped at the same
    BATCH_SIZE Spliterator.try_split() uses (design.md decision 1: one number
    for both, over splitting it). It saturates in log_8(BATCH_SIZE) refills
    regardless of source length, so a draining pipeline pays a fixed, small
    toll for the climb rather than reaching the workers * BATCH_SIZE ceiling
    immediately; a consumer that stops early - a short-circuiting terminal, or
    a caller breaking out of iterator() - is charged only for how far the
    climb had gotten, not for the ceiling (measured in
    ramp-batch-growth-geometrically, which inverted task 7.2's rejection of an
    arithmetic version of this same idea). The 8 is one retunable constant
    shared by every ramp site, including _fork_join_unordered_batches()'s own
    sliding-window ramp, which cannot use this generator (it refills
    continuously rather than in rounds) but ramps by the same rule.

    Holds no resource of its own - `source` is owned by the caller's
    maybe_aclosing() - so a caller breaking out of the `async for` needs no
    aclosing() around it."""
    size = 1
    while True:
        round_batches = await _pull_round(source, workers, size)
        if not round_batches:
            return
        yield round_batches
        if len(round_batches) < workers:
            return
        size = min(size * 8, BATCH_SIZE)


async def _run_round(chain: list[Op], round_batches: list[list[Any]], state_map: StateMap) -> list[list[Any]]:
    """Every batch in a round, on its own thread via _run_batch_sync(), waited
    for together. Cancellation on a first exception is _gather_or_cancel()'s."""
    tasks = [asyncio.create_task(asyncio.to_thread(_run_batch_sync, chain, items, state_map)) for items in round_batches]
    return await _gather_or_cancel(tasks)


async def _fork_join_ordered_batches(src: AsyncIterator, chain: list[Op], workers: int, state_map: StateMap) -> AsyncGenerator:
    """One round of up to `workers` contiguous batches at a time — _rounds(),
    then _run_round() — yielded in batch order once the whole round has
    returned. Batch order is encounter order for free: batches are contiguous
    and pulled in sequence, so there is no merge to get wrong and nothing to
    reorder afterwards. Used whenever something downstream — an op needing a
    global view, or a terminal demanding it — needs that order; see
    _fork_join_batches()."""
    async for round_batches in _rounds(src, workers):
        results = await _run_round(chain, round_batches, state_map)
        for outputs in results:
            for out in outputs:
                yield out


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
    size = 1

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
            # same ramp as _rounds() - see its comment for the rule; the 8 is
            # one retunable constant shared by every ramp site (design.md
            # decision 4, ramp-batch-growth-geometrically). This is a sliding
            # window rather than a round loop, so it cannot use _rounds()
            # itself and keeps its own line.
            size = min(size * 8, BATCH_SIZE)
            await _fill()
    except BaseException:
        # same cancel-siblings-and-drain shape as _gather_or_cancel(), but
        # over a live in-flight window on the way out of a generator rather
        # than a completed gather() call - different enough not to share it
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
    single-event-loop cooperative scheduling; see _shared_state().

    aiter(source) once, here — not inside batch() — for the same reason
    _race_through() called it exactly once on `shared`: source may be a bare
    AsyncIterable whose __aiter__() returns a fresh iterator each call rather
    than self (stream-execution-model's source-acceptance requirement covers
    exactly this shape), and anext() requires an iterator, not merely an
    iterable. One conversion up front, reused by every batch() pull."""
    state_map = _shared_state(chain)
    async with maybe_aclosing(aiter(source)) as src:
        through = _fork_join_ordered_batches if ordered else _fork_join_unordered_batches
        async for out in through(src, chain, workers, state_map):
            yield out


async def fork_join_through(
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
        async for out in stream_through(barrier, ordered):
            yield out
        return
    async for out in fork_join_through(rest, stream_through(barrier, ordered), workers, demand, is_ordered(barrier)):
        yield out

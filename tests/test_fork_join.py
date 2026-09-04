"""Targeted verification for FORK_JOIN (fork-join-executor-and-spliterator,
tasks 2.1-2.7). The old racing test files are the subject of section 3's
audit and are not touched here; this file covers only what section 2's own
tasks ask to be verified about the new executor directly."""

import asyncio
import threading
import time

import pytest

from snakestream import Stream
from snakestream.collectors import to_list
from snakestream.execution import _FIRST_BATCH_SIZE, FORK_JOIN, SEQUENTIAL
from snakestream.spliterator import BATCH_SIZE


# --- 2.2 asyncio.gather preserves intra-batch order, including flat_map ----


@pytest.mark.asyncio
async def test_parallel_map_preserves_encounter_order_with_uneven_latency() -> None:
    async def uneven(x: int) -> int:
        await asyncio.sleep(0.02 if x % 3 == 0 else 0.001)
        return x

    source = list(range(30))
    lst = await Stream.of(source).parallel().map(uneven).collect(to_list())

    assert lst == source


@pytest.mark.asyncio
async def test_parallel_flat_map_preserves_encounter_order() -> None:
    lst = await Stream.of([1, 2, 3, 4]).parallel().flat_map(lambda x: Stream.of([x, x * 10])).collect(to_list())

    assert lst == [1, 10, 2, 20, 3, 30, 4, 40]


@pytest.mark.asyncio
async def test_parallel_flat_map_preserves_order_under_uneven_latency() -> None:
    # flat_map()'s mapper itself must be sync (it returns a Stream, not an
    # Awaitable[Stream]) - the timing variance instead lives in the inner
    # stream's own source, iterated inside _FlatMapSink.accept()
    async def inner_source(x: int):
        await asyncio.sleep(0.02 if x % 3 == 0 else 0.001)
        yield x
        yield x + 100

    def inner(x: int) -> Stream:
        return Stream.of(inner_source(x))

    source = list(range(20))
    lst = await Stream.of(source).parallel().flat_map(inner).collect(to_list())

    expected = [y for x in source for y in (x, x + 100)]
    assert lst == expected


# --- 2.3 batch size is the single read-ahead bound --------------------------


@pytest.mark.asyncio
async def test_in_flight_elements_are_bounded_by_workers_times_batch_size() -> None:
    in_flight = 0
    max_in_flight = 0
    # a plain threading.Lock, not asyncio.Lock: each batch runs its own
    # asyncio.run() on its own OS thread, so this counter is genuinely
    # shared across event loops - asyncio.Lock only binds to (and then
    # rejects any other) loop once actually contended, which an
    # increment/decrement this short rarely triggers, making that misuse
    # a flaky pass rather than a reliable one
    lock = threading.Lock()

    async def track(x: int) -> int:
        nonlocal in_flight, max_in_flight
        with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        with lock:
            in_flight -= 1
        return x

    source = list(range(500))
    await Stream.of(source).parallel().map(track).collect(to_list())

    # steady-state rounds pull workers batches of BATCH_SIZE each; the first
    # round is smaller (_FIRST_BATCH_SIZE), so the observed peak can only be
    # at or under workers * BATCH_SIZE, never over it
    assert max_in_flight <= FORK_JOIN.workers * BATCH_SIZE


# --- 2.4 the first batch is small: a short-circuiting terminal must not ----
# --- over-pull a full BATCH_SIZE-per-worker round ---------------------------


@pytest.mark.asyncio
async def test_limit_under_parallel_does_not_pull_a_full_batch_size_per_worker() -> None:
    pulled = 0

    async def counting_source():
        nonlocal pulled
        for i in range(10_000):
            pulled += 1
            yield i

    lst = await Stream.of(counting_source()).parallel().limit(3).collect(to_list())

    assert lst == [0, 1, 2]
    # bounded by the small first-round pull, not by workers * BATCH_SIZE
    assert pulled < BATCH_SIZE


@pytest.mark.asyncio
async def test_limit_zero_under_parallel_pulls_nothing() -> None:
    seen: list[int] = []

    lst = await Stream.of([1, 2, 3, 4]).parallel().peek(seen.append).limit(0).collect(to_list())

    assert lst == []
    assert seen == []


# --- order-blind terminals don't wait behind an unrelated slow batch --------
# --- (design.md decision 10) -------------------------------------------------


@pytest.mark.asyncio
async def test_an_order_blind_terminal_does_not_wait_on_a_slow_batch_elsewhere() -> None:
    # a slow element and the terminal's target land in *different* batches
    # (target index 17 is past the first _FIRST_BATCH_SIZE=16 batch that
    # index 0's slow element occupies) - the case design.md decision 10 fixed
    async def endless():
        i = 0
        while True:
            yield i
            i += 1

    async def one_slow_element(n: int) -> int:
        await asyncio.sleep(0.4 if n == 0 else 0.0)
        return n

    result = await asyncio.wait_for(
        Stream.of(endless()).parallel().map(one_slow_element).any_match(lambda n: n == 17),
        timeout=0.2,
    )

    assert result is True


# --- 2.5 exception propagation across a worker thread ----------------------


@pytest.mark.asyncio
async def test_an_exception_in_a_worker_propagates_with_its_type_and_message() -> None:
    def boom(x: int) -> int:
        if x == 5:
            raise ValueError("kaboom")
        return x

    with pytest.raises(ValueError, match="kaboom") as excinfo:
        await Stream.of(list(range(20))).parallel().map(boom).collect(to_list())

    # traceback intact across the thread boundary: the frame that actually
    # raised is still in it, not swallowed into an opaque wrapper
    frame_names = [frame.name for frame in excinfo.traceback]
    assert "boom" in frame_names


@pytest.mark.asyncio
async def test_an_exception_in_one_batch_does_not_leave_unretrieved_exceptions(recwarn) -> None:
    def boom(x: int) -> int:
        if x == 50:
            raise ValueError("kaboom")
        return x

    with pytest.raises(ValueError, match="kaboom"):
        await Stream.of(list(range(200))).parallel().map(boom).collect(to_list())

    # let any tasks whose exception wasn't retrieved get garbage collected
    # and emit their warning before we check for one
    import gc

    gc.collect()
    await asyncio.sleep(0)
    gc.collect()

    messages = [str(w.message) for w in recwarn.list]
    assert not any("was never retrieved" in m for m in messages)


# --- design.md decision 8: threading.Lock-guarded shared state under real --
# --- concurrent access (limit/skip/distinct sharing state across batches) --


@pytest.mark.asyncio
async def test_limit_skip_distinct_stay_correct_under_concurrent_batch_access() -> None:
    # unordered() is the load-bearing part of this test: it is what keeps
    # limit()/skip()/distinct() inside the parallel batches (sharing
    # _GuardedCounter/_GuardedSet across genuinely concurrent OS threads,
    # design.md decision 8) rather than pulled out to split_point()'s single
    # ordered pass, where nothing contends and a missing lock would not show.
    #
    # This raises the odds of catching a race; it cannot prove one absent.
    # A flaky failure here on a future change is real signal - do not read a
    # green run as license to remove a lock (_GuardedCounter's own docstring
    # explains why Box, elsewhere in this codebase, correctly has none, which
    # invites exactly that inverse edit) or to move `await downstream.accept
    # (element)` inside the `with state.lock:` block, which would serialise
    # the batches it is meant to let run concurrently, or deadlock them.
    #
    # Runs on both CI legs deliberately, not skipped on the GIL build: a
    # build-conditional test is the shape free-threaded-support's own spec
    # rules out, and the functional contract (exact cardinality) is worth
    # asserting on the GIL leg too, for close to free.
    n, trials = 5000, 12

    for _ in range(trials):
        limited = await Stream.of(list(range(n))).parallel().unordered().limit(100).to_array()
        assert len(limited) == 100
        assert len(set(limited)) == 100

        skipped = await Stream.of(list(range(n))).parallel().unordered().skip(n - 100).to_array()
        assert len(skipped) == 100
        assert len(set(skipped)) == 100

        distinct = await Stream.of([i % 250 for i in range(n)]).parallel().unordered().distinct().to_array()
        assert len(distinct) == 250
        assert len(set(distinct)) == 250


# --- 2.6 .parallel() binds FORK_JOIN, and mode switches stay composable ----


@pytest.mark.asyncio
async def test_parallel_reports_is_parallel_true() -> None:
    assert Stream.of([1, 2, 3]).parallel().is_parallel() is True


@pytest.mark.asyncio
async def test_parallel_stream_uses_fork_join() -> None:
    stream = Stream.of([1, 2, 3]).parallel()
    assert stream._executor is FORK_JOIN


@pytest.mark.asyncio
async def test_sequential_after_parallel_wins() -> None:
    lst = await Stream.of([1, 2, 3]).parallel().sequential().collect(to_list())
    assert lst == [1, 2, 3]
    assert Stream.of([1, 2, 3]).parallel().sequential()._executor is SEQUENTIAL


@pytest.mark.asyncio
async def test_parallel_after_sequential_wins() -> None:
    assert Stream.of([1, 2, 3]).sequential().parallel()._executor is FORK_JOIN


# --- source acceptance under fork/join: a bare AsyncIterable whose __aiter__ -
# --- returns a fresh iterator each call, not self ---------------------------


class _SeparateIterAsyncIterable:
    """__aiter__ handing back a fresh iterator rather than self - stream-
    execution-model's source-acceptance requirement covers this shape
    explicitly. anext() requires an iterator, not merely an iterable, so
    the executor must call aiter(source) itself before pulling; passing the
    raw iterable straight to anext() (as batch()/_pull_round() briefly did)
    raises TypeError the moment a non-empty chain actually reaches it."""

    def __init__(self, n: int) -> None:
        self._n = n

    def __aiter__(self):
        async def gen():
            for i in range(self._n):
                yield i

        return gen()


@pytest.mark.asyncio
async def test_parallel_over_a_source_whose_aiter_returns_a_separate_iterator() -> None:
    lst = await Stream(_SeparateIterAsyncIterable(5)).parallel().map(lambda x: x).collect(to_list())

    assert sorted(lst) == [0, 1, 2, 3, 4]
    assert len(lst) == 5


# --- 2.7 the shared-source pull happens only on the main loop --------------


@pytest.mark.asyncio
async def test_only_the_main_thread_ever_pulls_from_the_shared_source() -> None:
    pull_threads: set[threading.Thread] = set()
    map_threads: set[threading.Thread] = set()

    async def source():
        for i in range(200):
            pull_threads.add(threading.current_thread())
            yield i

    def track_worker(x: int) -> int:
        map_threads.add(threading.current_thread())
        return x

    lst = await Stream.of(source()).parallel().map(track_worker).collect(to_list())

    assert sorted(lst) == list(range(200))
    # exactly one thread ever pulled from the source - the pull happens
    # sequentially inside _pull_round() on the main coroutine, never inside
    # a worker's asyncio.to_thread() - and it's not one of the worker threads
    assert pull_threads == {threading.current_thread()}
    assert len(map_threads) > 1
    assert threading.current_thread() not in map_threads


@pytest.mark.asyncio
async def test_parallel_over_a_slow_async_source_completes() -> None:
    # a source with a real await suspension point: nothing should deadlock
    # now that the shared-source pull is sequential on the main coroutine
    # rather than lock-guarded across concurrent branches
    async def slow_source():
        for i in range(10):
            await asyncio.sleep(0.001)
            yield i

    lst = await Stream.of(slow_source()).parallel().map(lambda x: x * 2).collect(to_list())

    assert lst == [x * 2 for x in range(10)]


# --- fork/join parallelises CPU-bound-shaped work (sanity, not a benchmark) -


@pytest.mark.asyncio
async def test_parallel_map_runs_concurrently_not_serially() -> None:
    # time.sleep() blocks (no await point), so gather() only overlaps it
    # across *threads*, not within one - enough elements are needed to span
    # every worker's own batch in round 1, or everything lands on one
    # thread and runs sequentially there regardless of gather()
    per_worker = min(_FIRST_BATCH_SIZE, BATCH_SIZE)
    source = list(range(FORK_JOIN.workers * per_worker))

    def slow(x: int) -> int:
        time.sleep(0.02)
        return x

    start = time.perf_counter()
    lst = await Stream.of(source).parallel().map(slow).collect(to_list())
    elapsed = time.perf_counter() - start

    assert lst == source
    # serial would be len(source) * 20ms; spread evenly across workers and
    # run concurrently (time.sleep() releases the GIL), one worker's own
    # per_worker * 20ms is the expected floor - generously bounded well
    # under the serial total to absorb scheduling jitter
    assert elapsed < (len(source) * 0.02) * 0.6

import time
import pytest
import asyncio

from snakestream import Stream
from snakestream.collectors import to_list


@pytest.mark.asyncio
async def test_parallel_simple(int_2_letter) -> None:
    # when
    it = await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]).parallel().map(lambda x: int_2_letter[x]).distinct().collect(to_list())
    # then
    assert len(it) == 4
    assert "a" in it
    assert "b" in it
    assert "c" in it
    assert "d" in it


@pytest.mark.asyncio
async def test_parallel_is_faster_than_sequential() -> None:

    async def sleep(n):
        await asyncio.sleep(0.1)

    # when
    start_parallel = time.time()
    await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]).parallel().map(sleep).distinct().collect(to_list())
    end_parallel = time.time()
    time_parallel = end_parallel - start_parallel

    start_sequential = time.time()
    await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]).map(sleep).distinct().collect(to_list())
    end_sequential = time.time()
    time_sequential = end_sequential - start_sequential

    # then
    # usually something like 0,2 compared to 0.8
    assert (time_parallel) < (time_sequential)


@pytest.mark.asyncio
async def test_parallel_distinct_no_cross_branch_duplicates() -> None:
    # given: a source large enough that a repeated value is likely to land
    # in more than one of the racing branches
    values = [1, 2, 3, 4] * 20

    # when
    it = await Stream.of(values).parallel().distinct().collect(to_list())

    # then
    assert sorted(it) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_parallel_limit_does_not_exceed_n_across_branches() -> None:
    # when
    it = await Stream.iterate(0, lambda n: n + 1).parallel().limit(10).collect(to_list())

    # then
    assert len(it) <= 10


@pytest.mark.asyncio
async def test_parallel_skip_drops_exactly_n_across_branches() -> None:
    # when
    it = await Stream.of(list(range(100))).parallel().skip(10).collect(to_list())

    # then
    assert len(it) == 90


@pytest.mark.asyncio
async def test_parallel_skip_state_fresh_across_separate_streams() -> None:
    # given: a first parallel skip() stream drains its own shared counter
    await Stream.of(list(range(20))).parallel().skip(10).collect(to_list())

    # when: a second, independently-built skip() stream should still drop
    # its own n elements, unaffected by the first stream's counter
    second = await Stream.of(list(range(20))).parallel().skip(10).collect(to_list())

    # then
    assert len(second) == 10


@pytest.mark.asyncio
async def test_parallel_distinct_state_fresh_across_separate_streams() -> None:
    # given: a first parallel distinct() stream consumes elements that would
    # collide with a second, independently-built stream if state leaked
    await Stream.of([1, 2, 3] * 10).parallel().distinct().collect(to_list())

    # when
    second = await Stream.of([1, 2, 3] * 10).parallel().distinct().collect(to_list())

    # then
    assert sorted(second) == [1, 2, 3]


async def _agen_with_real_await(n: int):
    for i in range(n):
        await asyncio.sleep(0)
        yield i


@pytest.mark.asyncio
async def test_parallel_over_source_with_real_await_empty_chain() -> None:
    # when: no intermediate ops, so branches would race __anext__() directly
    # on the shared source if it weren't guarded
    it = await Stream.of(_agen_with_real_await(20)).parallel().collect(to_list())

    # then
    assert sorted(it) == list(range(20))


@pytest.mark.asyncio
async def test_parallel_over_source_with_real_await_nonempty_chain() -> None:
    # when: a chain of intermediate ops is present, but every branch's
    # innermost pull still hits the same shared source
    it = await Stream.of(_agen_with_real_await(20)).parallel().map(lambda x: x * 2).collect(to_list())

    # then
    assert sorted(it) == [x * 2 for x in range(20)]


@pytest.mark.asyncio
async def test_parallel_limit_with_real_await_source_closes_safely() -> None:
    # when: a branch reaches max_size and closes the shared source while
    # other branches may still be mid-pull against it
    it = await Stream.of(_agen_with_real_await(50)).parallel().limit(10).collect(to_list())

    # then: no unhandled exception, and at most n elements total
    assert len(it) <= 10


@pytest.mark.asyncio
async def test_parallel_downstream_processing_stays_concurrent_with_real_await_source() -> None:
    async def slow_map(x):
        await asyncio.sleep(0.05)
        return x

    # when
    start = time.time()
    it = await Stream.of(_agen_with_real_await(8)).parallel().map(slow_map).collect(to_list())
    elapsed = time.time() - start

    # then: mapper invocations overlap across branches even though pulls
    # from the shared source are serialized, so this is well under the
    # ~0.4s a fully sequential run of 8 * 0.05s sleeps would take
    assert sorted(it) == list(range(8))
    assert elapsed < 0.35


@pytest.mark.asyncio
async def test_parallel_applies_to_ops_declared_before_it(int_2_letter) -> None:
    # given: a mapper slow enough that racing is visible in wall clock. The
    # .map() is declared BEFORE .parallel(), which used to freeze it under the
    # sequential mode in force at that point.
    async def slow(x):
        await asyncio.sleep(0.1)
        return x

    # when
    started = time.time()
    it = await Stream.of(list(range(8))).map(slow).parallel().collect(to_list())
    elapsed = time.time() - started

    # then: the executor in force at the terminal governs the whole pipeline,
    # so the map raced across all four branches (8/4 * 0.1) rather than running
    # sequentially (8 * 0.1). Matches Java, where parallel() sets a flag on the
    # source stage and is not positional.
    assert sorted(it) == list(range(8))
    assert elapsed < 0.35


@pytest.mark.asyncio
async def test_parallel_declared_late_still_produces_every_element(int_2_letter) -> None:
    # when: a stateful op declared before the switch now runs under the race,
    # so distinct() has to stay globally correct across branches
    it = await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]).map(lambda x: int_2_letter[x]).distinct().parallel().collect(to_list())
    # then
    assert len(it) == 4
    assert "a" in it
    assert "b" in it
    assert "c" in it
    assert "d" in it

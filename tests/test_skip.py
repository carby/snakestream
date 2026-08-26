import asyncio
import pytest
from snakestream.collectors import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_skip_drops_first_n_of_longer_source() -> None:
    # when
    lst = await Stream.of([0, 1, 2, 3, 4]).skip(2).collect(to_list())

    # then
    assert lst == [2, 3, 4]


@pytest.mark.asyncio
async def test_skip_shorter_than_n_source_yields_nothing() -> None:
    # when
    lst = await Stream.of([0, 1]).skip(5).collect(to_list())

    # then
    assert lst == []


@pytest.mark.asyncio
async def test_skip_zero_is_noop() -> None:
    # when
    lst = await Stream.of([0, 1, 2]).skip(0).collect(to_list())

    # then
    assert lst == [0, 1, 2]


@pytest.mark.asyncio
async def test_skip_exact_size_source_yields_nothing() -> None:
    # when
    lst = await Stream.of([0, 1, 2]).skip(3).collect(to_list())

    # then
    assert lst == []


@pytest.mark.asyncio
async def test_skip_async_source() -> None:
    async def gen():
        for i in range(5):
            yield i

    # when
    lst = await Stream.of(gen()).skip(2).collect(to_list())

    # then
    assert lst == [2, 3, 4]


@pytest.mark.asyncio
async def test_skip_state_not_shared_across_separate_streams() -> None:
    # given: a first stream drains its own skip() counter
    await Stream.of([0, 1, 2]).skip(2).collect(to_list())

    # when: a second, independently-built skip() stream should still drop
    # its own n elements, unaffected by the first stream's counter
    second = await Stream.of([0, 1, 2, 3, 4]).skip(2).collect(to_list())

    # then
    assert second == [2, 3, 4]


@pytest.mark.asyncio
async def test_skip_state_fresh_on_second_composition() -> None:
    # given
    stream = Stream.of([0, 1, 2, 3, 4]).skip(2)
    first = await stream.collect(to_list())

    # when
    second = await stream.collect(to_list())

    # then
    assert first == [2, 3, 4]
    # source is exhausted after the first run, but a second composition must
    # not raise or silently reuse the first run's skipped counter
    assert second == []


# --- under the racing executor ----------------------------------------------
#
# The roadmap's reproduction: a source of twelve whose first five elements are
# the expensive ones, so arrival order and encounter order disagree. The
# mechanism that keeps them apart is in tests/test_racing_encounter_order.py;
# these two are here so the op's own file says what the op selects.


async def _slow_head(n: int) -> int:
    await asyncio.sleep(0.05 if n < 5 else 0.001)
    return n


@pytest.mark.asyncio
async def test_parallel_skip_drops_the_first_n_in_encounter_order() -> None:
    # when
    lst = await Stream.of(list(range(12))).parallel().map(_slow_head).skip(5).collect(to_list())
    # then 0..4 are the ones dropped, as they are sequentially
    assert lst == [5, 6, 7, 8, 9, 10, 11]


@pytest.mark.asyncio
async def test_parallel_unordered_skip_drops_the_first_n_to_arrive() -> None:
    # when
    lst = await Stream.of(list(range(12))).parallel().unordered().map(_slow_head).skip(5).collect(to_list())
    # then exactly five dropped, but not 0..4
    assert len(lst) == 7
    assert sorted(lst) != [5, 6, 7, 8, 9, 10, 11]

import asyncio
import pytest
from snakestream.collectors import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_limit_does_not_pull_past_nth_element() -> None:
    # given
    seen: list[int] = []

    # when
    lst = await Stream.iterate(0, lambda n: n + 1).peek(seen.append).limit(3).collect(to_list())

    # then
    assert lst == [0, 1, 2]
    assert seen == [0, 1, 2]


@pytest.mark.asyncio
async def test_limit_exact_size_source() -> None:
    # when
    lst = await Stream.of([0, 1, 2]).limit(3).collect(to_list())

    # then
    assert lst == [0, 1, 2]


@pytest.mark.asyncio
async def test_limit_shorter_than_n_source() -> None:
    # when
    lst = await Stream.of([0, 1]).limit(5).collect(to_list())

    # then
    assert lst == [0, 1]


@pytest.mark.asyncio
async def test_limit_simple() -> None:
    # when
    lst = await Stream.iterate(0, lambda n: n + 1).limit(10).collect(to_list())

    # then
    assert len(lst) == 10


@pytest.mark.asyncio
async def test_limit_zero() -> None:
    # when
    lst = await Stream.iterate(0, lambda n: n + 1).limit(0).collect(to_list())

    # then
    assert len(lst) == 0


@pytest.mark.asyncio
async def test_limit_parallel() -> None:
    # when
    lst = await Stream.iterate(0, lambda n: n + 1).parallel().limit(10).collect(to_list())

    # then
    assert len(lst) == 10


@pytest.mark.asyncio
async def test_limit_parallel_shared_close_across_branches() -> None:
    # given: a large finite source, so multiple racing branches are likely to
    # observe the shared count reaching max_size and close the shared source
    # out from under each other

    # when
    lst = await Stream.of(list(range(1000))).parallel().limit(10).collect(to_list())

    # then: no exception escapes collect(), and the total across all branches
    # is exactly max_size
    assert len(lst) == 10


@pytest.mark.asyncio
async def test_limit_multiple() -> None:
    # when
    lst = await Stream.of([[0, 1, 2], [3, 4], [5, 6, 7], [8, 9]]).limit(3).flat_map(Stream.of).limit(6).collect(to_list())

    # then
    assert lst == [0, 1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_limit_state_not_shared_across_separate_streams() -> None:
    # given: a first stream exhausts its own limit() counter
    await Stream.iterate(0, lambda n: n + 1).limit(5).collect(to_list())

    # when: a second, independently-built limit() stream should still allow
    # up to its own max_size, unaffected by the first stream's counter
    second = await Stream.iterate(0, lambda n: n + 1).limit(5).collect(to_list())

    # then
    assert len(second) == 5


@pytest.mark.asyncio
async def test_limit_state_fresh_on_second_composition() -> None:
    # given
    stream = Stream.iterate(0, lambda n: n + 1).limit(5)
    first = await stream.collect(to_list())

    # when
    second = await stream.collect(to_list())

    # then
    assert len(first) == 5
    # source is exhausted after the first run, but a second composition must
    # not raise or silently reuse the first run's size counter
    assert second == []


@pytest.mark.asyncio
async def test_limit_zero_does_not_run_upstream_ops() -> None:
    # given: limit(0) is cancelled from the moment it begins, so nothing
    # upstream of it should ever see an element
    seen: list[int] = []

    # when
    lst = await Stream.of([1, 2, 3]).peek(seen.append).limit(0).collect(to_list())

    # then
    assert lst == []
    assert seen == []


@pytest.mark.asyncio
async def test_limit_zero_does_not_pull_from_source() -> None:
    # given: a source that records every pull before yielding
    pulled: list[int] = []

    def source():
        for i in [1, 2, 3]:
            pulled.append(i)
            yield i

    # when
    lst = await Stream.of(source()).limit(0).collect(to_list())

    # then
    assert lst == []
    assert pulled == []


@pytest.mark.asyncio
async def test_limit_zero_on_parallel_stream_yields_nothing() -> None:
    # given
    seen: list[int] = []

    # when
    lst = await Stream.of([1, 2, 3, 4]).parallel().peek(seen.append).limit(0).collect(to_list())

    # then
    assert lst == []
    assert seen == []


@pytest.mark.asyncio
async def test_limit_zero_still_runs_the_full_sink_lifecycle() -> None:
    # given a chain that pulled nothing must still have been begun and ended:
    # sorted() flushes from end(), so an unended chain would silently swallow
    # a downstream terminal's result rather than returning an empty one
    lst = await Stream.of([3, 1, 2]).sorted().limit(0).collect(to_list())

    # then
    assert lst == []


@pytest.mark.asyncio
async def test_limit_zero_terminal_still_returns_its_empty_result() -> None:
    # when: a terminal driven over a chain that pulls nothing
    total = await Stream.of([1, 2, 3]).limit(0).count()
    found = await Stream.of([1, 2, 3]).limit(0).find_first()

    # then
    assert total == 0
    assert found is None


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
async def test_parallel_limit_selects_the_first_n_in_encounter_order() -> None:
    # when
    lst = await Stream.of(list(range(12))).parallel().map(_slow_head).limit(5).collect(to_list())
    # then the same five the sequential pipeline picks, not the five that
    # finished first
    assert lst == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_parallel_unordered_limit_selects_the_first_n_to_arrive() -> None:
    # when the caller has said any n will do
    lst = await Stream.of(list(range(12))).parallel().unordered().map(_slow_head).limit(5).collect(to_list())
    # then still exactly five, chosen by the race
    assert len(lst) == 5
    assert lst != [0, 1, 2, 3, 4]

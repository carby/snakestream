import pytest
from snakestream.collector import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_limit_does_not_pull_past_nth_element() -> None:
    # given
    seen: list[int] = []

    # when
    lst = await Stream.iterate(0, lambda n: n + 1).peek(seen.append).limit(3).collect(to_list)

    # then
    assert lst == [0, 1, 2]
    assert seen == [0, 1, 2]


@pytest.mark.asyncio
async def test_limit_exact_size_source() -> None:
    # when
    lst = await Stream.of([0, 1, 2]).limit(3).collect(to_list)

    # then
    assert lst == [0, 1, 2]


@pytest.mark.asyncio
async def test_limit_shorter_than_n_source() -> None:
    # when
    lst = await Stream.of([0, 1]).limit(5).collect(to_list)

    # then
    assert lst == [0, 1]


@pytest.mark.asyncio
async def test_limit_simple() -> None:
    # when
    lst = await Stream.iterate(0, lambda n: n + 1).limit(10).collect(to_list)

    # then
    assert len(lst) == 10


@pytest.mark.asyncio
async def test_limit_zero() -> None:
    # when
    lst = await Stream.iterate(0, lambda n: n + 1).limit(0).collect(to_list)

    # then
    assert len(lst) == 0


@pytest.mark.asyncio
async def test_limit_parallel() -> None:
    # when
    lst = await Stream.iterate(0, lambda n: n + 1).parallel().limit(10).collect(to_list)

    # then
    assert len(lst) == 10


@pytest.mark.asyncio
async def test_limit_parallel_shared_close_across_branches() -> None:
    # given: a large finite source, so multiple racing branches are likely to
    # observe the shared count reaching max_size and close the shared source
    # out from under each other

    # when
    lst = await Stream.of(list(range(1000))).parallel().limit(10).collect(to_list)

    # then: no exception escapes collect(), and the total across all branches
    # is exactly max_size
    assert len(lst) == 10


@pytest.mark.asyncio
async def test_limit_multiple() -> None:
    # when
    lst = (
        await Stream.of([[0, 1, 2], [3, 4], [5, 6, 7], [8, 9]])
        .limit(3)
        .flat_map(lambda x: Stream.of(x))
        .limit(6)
        .collect(to_list)
    )

    # then
    assert lst == [0, 1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_limit_state_not_shared_across_separate_streams() -> None:
    # given: a first stream exhausts its own limit() counter
    await Stream.iterate(0, lambda n: n + 1).limit(5).collect(to_list)

    # when: a second, independently-built limit() stream should still allow
    # up to its own max_size, unaffected by the first stream's counter
    second = await Stream.iterate(0, lambda n: n + 1).limit(5).collect(to_list)

    # then
    assert len(second) == 5


@pytest.mark.asyncio
async def test_limit_state_fresh_on_second_composition() -> None:
    # given
    stream = Stream.iterate(0, lambda n: n + 1).limit(5)
    first = await stream.collect(to_list)

    # when
    second = await stream.collect(to_list)

    # then
    assert len(first) == 5
    # source is exhausted after the first run, but a second composition must
    # not raise or silently reuse the first run's size counter
    assert second == []

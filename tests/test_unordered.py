import pytest

from snakestream.collector import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_is_ordered_default_sequential() -> None:
    # when
    res = Stream.of([1, 2, 3]).is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_is_ordered_default_parallel() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_unordered_sets_is_ordered_false() -> None:
    # when
    res = Stream.of([1, 2, 3]).unordered().is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_unordered_returns_self_for_chaining() -> None:
    # given
    stream = Stream.of([1, 2, 3])

    # when
    res = stream.unordered()

    # then
    assert res is stream


@pytest.mark.asyncio
async def test_unordered_chains_with_other_intermediate_ops() -> None:
    # when
    res = await Stream.of([1, 2, 3, 4]).unordered().filter(lambda x: x % 2 == 0).collect(to_list())
    # then
    assert sorted(res) == [2, 4]


@pytest.mark.asyncio
async def test_unordered_does_not_affect_other_instances() -> None:
    # given
    a = Stream.of([1, 2, 3])
    b = Stream.of([1, 2, 3])

    # when
    a.unordered()

    # then
    assert a.is_ordered() is False
    assert b.is_ordered() is True


@pytest.mark.asyncio
async def test_unordered_survives_parallel_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).unordered().parallel().is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_unordered_survives_sequential_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().unordered().sequential().is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_ordered_stays_true_across_parallel_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_ordered_stays_true_across_sequential_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().sequential().is_ordered()
    # then
    assert res is True

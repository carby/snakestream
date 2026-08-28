import functools

import pytest
import asyncio
from hypothesis import given
from hypothesis import strategies as st

from snakestream import Stream
from snakestream.collectors import to_list
from snakestream.comparator import comparing


@pytest.mark.asyncio
async def test_sorted() -> None:
    outset = [1, 5, 3, 4, 5, 2]

    actual = await Stream.of(outset).sorted().collect(to_list())

    assert sorted(outset) == actual


@pytest.mark.asyncio
async def test_sorted_reverse() -> None:
    outset = [1, 5, 3, 4, 5, 2]

    actual = await Stream.of(outset).sorted(reverse=True).collect(to_list())

    assert sorted(outset, reverse=True) == actual


@pytest.mark.asyncio
async def test_sorted_comparator() -> None:
    outset = [
        {"x": 1, "y": 5},
        {"x": 3, "y": 7},
        {"x": 2, "y": 6},
    ]

    def compare(a, b):
        if a["x"] > b["x"]:
            return 1
        if a["x"] < b["x"]:
            return -1
        return 0

    actual = await Stream.of(outset).sorted(comparator=compare).collect(to_list())

    assert sorted(outset, key=lambda x: x["x"]) == actual


@pytest.mark.asyncio
async def test_sorted_async_comparator_and_reverse() -> None:
    outset = [
        {"x": 1, "y": 5},
        {"x": 3, "y": 7},
        {"x": 2, "y": 6},
    ]

    async def compare_async(a, b):
        await asyncio.sleep(0.01)
        if a["x"] == b["x"]:
            return 0
        if a["x"] > b["x"]:
            return 1
        return -1

    actual = await Stream.of(outset).sorted(comparator=compare_async, reverse=True).collect(to_list())

    assert actual == [
        {"x": 3, "y": 7},
        {"x": 2, "y": 6},
        {"x": 1, "y": 5},
    ]


@given(values=st.lists(st.integers()))
@pytest.mark.asyncio
async def test_sorted_matches_builtin_sorted(values: list[int]) -> None:
    # when
    actual = await Stream.of(values).sorted().collect(to_list())

    # then
    assert actual == sorted(values)


def _compare_by_abs(a: int, b: int) -> int:
    return (abs(a) > abs(b)) - (abs(a) < abs(b))


@given(values=st.lists(st.integers()))
@pytest.mark.asyncio
async def test_sorted_comparator_matches_cmp_to_key(values: list[int]) -> None:
    # when
    actual = await Stream.of(values).sorted(comparator=_compare_by_abs).collect(to_list())

    # then
    assert actual == sorted(values, key=functools.cmp_to_key(_compare_by_abs))


@given(values=st.lists(st.integers()))
@pytest.mark.asyncio
async def test_sorted_async_comparator_matches_cmp_to_key(values: list[int]) -> None:
    async def async_compare_by_abs(a: int, b: int) -> int:
        return _compare_by_abs(a, b)

    # when
    actual = await Stream.of(values).sorted(comparator=async_compare_by_abs).collect(to_list())

    # then
    assert actual == sorted(values, key=functools.cmp_to_key(_compare_by_abs))


@pytest.mark.asyncio
async def test_sorted_rejects_bool_comparator() -> None:
    outset = [3, 1, 2]
    # when / then
    with pytest.raises(TypeError):
        await Stream.of(outset).sorted(comparator=lambda a, b: a > b).collect(to_list())


@pytest.mark.asyncio
async def test_sorted_rejects_async_bool_comparator() -> None:
    async def async_compare(a: int, b: int) -> bool:
        await asyncio.sleep(0.01)
        return a > b

    outset = [3, 1, 2]
    # when / then
    with pytest.raises(TypeError):
        await Stream.of(outset).sorted(comparator=async_compare).collect(to_list())


@pytest.mark.asyncio
async def test_sorted_rejects_non_int_on_a_later_comparison() -> None:
    # the int contract holds for every comparison, not just the first: this
    # comparator returns int for (3, 1) and float once 2.5 is involved
    outset = [3, 1, 2.5]
    # when / then
    with pytest.raises(TypeError):
        await Stream.of(outset).sorted(comparator=lambda a, b: a - b).collect(to_list())


# --- under the racing executor ----------------------------------------------


def _asc(a: int, b: int) -> int:
    return a - b


@pytest.mark.asyncio
async def test_parallel_sorted_sorts_the_whole_stream_over_an_async_source() -> None:
    # given an async source, where every racing branch really does take a
    # share - a sort per branch's subset would merge to something unsorted
    async def descending():
        for i in range(12, 0, -1):
            await asyncio.sleep(0)
            yield i

    # when
    actual = await Stream.of(descending()).parallel().sorted(_asc).collect(to_list())

    # then
    assert actual == list(range(1, 13))


@pytest.mark.asyncio
async def test_parallel_sorted_sorts_the_whole_stream_over_a_sync_source() -> None:
    # given the same pipeline over a list, with a peek recording what the
    # branches' heads saw - so this passing is the ordering requirement being
    # honoured, not one branch happening to take every element
    seen: list[int] = []

    actual = await Stream.of(list(range(12, 0, -1))).parallel().peek(seen.append).sorted(_asc).collect(to_list())

    # then
    assert actual == list(range(1, 13))
    assert sorted(seen) == list(range(1, 13))


# --- stability ---------------------------------------------------------------
#
# comparator-contract requires sorted() to be stable: elements comparing equal
# keep the relative order they entered with. It is the same rule as min()/max()'s
# tie-break, read over a whole stream rather than one running result, which is
# why one capability states both.
#
# Every comparator form the capability accepts is covered, because they reach
# three different algorithms in sort.py: a sync comparator goes to Timsort via
# cmp_to_key, an async one to merge_sort's hand-written merge, and a comparing()
# key comparator to the decorate-sort-undecorate path.

_STABILITY_SOURCE = [("a", 5), ("b", 3), ("c", 5)]


def _by_second(x, y):
    return x[1] - y[1]


@pytest.mark.asyncio
async def test_sync_comparator_sort_is_stable() -> None:
    # when
    it = await Stream.of(_STABILITY_SOURCE).sorted(_by_second).collect(to_list())
    # then
    assert it == [("b", 3), ("a", 5), ("c", 5)]


@pytest.mark.asyncio
async def test_async_comparator_sort_is_stable() -> None:
    async def _async_by_second(x, y):
        await asyncio.sleep(0.001)
        return x[1] - y[1]

    # when
    it = await Stream.of(_STABILITY_SOURCE).sorted(_async_by_second).collect(to_list())
    # then
    assert it == [("b", 3), ("a", 5), ("c", 5)]


@pytest.mark.asyncio
async def test_key_comparator_sort_is_stable() -> None:
    # when
    it = await Stream.of(_STABILITY_SOURCE).sorted(comparing(lambda pair: pair[1])).collect(to_list())
    # then
    assert it == [("b", 3), ("a", 5), ("c", 5)]


@pytest.mark.asyncio
async def test_reversed_key_comparator_is_stable_rather_than_reversing_ties() -> None:
    # given: reversed() negates the ordering, which is not the same as
    # reversing the output - the tied pair keeps its encounter order
    ordering = comparing(lambda pair: pair[1]).reversed()

    # when
    it = await Stream.of(_STABILITY_SOURCE).sorted(ordering).collect(to_list())

    # then
    assert it == [("a", 5), ("c", 5), ("b", 3)]

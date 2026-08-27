import asyncio
import functools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from snakestream import Stream
from snakestream.collectors import max_by, min_by, to_list
from snakestream.comparator import comparing


@pytest.mark.asyncio
async def test_sorted_with_sync_key_extractor() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x["v"])).collect(to_list())

    assert actual == [{"v": 1}, {"v": 2}, {"v": 3}]


@pytest.mark.asyncio
async def test_sorted_with_async_key_extractor() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    async def key(x: dict) -> int:
        await asyncio.sleep(0.01)
        return x["v"]

    actual = await Stream.of(outset).sorted(comparing(key)).collect(to_list())

    assert actual == [{"v": 1}, {"v": 2}, {"v": 3}]


@pytest.mark.asyncio
async def test_min_accepts_comparing_sync() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    result = await Stream.of(outset).min(comparing(lambda x: x["v"]))

    assert result == {"v": 1}


@pytest.mark.asyncio
async def test_max_accepts_comparing_sync() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    result = await Stream.of(outset).max(comparing(lambda x: x["v"]))

    assert result == {"v": 3}


@pytest.mark.asyncio
async def test_min_accepts_comparing_async() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    async def key(x: dict) -> int:
        await asyncio.sleep(0.01)
        return x["v"]

    result = await Stream.of(outset).min(comparing(key))

    assert result == {"v": 1}


@pytest.mark.asyncio
async def test_max_accepts_comparing_async() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    async def key(x: dict) -> int:
        await asyncio.sleep(0.01)
        return x["v"]

    result = await Stream.of(outset).max(comparing(key))

    assert result == {"v": 3}


@pytest.mark.asyncio
async def test_min_by_accepts_comparing() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    result = await Stream.of(outset).collect(min_by(comparing(lambda x: x["v"])))

    assert result == {"v": 1}


@pytest.mark.asyncio
async def test_max_by_accepts_comparing() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    result = await Stream.of(outset).collect(max_by(comparing(lambda x: x["v"])))

    assert result == {"v": 3}


@pytest.mark.asyncio
async def test_min_by_accepts_comparing_async() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    async def key(x: dict) -> int:
        await asyncio.sleep(0.01)
        return x["v"]

    result = await Stream.of(outset).collect(min_by(comparing(key)))

    assert result == {"v": 1}


@pytest.mark.asyncio
async def test_max_by_accepts_comparing_async() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    async def key(x: dict) -> int:
        await asyncio.sleep(0.01)
        return x["v"]

    result = await Stream.of(outset).collect(max_by(comparing(key)))

    assert result == {"v": 3}


def test_comparing_result_is_callable_as_ordinary_comparator() -> None:
    cmp = comparing(lambda x: x["v"])

    assert cmp({"v": 1}, {"v": 2}) < 0
    assert cmp({"v": 2}, {"v": 1}) > 0
    assert cmp({"v": 1}, {"v": 1}) == 0
    assert isinstance(cmp({"v": 1}, {"v": 2}), int)


@pytest.mark.asyncio
async def test_comparing_async_result_is_callable_as_ordinary_comparator() -> None:
    async def key(x: dict) -> int:
        return x["v"]

    cmp = comparing(key)

    assert await cmp({"v": 1}, {"v": 2}) < 0
    assert await cmp({"v": 2}, {"v": 1}) > 0
    assert await cmp({"v": 1}, {"v": 1}) == 0


@given(values=st.lists(st.tuples(st.integers(), st.integers())))
@pytest.mark.asyncio
async def test_sorted_order_matches_call_path_order(values: list[tuple[int, int]]) -> None:
    # given a comparing() comparator built on a key extractor with duplicate
    # keys guaranteed (second element is fixed), so ties actually occur
    outset = [(v, 0) for v, _ in values]
    cmp = comparing(lambda x: x[0])

    # when: sort via the fast path, and independently via the __call__ path
    fast = await Stream.of(outset).sorted(cmp).collect(to_list())

    def sign(a: tuple, b: tuple) -> int:
        r = cmp(a, b)
        assert isinstance(r, int)
        return r

    slow = sorted(outset, key=functools.cmp_to_key(sign))

    # then
    assert fast == slow


@pytest.mark.asyncio
async def test_sorted_order_matches_call_path_order_on_bool_keys() -> None:
    outset = [1, 2, 3, 4, 5]
    cmp = comparing(lambda x: x % 2 == 0)

    fast = await Stream.of(outset).sorted(cmp).collect(to_list())

    def sign(a: int, b: int) -> int:
        r = cmp(a, b)
        assert isinstance(r, int)
        return r

    slow = sorted(outset, key=functools.cmp_to_key(sign))

    assert fast == slow


@pytest.mark.asyncio
async def test_key_extractor_invoked_exactly_once_per_element() -> None:
    calls: list[int] = []

    def key(x: int) -> int:
        calls.append(x)
        return x

    outset = [5, 3, 1, 4, 2]
    await Stream.of(outset).sorted(comparing(key)).collect(to_list())

    assert len(calls) == len(outset)


class _CoroutineReturningKey:
    """A key extractor with a plain `def __call__` that returns a coroutine -
    classifies as sync via is_async_callable, so the fast path's one-time
    isawaitable safety net is what actually catches it."""

    def __call__(self, x: int) -> object:
        async def _inner() -> int:
            return x

        return _inner()


@pytest.mark.asyncio
async def test_key_extractor_misclassified_sync_is_caught_by_safety_net() -> None:
    outset = [3, 1, 2]

    actual = await Stream.of(outset).sorted(comparing(_CoroutineReturningKey())).collect(to_list())

    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_key_extractor_invoked_exactly_once_per_element_async() -> None:
    calls: list[int] = []

    async def key(x: int) -> int:
        calls.append(x)
        return x

    outset = [5, 3, 1, 4, 2]
    await Stream.of(outset).sorted(comparing(key)).collect(to_list())

    assert len(calls) == len(outset)


@pytest.mark.asyncio
async def test_stability_equal_keys_keep_encounter_order() -> None:
    outset = [("a", 1), ("b", 1), ("c", 0)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[1])).collect(to_list())

    assert actual == [("c", 0), ("a", 1), ("b", 1)]


@pytest.mark.asyncio
async def test_incomparable_keys_raise_type_error() -> None:
    outset = [1, "a", 2]

    with pytest.raises(TypeError):
        await Stream.of(outset).sorted(comparing(lambda x: x)).collect(to_list())


@pytest.mark.asyncio
async def test_bool_valued_key_sorts_false_before_true() -> None:
    outset = [1, 2, 3, 4, 5]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x % 2 == 0)).collect(to_list())

    assert actual == [1, 3, 5, 2, 4]


class _NoLessThan:
    """An element with no __lt__ - only its key is comparable."""

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _NoLessThan) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"_NoLessThan({self.value})"


@pytest.mark.asyncio
async def test_elements_without_lt_sort_correctly_when_keys_do() -> None:
    outset = [_NoLessThan(3), _NoLessThan(1), _NoLessThan(2)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x.value)).collect(to_list())

    assert actual == [_NoLessThan(1), _NoLessThan(2), _NoLessThan(3)]


@pytest.mark.asyncio
async def test_sorted_reverse_with_comparing_reverses_the_buffer() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x["v"]), reverse=True).collect(to_list())

    assert actual == [{"v": 3}, {"v": 2}, {"v": 1}]


@pytest.mark.asyncio
async def test_sorted_reverse_with_comparing_reverses_equal_key_runs_too() -> None:
    outset = [("a", 1), ("b", 1), ("c", 0)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[1]), reverse=True).collect(to_list())

    # order-reversal of the ascending stable result, not comparator-negation
    assert actual == [("b", 1), ("a", 1), ("c", 0)]


@pytest.mark.asyncio
async def test_comparing_under_parallel_sorts_the_whole_stream() -> None:
    async def descending():
        for i in range(12, 0, -1):
            await asyncio.sleep(0)
            yield {"v": i}

    actual = await Stream.of(descending()).parallel().sorted(comparing(lambda x: x["v"])).collect(to_list())

    assert actual == [{"v": i} for i in range(1, 13)]


@pytest.mark.asyncio
async def test_comparing_after_unordered_still_restores_ordering() -> None:
    async def descending():
        for i in range(12, 0, -1):
            await asyncio.sleep(0)
            yield {"v": i}

    actual = await Stream.of(descending()).parallel().unordered().sorted(comparing(lambda x: x["v"])).collect(to_list())

    assert actual == [{"v": i} for i in range(1, 13)]


@pytest.mark.asyncio
async def test_sorted_by_comparing_empty_stream() -> None:
    actual = await Stream.of([]).sorted(comparing(lambda x: x)).collect(to_list())

    assert actual == []


@pytest.mark.asyncio
async def test_sorted_by_comparing_single_element_stream() -> None:
    actual = await Stream.of([{"v": 1}]).sorted(comparing(lambda x: x["v"])).collect(to_list())

    assert actual == [{"v": 1}]

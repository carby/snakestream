import pytest
import asyncio

from snakestream import Stream
from conftest import MyObject


@pytest.mark.asyncio
async def test_find_min_value_normal_input():
    input_list = [1, 2, 3, 4, 5]
    # when
    it = await Stream.of(input_list).min(lambda x, y: x - y)
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_min_value_async_input():
    async def async_comparator(x: int, y: int) -> int:
        await asyncio.sleep(0.01)
        return x - y

    input_list = [1, 2, 3, 4, 5]
    # when
    it = await Stream.of(input_list).min(async_comparator)
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_min_value_empty_input():
    input_list = []
    # when
    it = await Stream.of(input_list).min(lambda x, y: x - y)
    # then
    assert it is None


@pytest.mark.asyncio
async def test_find_min_value_list_with_dupe_items():
    input_list = [1, 1, 2, 3, 4, 5]
    # when
    it = await Stream.of(input_list).min(lambda x, y: x - y)
    # then
    assert it == 1

    input_list = [1, 2, 3, 4, 5, 5]
    # when
    it = await Stream.of(input_list).min(lambda x, y: x - y)
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_min_value_negative_values():
    input_list = [-1, -2, -3, -4, -5]
    # when
    it = await Stream.of(input_list).min(lambda x, y: x - y)
    # then
    assert it == -5


@pytest.mark.asyncio
async def test_find_min_value_custom_comparator():
    input_list = ["a", "bb", "ccc"]
    # when
    it = await Stream.of(input_list).min(lambda x, y: len(x) - len(y))
    # then
    assert it == "a"


@pytest.mark.asyncio
async def test_find_min_value_with_falsy_values():
    input_list = [5, 3, 0, 4]
    # when
    it = await Stream.of(input_list).min(lambda x, y: x - y)
    # then
    assert it == 0


@pytest.mark.asyncio
async def test_find_min_value_single_falsy_value():
    input_list = [0]
    # when
    it = await Stream.of(input_list).min(lambda x, y: x - y)
    # then
    assert it == 0


@pytest.mark.asyncio
async def test_find_min_value_object_comparator() -> None:
    # when
    input_list = [
        MyObject(1, "object1"),
        MyObject(2, "object2"),
        MyObject(3, "object3"),
        MyObject(2, "object2"),
        MyObject(3, "object3"),
    ]
    it = await Stream.of(input_list).min(lambda x, y: x.id - y.id)
    # then
    assert it == MyObject(1, "object1")


@pytest.mark.asyncio
async def test_find_min_value_three_way_comparator():
    input_list = [3, 1, 2]
    # when
    it = await Stream.of(input_list).min(lambda x, y: x - y)
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_min_value_three_way_comparator_async():
    async def async_comparator(x: int, y: int) -> int:
        await asyncio.sleep(0.01)
        return x - y

    input_list = [3, 1, 2]
    # when
    it = await Stream.of(input_list).min(async_comparator)
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_min_value_keeps_first_of_tied_elements():
    input_list = [("a", 5), ("b", 5)]
    # when
    it = await Stream.of(input_list).min(lambda x, y: x[1] - y[1])
    # then
    assert it == ("a", 5)


@pytest.mark.asyncio
async def test_find_min_value_rejects_bool_comparator():
    input_list = [3, 1, 2]
    # when / then
    with pytest.raises(TypeError):
        await Stream.of(input_list).min(lambda x, y: x > y)


@pytest.mark.asyncio
async def test_find_min_value_rejects_async_bool_comparator():
    async def async_comparator(x: int, y: int) -> bool:
        await asyncio.sleep(0.01)
        return x > y

    input_list = [3, 1, 2]
    # when / then
    with pytest.raises(TypeError):
        await Stream.of(input_list).min(async_comparator)

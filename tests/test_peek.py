import asyncio

import pytest

from conftest import MyObject
from snakestream import stream_of
from snakestream.collector import to_list

obj1 = MyObject(1, "Object1")
obj2 = MyObject(2, "Object2")
obj3 = MyObject(3, "Object3")


input_list = [
    obj1,
    obj2,
    obj3,
    obj2,
    obj3,
]


@pytest.mark.asyncio
async def test_ok() -> None:
    # when
    it = await stream_of(input_list) \
        .peek(lambda x: x) \
        .collect(to_list)
    # then
    assert it == input_list
    assert it[0] is input_list[0]
    assert it[1] is input_list[1]
    assert it[2] is input_list[2]
    assert it[3] is input_list[3]
    assert it[4] is input_list[4]


@pytest.mark.asyncio
async def test_ok_async_function() -> None:
    names = []

    async def some_func(x: MyObject) -> None:
        await asyncio.sleep(0.01)
        names.append(x.name)
        return

    # when
    it = await stream_of(input_list) \
        .peek(some_func) \
        .collect(to_list)
    # then
    assert it == input_list
    assert it[0] is input_list[0]
    assert it[1] is input_list[1]
    assert it[2] is input_list[2]
    assert it[3] is input_list[3]
    assert it[4] is input_list[4]

    assert names == ['Object1', 'Object2', 'Object3', 'Object2', 'Object3',]


@pytest.mark.asyncio
async def test_empty_stream() -> None:
    # when
    it = await stream_of([]) \
        .peek(lambda x: x) \
        .collect(to_list)
    # then
    assert it == []


@pytest.mark.asyncio
async def test_multiple_calls() -> None:
    # when
    it = await stream_of(input_list) \
        .peek(lambda x: x) \
        .peek(lambda x: x) \
        .collect(to_list)
    # then
    assert it == input_list
    assert it[0] is input_list[0]
    assert it[1] is input_list[1]
    assert it[2] is input_list[2]
    assert it[3] is input_list[3]
    assert it[4] is input_list[4]


@pytest.mark.asyncio
async def test_mutate_internal_state() -> None:
    def lower_name(x: MyObject) -> None:
        x.name = x.name.lower()

    # when
    it = await stream_of(input_list) \
        .peek(lower_name) \
        .collect(to_list)
    # then
    assert it == input_list
    assert it[0] is input_list[0]
    assert it[1] is input_list[1]
    assert it[2] is input_list[2]
    assert it[3] is input_list[3]
    assert it[4] is input_list[4]

    assert it[0].name == 'object1'
    assert it[1].name == 'object2'
    assert it[2].name == 'object3'
    assert it[3].name == 'object2'
    assert it[4].name == 'object3'

import pytest

from snakestream.collector import joining
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_joining_no_args_concatenates_with_no_delimiter() -> None:
    # when
    result = await Stream.of(["a", "b", "c"]).collect(joining())

    # then
    assert result == "abc"


@pytest.mark.asyncio
async def test_joining_delimiter_only() -> None:
    # when
    result = await Stream.of(["a", "b", "c"]).collect(joining(", "))

    # then
    assert result == "a, b, c"


@pytest.mark.asyncio
async def test_joining_delimiter_prefix_and_suffix() -> None:
    # when
    result = await Stream.of(["a", "b", "c"]).collect(joining(", ", "[", "]"))

    # then
    assert result == "[a, b, c]"


@pytest.mark.asyncio
async def test_joining_single_element_has_no_delimiter_applied() -> None:
    # when
    result = await Stream.of(["a"]).collect(joining(", "))

    # then
    assert result == "a"


@pytest.mark.asyncio
async def test_joining_empty_stream_returns_empty_string() -> None:
    # when
    result = await Stream.of([]).collect(joining(", "))

    # then
    assert result == ""


@pytest.mark.asyncio
async def test_joining_empty_stream_with_prefix_and_suffix() -> None:
    # when
    result = await Stream.of([]).collect(joining(", ", "[", "]"))

    # then
    assert result == "[]"


@pytest.mark.asyncio
async def test_joining_non_string_element_raises_type_error() -> None:
    # when / then
    with pytest.raises(TypeError):
        await Stream.of(["a", 1, "c"]).collect(joining())

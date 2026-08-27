import pytest
from snakestream.collectors import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_composition_does_not_shrink_chain() -> None:
    # given
    stream = Stream.of([1, 2, 3]).map(lambda x: x * 2).filter(lambda x: x > 0)
    chain_len_before = len(stream._chain)

    # when
    stream.iterator()

    # then
    assert len(stream._chain) == chain_len_before


@pytest.mark.asyncio
async def test_second_terminal_op_reuses_same_chain() -> None:
    # given
    stream = Stream.of([1, 2, 3]).map(lambda x: x * 2)
    chain_len_before = len(stream._chain)

    # when
    first = await stream.collect(to_list())
    chain_len_after_first = len(stream._chain)
    second = await stream.collect(to_list())

    # then
    assert first == [2, 4, 6]
    # the source is a one-shot generator, so the second collect() legitimately
    # sees nothing further to pull -- what matters is the chain itself wasn't
    # drained by the first composition, so a second run doesn't crash and would
    # apply the same operations if the source had more to give.
    assert second == []
    assert chain_len_after_first == chain_len_before
    assert len(stream._chain) == chain_len_before

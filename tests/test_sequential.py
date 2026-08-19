import sys

import pytest
from snakestream.collector import to_list
from snakestream.sink import Op
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_sequential_simple(int_2_letter) -> None:
    # when
    it = await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]).sequential().map(lambda x: int_2_letter[x]).distinct().collect(to_list)
    # then
    assert 4 == len(it)
    assert "a" in it
    assert "b" in it
    assert "c" in it
    assert "d" in it


def test_sequential_long_chain_does_not_recurse_at_build_time() -> None:
    # given a chain of ops deep enough to blow the default recursion limit if
    # _sequential() still recursed once per queued op to build the linked
    # sink chain (identity ops isolate the build-time traversal from any
    # per-op accept() delegation at consumption time, which is a separate,
    # larger concern tracked outside this change)
    n = sys.getrecursionlimit() * 2

    class _IdentityOp(Op):
        def link(self, downstream):
            return downstream

    intermediaries = [_IdentityOp()] * n
    sentinel = object()
    # when
    result = Stream.of([])._sequential(intermediaries, sentinel)
    # then
    assert result is sentinel


@pytest.mark.asyncio
async def test_sequential_switch_to_parallel(int_2_letter) -> None:
    # when
    it = (
        await Stream.of([1, 2, 3, 4, 1, 2, 3, 4])
        .parallel()
        .map(lambda x: int_2_letter[x])
        .sequential()
        .distinct()
        .collect(to_list)
    )
    # then
    assert 4 == len(it)
    assert "a" in it
    assert "b" in it
    assert "c" in it
    assert "d" in it

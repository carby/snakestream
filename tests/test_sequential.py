import sys

import asyncio
import time

import pytest
from snakestream.base_stream import _wrap_sink
from snakestream.collector import to_list
from snakestream.sink import Op
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_sequential_simple(int_2_letter) -> None:
    # when
    it = await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]).sequential().map(lambda x: int_2_letter[x]).distinct().collect(to_list())
    # then
    assert 4 == len(it)
    assert "a" in it
    assert "b" in it
    assert "c" in it
    assert "d" in it


def test_sequential_long_chain_does_not_recurse_at_build_time() -> None:
    # given a chain of ops deep enough to blow the default recursion limit if
    # _wrap_sink() still recursed once per queued op to build the linked
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
    result = _wrap_sink(intermediaries, sentinel)
    # then
    assert result is sentinel


@pytest.mark.asyncio
async def test_sequential_applies_to_ops_declared_before_it(int_2_letter) -> None:
    # given: the same slow mapper, this time with .parallel() declared BEFORE
    # it and .sequential() after
    async def slow(x):
        await asyncio.sleep(0.1)
        return x

    # when
    started = time.time()
    it = await Stream.of(list(range(8))).parallel().map(slow).sequential().collect(to_list())
    elapsed = time.time() - started

    # then: the last switch wins for the whole pipeline, so the map ran
    # sequentially (8 * 0.1) despite the earlier .parallel(). There is no such
    # thing as a mid-chain mode switch — the executor in force at the terminal
    # governs every queued op.
    assert sorted(it) == list(range(8))
    assert elapsed > 0.7


@pytest.mark.asyncio
async def test_sequential_declared_late_still_produces_every_element(int_2_letter) -> None:
    # when
    it = (
        await Stream.of([1, 2, 3, 4, 1, 2, 3, 4])
        .parallel()
        .map(lambda x: int_2_letter[x])
        .sequential()
        .distinct()
        .collect(to_list())
    )
    # then
    assert 4 == len(it)
    assert "a" in it
    assert "b" in it
    assert "c" in it
    assert "d" in it

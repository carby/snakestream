"""Targeted verification for the partition protocol (make-combiners-live,
tasks 2.1-3.4): the fork-join executor's partitioned value() path, the live
collect(supplier, accumulator, combiner) combiner, and the new three-argument
reduce(). Section 4's per-collector combiner tests live in each collector's
own test file (task 4.6); this file covers the mechanism itself."""

import asyncio

import pytest

from snakestream import Stream
from snakestream.collectors import to_list


# A source spanning several fork-join batches: _FIRST_BATCH_SIZE=4 per worker
# with 4 workers pulls 16 in round one, so 50 elements guarantees a second
# round and several partitions to merge - the trap task 4.6 and design.md's
# Risks both call out, where a source small enough to be one partition would
# pass without ever merging.
_N = 50


# --- 2.1 the non-partitioning path is unchanged -----------------------------


@pytest.mark.asyncio
async def test_a_collector_with_no_combiner_is_not_partitioned() -> None:
    # to_list()'s Collector carries no combiner; the parallel result must
    # still equal the sequential one via the untouched single-container path.
    source = list(range(_N))
    seq = await Stream.of(source).sequential().collect(to_list())
    par = await Stream.of(source).parallel().collect(to_list())

    assert par == seq == source


# --- 2.2 merge order follows batch (encounter) order, not completion order -


def _concat_parts(a: list[str], b: list[str]) -> list[str]:
    a.extend(b)
    return a


@pytest.mark.asyncio
async def test_merge_follows_encounter_order_not_a_permutation() -> None:
    letters = [chr(ord("a") + i % 26) for i in range(_N)]

    seq = "".join(await Stream.of(letters).sequential().collect(list, list.append, _concat_parts))
    par = "".join(await Stream.of(letters).parallel().collect(list, list.append, _concat_parts))

    assert par == seq == "".join(letters)


# --- 2.3 unordered() does not license merging out of order ------------------


@pytest.mark.asyncio
async def test_unordered_does_not_change_merge_order() -> None:
    letters = [chr(ord("a") + i % 26) for i in range(_N)]

    seq = "".join(await Stream.of(letters).sequential().collect(list, list.append, _concat_parts))
    par = "".join(await Stream.of(letters).parallel().unordered().collect(list, list.append, _concat_parts))

    assert par == seq == "".join(letters)


# --- 2.4 sequential never invokes a supplied combiner, and produces one ----
# --- partition ----------------------------------------------------------


@pytest.mark.asyncio
async def test_sequential_never_invokes_the_combiner() -> None:
    calls = 0

    def combiner(a: list, b: list) -> list:
        nonlocal calls
        calls += 1
        return a + b

    result = await Stream.of(list(range(_N))).sequential().collect(list, list.append, combiner)

    assert result == list(range(_N))
    assert calls == 0


# --- 2.5 an element lands in exactly one partition --------------------------


@pytest.mark.asyncio
async def test_every_element_lands_in_exactly_one_partition_through_filter_and_flat_map() -> None:
    source = list(range(_N))
    expected = sorted(y for x in source if x % 2 == 0 for y in (x, x + 1000))

    result = await (
        Stream.of(source)
        .parallel()
        .filter(lambda x: x % 2 == 0)
        .flat_map(lambda x: Stream.of([x, x + 1000]))
        .collect(to_list())
    )

    assert sorted(result) == expected
    assert len(result) == len(expected)


# --- 3.1 collect(supplier, accumulator, combiner)'s combiner is live -------


@pytest.mark.asyncio
async def test_hand_rolled_collect_combiner_is_invoked_and_matches_sequential() -> None:
    merges = 0

    async def supplier() -> dict:
        return {}

    def accumulate(acc: dict, element: int) -> None:
        acc[element] = acc.get(element, 0) + 1

    def combiner(a: dict, b: dict) -> dict:
        nonlocal merges
        merges += 1
        for k, v in b.items():
            a[k] = a.get(k, 0) + v
        return a

    source = [i % 7 for i in range(_N)]
    seq = await Stream.of(source).sequential().collect(dict, accumulate, combiner)
    merges_after_seq = merges
    par = await Stream.of(source).parallel().collect(supplier, accumulate, combiner)

    assert par == seq
    assert merges_after_seq == 0
    assert merges > 0


# --- 3.2 / 3.3 the third reduce() overload --------------------------------


@pytest.mark.asyncio
async def test_reduce_one_arg_still_dispatches() -> None:
    result = await Stream.of([1, 2, 3, 4]).reduce(lambda a, b: a + b)
    assert result == 10


@pytest.mark.asyncio
async def test_reduce_two_arg_still_dispatches() -> None:
    result = await Stream.of([1, 2, 3, 4]).reduce(10, lambda a, b: a + b)
    assert result == 20


@pytest.mark.asyncio
async def test_reduce_three_arg_dispatches_and_invokes_combiner() -> None:
    calls = 0

    def combine(a: int, b: int) -> int:
        nonlocal calls
        calls += 1
        return a + b

    source = list(range(_N))
    result = await Stream.of(source).parallel().reduce(0, lambda acc, x: acc + x, combine)

    assert result == sum(source)
    assert calls > 0


@pytest.mark.asyncio
async def test_reduce_three_arg_under_sequential_equals_two_arg() -> None:
    source = list(range(_N))

    two_arg = await Stream.of(source).sequential().reduce(0, lambda acc, x: acc + x)
    three_arg = await Stream.of(source).sequential().reduce(0, lambda acc, x: acc + x, lambda a, b: a + b)

    assert three_arg == two_arg


@pytest.mark.asyncio
async def test_reduce_three_arg_parallel_equals_sequential_over_several_batches() -> None:
    source = list(range(_N))

    seq = await Stream.of(source).sequential().reduce(0, lambda acc, x: acc + x, lambda a, b: a + b)
    par = await Stream.of(source).parallel().reduce(0, lambda acc, x: acc + x, lambda a, b: a + b)

    assert par == seq


@pytest.mark.asyncio
async def test_reduce_three_arg_async_callables() -> None:
    async def accumulate(acc: int, x: int) -> int:
        await asyncio.sleep(0)
        return acc + x

    async def combine(a: int, b: int) -> int:
        await asyncio.sleep(0)
        return a + b

    source = list(range(_N))
    result = await Stream.of(source).parallel().reduce(0, accumulate, combine)

    assert result == sum(source)


@pytest.mark.asyncio
async def test_ordered_batches_over_an_empty_source_yield_nothing() -> None:
    # an op needing a global view (sorted()) forces the ordered fork-join
    # dispatch even over an empty source, exercising the empty-round exit
    # unrelated to the partitioning path this file otherwise covers
    result = await Stream.of([]).parallel().sorted().collect(to_list())
    assert result == []

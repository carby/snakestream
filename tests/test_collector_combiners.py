"""Per-collector combiner verification (make-combiners-live, tasks 4.1-4.6).

Every collector that gains a combiner gets a test asserting the .parallel()
result equals the .sequential() result over a source spanning several
batches (task 4.6) - a source small enough to be one partition would pass
without the combiner ever running, which is the trap design.md's Risks
section calls out. _N below is chosen the same way test_partitioning.py's is:
_FIRST_BATCH_SIZE=4 per worker times 4 workers pulls 16 in the first round,
so 50 elements guarantees a second round and several partitions to merge."""

import pytest

from snakestream import Stream
from snakestream.collector import Characteristics, Collector
from snakestream.collectors import (
    averaging_double,
    averaging_int,
    averaging_long,
    collecting_and_then,
    counting,
    grouping_by,
    joining,
    max_by,
    mapping,
    min_by,
    partitioning_by,
    reducing,
    summarizing_double,
    summarizing_int,
    summarizing_long,
    summing_double,
    summing_int,
    summing_long,
    to_collection,
    to_list,
    to_map,
    to_set,
)
from snakestream.exception import IllegalStateException

_N = 50


async def _parallel_equals_sequential(source: list, collector: Collector) -> None:
    seq = await Stream.of(source).sequential().collect(collector)
    par = await Stream.of(source).parallel().collect(collector)
    assert par == seq


# --- 4.1 leaf combiners ------------------------------------------------


@pytest.mark.asyncio
async def test_to_list_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), to_list())


@pytest.mark.asyncio
async def test_to_set_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), to_set())


@pytest.mark.asyncio
async def test_to_collection_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), to_collection(set))


@pytest.mark.asyncio
async def test_counting_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), counting())


@pytest.mark.asyncio
async def test_joining_combiner_matches_sequential() -> None:
    letters = [chr(ord("a") + i % 26) for i in range(_N)]
    await _parallel_equals_sequential(letters, joining(","))


@pytest.mark.asyncio
async def test_summing_int_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), summing_int(lambda x: x))


@pytest.mark.asyncio
async def test_summing_long_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), summing_long(lambda x: x))


@pytest.mark.asyncio
async def test_summarizing_int_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), summarizing_int(lambda x: x))


@pytest.mark.asyncio
async def test_summarizing_long_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), summarizing_long(lambda x: x))


@pytest.mark.asyncio
async def test_summarizing_int_combine_keeps_least_when_smaller_in_a() -> None:
    # exercises the branch where a partition's own least/greatest already
    # beats its peer's, so the merge leaves it unchanged
    source = list(range(_N, 0, -1))  # descending: earlier batches hold the larger values
    await _parallel_equals_sequential(source, summarizing_int(lambda x: x))


def _cmp(a: int, b: int) -> int:
    return a - b


@pytest.mark.asyncio
async def test_min_by_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), min_by(_cmp))


@pytest.mark.asyncio
async def test_max_by_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), max_by(_cmp))


# --- 4.2 min_by/max_by keep first-of-tied-wins under partitioning ------


@pytest.mark.asyncio
async def test_min_by_keeps_first_of_tied_wins_under_partitioning() -> None:
    # every element compares equal under this comparator, so the tie-break
    # decides everything: the first element in encounter order must win,
    # exactly as it does sequentially - the case proving combinable and
    # UNORDERED are independent (design decision 4)
    source = [(i, "first" if i == 0 else "other") for i in range(_N)]

    def all_tied(a: tuple, b: tuple) -> int:
        return 0

    seq = await Stream.of(source).sequential().collect(min_by(all_tied))
    par = await Stream.of(source).parallel().collect(min_by(all_tied))

    assert par == seq == (0, "first")
    assert Characteristics.UNORDERED not in min_by(all_tied).characteristics


@pytest.mark.asyncio
async def test_min_by_combine_awaits_an_async_comparator() -> None:
    async def async_cmp(a: int, b: int) -> int:
        return a - b

    await _parallel_equals_sequential(list(range(_N)), min_by(async_cmp))


@pytest.mark.asyncio
async def test_min_by_empty_partition_does_not_win_a_tie() -> None:
    # exercises _combine_extremum's UNSET branches: a filter thins some
    # batches to nothing, so their peer's `found` stays UNSET and must not
    # displace a real element from another partition
    source = list(range(_N))
    seq = await Stream.of(source).sequential().filter(lambda x: x < 3).collect(min_by(_cmp))
    par = await Stream.of(source).parallel().filter(lambda x: x < 3).collect(min_by(_cmp))

    assert par == seq == 0


# --- 4.1 reducing() -------------------------------------------------------


@pytest.mark.asyncio
async def test_reducing_one_arg_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), reducing(lambda a, b: a + b))


@pytest.mark.asyncio
async def test_reducing_two_arg_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), reducing(0, lambda a, b: a + b))


@pytest.mark.asyncio
async def test_reducing_three_arg_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), reducing(0, lambda x: x * 2, lambda a, b: a + b))


@pytest.mark.asyncio
async def test_reducing_one_arg_empty_partition_does_not_contribute() -> None:
    # exercises _combine_reduce's UNSET branches the same way min_by's does
    source = list(range(_N))
    seq = await Stream.of(source).sequential().filter(lambda x: x < 3).collect(reducing(lambda a, b: a + b))
    par = await Stream.of(source).parallel().filter(lambda x: x < 3).collect(reducing(lambda a, b: a + b))

    assert par == seq == 0 + 1 + 2


# --- 4.1 / 4.5 to_map -------------------------------------------------


@pytest.mark.asyncio
async def test_to_map_two_arg_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), to_map(lambda x: x, lambda x: x * x))


@pytest.mark.asyncio
async def test_to_map_two_arg_combiner_raises_on_cross_partition_duplicate() -> None:
    # two distinct elements landing in different partitions but mapping to
    # the same key must still raise, the same rule the accumulator applies
    # within one partition - _combine_to_map's own raise, not accept()'s
    source = list(range(_N))
    with pytest.raises(IllegalStateException):
        await Stream.of(source).parallel().collect(to_map(lambda x: x % 7, lambda x: x))


@pytest.mark.asyncio
async def test_to_map_three_arg_form_does_not_partition() -> None:
    collector = to_map(lambda x: x % 7, lambda x: x, lambda a, b: a + b)
    assert collector.combiner is None


@pytest.mark.asyncio
async def test_to_map_two_arg_form_partitions() -> None:
    collector = to_map(lambda x: x, lambda x: x)
    assert collector.combiner is not None


# --- 4.3 derived combiners ----------------------------------------------


@pytest.mark.asyncio
async def test_grouping_by_combiner_matches_sequential_over_combinable_downstream() -> None:
    await _parallel_equals_sequential(list(range(_N)), grouping_by(lambda x: x % 5, counting()))


@pytest.mark.asyncio
async def test_grouping_by_declares_no_combiner_over_non_combinable_downstream() -> None:
    collector = grouping_by(lambda x: x % 5, summing_double(float))
    assert collector.combiner is None
    # and the result still matches sequential - it just never partitions
    await _parallel_equals_sequential(list(range(_N)), collector)


@pytest.mark.asyncio
async def test_partitioning_by_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), partitioning_by(lambda x: x % 2 == 0, counting()))


@pytest.mark.asyncio
async def test_partitioning_by_declares_no_combiner_over_non_combinable_downstream() -> None:
    collector = partitioning_by(lambda x: x % 2 == 0, summing_double(float))
    assert collector.combiner is None


@pytest.mark.asyncio
async def test_mapping_combiner_matches_sequential() -> None:
    await _parallel_equals_sequential(list(range(_N)), mapping(lambda x: x * 2, to_list()))


@pytest.mark.asyncio
async def test_mapping_declares_no_combiner_over_non_combinable_downstream() -> None:
    collector = mapping(lambda x: x * 2, summing_double(float))
    assert collector.combiner is None
    await _parallel_equals_sequential(list(range(_N)), collector)


@pytest.mark.asyncio
async def test_collecting_and_then_combiner_matches_sequential() -> None:
    collector = collecting_and_then(to_list(), sorted)
    await _parallel_equals_sequential(list(range(_N, 0, -1)), collector)


@pytest.mark.asyncio
async def test_collecting_and_then_declares_no_combiner_over_non_combinable_downstream() -> None:
    collector = collecting_and_then(summing_double(float), lambda x: x)
    assert collector.combiner is None
    await _parallel_equals_sequential(list(range(_N)), collector)


# --- 4.4 the float family stays permanently uncombinable ----------------


@pytest.mark.asyncio
async def test_summing_double_declares_no_combiner() -> None:
    assert summing_double(float).combiner is None


@pytest.mark.asyncio
async def test_summarizing_double_declares_no_combiner() -> None:
    assert summarizing_double(float).combiner is None


@pytest.mark.asyncio
async def test_summing_double_result_is_bit_for_bit_identical_under_parallel() -> None:
    source = [i / 3 for i in range(_N)]
    await _parallel_equals_sequential(source, summing_double(lambda x: x))


@pytest.mark.asyncio
async def test_averaging_int_declares_no_combiner_despite_integral_input() -> None:
    # the one a future reader will try to "fix" (task 4.4): averaging_int's
    # elements are ints, but the accumulator is the shared _averaging(),
    # whose _AvgBox.total is a float - excluded for the same reason as the
    # rest of the float family.
    assert averaging_int(lambda x: x).combiner is None


@pytest.mark.asyncio
async def test_averaging_long_declares_no_combiner() -> None:
    assert averaging_long(lambda x: x).combiner is None


@pytest.mark.asyncio
async def test_averaging_double_declares_no_combiner() -> None:
    assert averaging_double(lambda x: x).combiner is None

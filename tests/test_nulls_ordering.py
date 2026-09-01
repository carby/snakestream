import asyncio
import functools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from snakestream import Stream
from snakestream.collectors import max_by, min_by, to_list
from snakestream.comparator import KeyComparator, NullPlacement, comparing, nulls_first, nulls_last

# --- Spec: nulls ordered to either end, over comparable values --------------


@pytest.mark.asyncio
async def test_nulls_first_orders_nulls_before_every_non_null_value() -> None:
    outset = [3, None, 1, None, 2]

    actual = await Stream.of(outset).sorted(nulls_first(comparing(lambda x: x))).collect(to_list())

    assert actual == [None, None, 1, 2, 3]


@pytest.mark.asyncio
async def test_nulls_last_orders_nulls_after_every_non_null_value() -> None:
    outset = [3, None, 1, None, 2]

    actual = await Stream.of(outset).sorted(nulls_last(comparing(lambda x: x))).collect(to_list())

    assert actual == [1, 2, 3, None, None]


@pytest.mark.asyncio
async def test_null_key_on_first_segment_falls_through_to_the_tie_break_segment() -> None:
    outset = [(None, 2), (None, 1)]

    actual = (
        await Stream.of(outset)
        .sorted(nulls_first(comparing(lambda x: x[0]).then_comparing(lambda x: x[1])))
        .collect(to_list())
    )

    assert actual == [(None, 1), (None, 2)]


@pytest.mark.asyncio
async def test_composing_a_tolerant_comparator_does_not_mutate_the_receiver() -> None:
    outset = [3, None, 1]
    base = nulls_first(comparing(lambda x: x))
    base.then_comparing(lambda x: x)

    actual = await Stream.of(outset).sorted(base).collect(to_list())

    assert actual == [None, 1, 3]


@pytest.mark.asyncio
async def test_ties_and_nulls_keep_encounter_order() -> None:
    outset = [("a", 1), (None, 0), ("b", 1), (None, 0), ("c", 1)]

    actual = await Stream.of(outset).sorted(nulls_last(comparing(lambda x: x[0]))).collect(to_list())

    # the two None-keyed elements tie with each other (both null keys) and
    # must keep their relative encounter order among themselves
    assert actual == [("a", 1), ("b", 1), ("c", 1), (None, 0), (None, 0)]


# --- 1. Null placement on the comparator -------------------------------------


@pytest.mark.asyncio
async def test_then_comparing_on_a_tolerant_chain_stays_tolerant() -> None:
    outset = [("a", None), ("a", 1), (None, 2)]

    cmp = nulls_first(comparing(lambda x: x[0])).then_comparing(lambda x: x[1])

    actual = await Stream.of(outset).sorted(cmp).collect(to_list())

    assert actual == [(None, 2), ("a", None), ("a", 1)]


@pytest.mark.asyncio
async def test_reversing_a_nulls_first_chain_places_nulls_last() -> None:
    outset = [1, None, 3, None, 2]

    actual = await Stream.of(outset).sorted(nulls_first(comparing(lambda x: x)).reversed()).collect(to_list())

    assert actual == [3, 2, 1, None, None]


# --- 2. The factories ---------------------------------------------------------


def test_nulls_first_over_key_comparator_returns_tolerant_key_comparator() -> None:
    base = comparing(lambda x: x)

    result = nulls_first(base)

    assert isinstance(result, KeyComparator)
    assert result.nulls is NullPlacement.FIRST
    assert result.segments == base.segments


@pytest.mark.asyncio
async def test_nulls_first_over_plain_comparator_wraps_and_delegates() -> None:
    def plain(a: int, b: int) -> int:
        return a - b

    cmp = nulls_first(plain)

    assert not isinstance(cmp, KeyComparator)
    assert cmp(None, None) == 0
    assert cmp(None, 1) < 0
    assert cmp(1, None) > 0
    assert cmp(1, 2) < 0


def test_nulls_first_over_nothing_returns_key_comparator_over_constant_key() -> None:
    cmp = nulls_first()

    assert isinstance(cmp, KeyComparator)
    assert cmp.nulls is NullPlacement.FIRST


@pytest.mark.asyncio
async def test_nulls_first_with_no_comparator_sorts_nulls_to_front_and_rest_stable() -> None:
    outset = [3, None, 1, None, 2]

    actual = await Stream.of(outset).sorted(nulls_first()).collect(to_list())

    assert actual == [None, None, 3, 1, 2]


@pytest.mark.asyncio
async def test_nulls_last_with_no_comparator_sorts_nulls_to_back_and_rest_stable() -> None:
    outset = [3, None, 1, None, 2]

    actual = await Stream.of(outset).sorted(nulls_last()).collect(to_list())

    assert actual == [3, 1, 2, None, None]


@pytest.mark.asyncio
async def test_async_wrapped_plain_comparator_sorts() -> None:
    async def cmp(a: int, b: int) -> int:
        await asyncio.sleep(0)
        return a - b

    outset = [3, None, 1]

    actual = await Stream.of(outset).sorted(nulls_last(cmp)).collect(to_list())

    assert actual == [1, 3, None]


@pytest.mark.asyncio
async def test_async_wrapped_comparator_direct_call_both_none() -> None:
    async def cmp(a: int, b: int) -> int:
        return a - b

    tolerant = nulls_last(cmp)

    assert await tolerant(None, None) == 0


@pytest.mark.asyncio
async def test_all_none_column_sorts_without_calling_extractor() -> None:
    calls: list[object] = []

    def key(x: object) -> object:
        calls.append(x)
        return x

    actual = await Stream.of([None, None, None]).sorted(nulls_first(comparing(key))).collect(to_list())

    assert actual == [None, None, None]
    assert calls == []


@pytest.mark.asyncio
async def test_direct_call_tolerant_async_chain_agrees_on_null_and_tie_cases() -> None:
    async def first(x: tuple) -> object:
        return x[0]

    async def second(x: tuple) -> object:
        return x[1]

    cmp = nulls_first(comparing(first).then_comparing(second))

    assert await cmp((None, 1), (None, 2)) < 0
    assert await cmp((None, 1), ("a", 1)) < 0
    assert await cmp(("a", 1), (None, 1)) > 0
    assert await cmp(("a", 1), ("a", 1)) == 0


@pytest.mark.asyncio
async def test_direct_call_tolerant_mixed_sync_async_chain() -> None:
    async def first(x: tuple) -> object:
        return x[0]

    def second(x: tuple) -> object:
        return x[1]

    cmp = nulls_first(comparing(first).then_comparing(second))

    assert await cmp((None, 1), ("a", None)) < 0
    assert await cmp(("a", None), ("a", 1)) < 0
    assert await cmp(("a", 1), ("a", 1)) == 0


@pytest.mark.asyncio
async def test_wrapped_async_comparator_bad_result_type_still_raises() -> None:
    async def bad(a: int, b: int) -> bool:
        return a > b

    with pytest.raises(TypeError):
        await Stream.of([1, 2, None]).sorted(nulls_last(bad)).collect(to_list())


# --- 3. The sorting fast path --------------------------------------------------


@pytest.mark.asyncio
async def test_key_extractor_never_invoked_with_none_element() -> None:
    calls: list[object] = []

    def key(x: object) -> object:
        calls.append(x)
        return x

    outset = [3, None, 1]
    await Stream.of(outset).sorted(nulls_first(comparing(key))).collect(to_list())

    assert None not in calls


@pytest.mark.asyncio
async def test_zero_key_sorts_as_a_key_not_a_null() -> None:
    outset = [{"v": 5}, {"v": 0}, {"v": None}]

    actual = await Stream.of(outset).sorted(nulls_last(comparing(lambda x: x["v"]))).collect(to_list())

    assert actual == [{"v": 0}, {"v": 5}, {"v": None}]


@pytest.mark.asyncio
async def test_false_key_sorts_as_a_key_not_a_null() -> None:
    outset = [{"v": True}, {"v": False}, {"v": None}]

    actual = await Stream.of(outset).sorted(nulls_last(comparing(lambda x: x["v"]))).collect(to_list())

    assert actual == [{"v": False}, {"v": True}, {"v": None}]


@pytest.mark.asyncio
async def test_empty_string_key_sorts_as_a_key_not_a_null() -> None:
    outset = [{"v": "b"}, {"v": ""}, {"v": None}]

    actual = await Stream.of(outset).sorted(nulls_last(comparing(lambda x: x["v"]))).collect(to_list())

    assert actual == [{"v": ""}, {"v": "b"}, {"v": None}]


@pytest.mark.asyncio
async def test_ascending_tolerant_chain() -> None:
    outset = [("b", 1), (None, 2), ("a", None), ("a", 1)]

    actual = (
        await Stream.of(outset)
        .sorted(nulls_first(comparing(lambda x: x[0]).then_comparing(lambda x: x[1])))
        .collect(to_list())
    )

    assert actual == [(None, 2), ("a", None), ("a", 1), ("b", 1)]


@pytest.mark.asyncio
async def test_descending_tolerant_chain() -> None:
    outset = [("b", 1), (None, 2), ("a", None), ("a", 1)]

    actual = (
        await Stream.of(outset)
        .sorted(nulls_last(comparing(lambda x: x[0]).then_comparing(lambda x: x[1])).reversed())
        .collect(to_list())
    )

    assert actual == [(None, 2), ("b", 1), ("a", None), ("a", 1)]


@pytest.mark.asyncio
async def test_mixed_direction_tolerant_chain() -> None:
    outset = [("b", 1), (None, 2), ("a", None), ("a", 1)]

    first_descending_second_ascending = comparing(lambda x: x[0]).reversed().then_comparing(lambda x: x[1])
    cmp = nulls_last(first_descending_second_ascending)

    actual = await Stream.of(outset).sorted(cmp).collect(to_list())

    assert actual == [(None, 2), ("b", 1), ("a", 1), ("a", None)]


# --- 4. The __call__ path -------------------------------------------------------


@pytest.mark.asyncio
async def test_min_over_stream_with_none_returns_none_under_nulls_first() -> None:
    outset = [3, None, 1]

    result = await Stream.of(outset).min(nulls_first(comparing(lambda x: x)))

    assert result is None


@pytest.mark.asyncio
async def test_min_over_stream_with_none_returns_smallest_under_nulls_last() -> None:
    outset = [3, None, 1]

    result = await Stream.of(outset).min(nulls_last(comparing(lambda x: x)))

    assert result == 1


@given(
    values=st.lists(
        st.tuples(st.one_of(st.none(), st.integers(min_value=0, max_value=5)), st.integers(min_value=0, max_value=1))
    ),
    first=st.booleans(),
    reverse=st.booleans(),
    chained=st.booleans(),
)
@pytest.mark.asyncio
async def test_fast_path_and_call_path_agree_across_the_matrix(
    values: list[tuple[int | None, int]], first: bool, reverse: bool, chained: bool
) -> None:
    base = comparing(lambda x: x[0])
    if chained:
        base = base.then_comparing(lambda x: x[1])

    tolerant = nulls_first(base) if first else nulls_last(base)
    if reverse:
        tolerant = tolerant.reversed()

    fast = await Stream.of(list(values)).sorted(tolerant).collect(to_list())

    def sign(a: object, b: object) -> int:
        r = tolerant(a, b)
        assert isinstance(r, int)
        return r

    slow = sorted(values, key=functools.cmp_to_key(sign))

    assert fast == slow


# --- 5. Terminals and collectors ------------------------------------------------


@pytest.mark.asyncio
async def test_min_max_min_by_max_by_accept_tolerant_comparator() -> None:
    outset = [{"v": 3}, {"v": None}, {"v": 1}]
    cmp = nulls_last(comparing(lambda x: x["v"]))

    assert await Stream.of(outset).min(cmp) == {"v": 1}
    assert await Stream.of(outset).max(cmp) == {"v": None}
    assert await Stream.of(outset).collect(min_by(cmp)) == {"v": 1}
    assert await Stream.of(outset).collect(max_by(cmp)) == {"v": None}


@pytest.mark.asyncio
async def test_tolerant_sorted_under_parallel_sorts_the_whole_stream() -> None:
    async def descending():
        yield 5
        await asyncio.sleep(0)
        yield None
        await asyncio.sleep(0)
        yield 3
        await asyncio.sleep(0)
        yield 1
        await asyncio.sleep(0)
        yield None

    actual = await Stream.of(descending()).parallel().sorted(nulls_last(comparing(lambda x: x))).collect(to_list())

    assert actual == [1, 3, 5, None, None]

import asyncio
import functools
import time

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


# --- 4.1 Chaining -----------------------------------------------------------


@pytest.mark.asyncio
async def test_then_comparing_breaks_ties_with_second_key() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1])).collect(to_list())

    assert actual == [("a", 1), ("a", 2), ("b", 1)]


@pytest.mark.asyncio
async def test_first_key_wins_when_distinct() -> None:
    outset = [("b", 9), ("a", 1), ("c", 5)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1])).collect(to_list())

    assert actual == [("a", 1), ("b", 9), ("c", 5)]


@pytest.mark.asyncio
async def test_three_segment_chain_third_decides() -> None:
    outset = [("a", 1, 2), ("a", 1, 1), ("a", 1, 3)]

    actual = (
        await Stream.of(outset)
        .sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1]).then_comparing(lambda x: x[2]))
        .collect(to_list())
    )

    assert actual == [("a", 1, 1), ("a", 1, 2), ("a", 1, 3)]


@pytest.mark.asyncio
async def test_then_comparing_accepts_another_key_comparator_preserving_direction() -> None:
    def first(x: tuple) -> str:
        return x[0]

    def second(x: tuple) -> int:
        return x[1]

    outset = [("b", 1), ("a", 2), ("a", 1)]
    tail = comparing(second).reversed()

    spliced = comparing(first).then_comparing(tail)

    assert spliced.segments == ((first, False), (second, True))
    actual = await Stream.of(outset).sorted(spliced).collect(to_list())
    assert actual == [("a", 2), ("a", 1), ("b", 1)]


# --- 4.2 Direction ------------------------------------------------------------


@pytest.mark.asyncio
async def test_reversed_single_segment() -> None:
    actual = await Stream.of([1, 3, 2]).sorted(comparing(lambda x: x).reversed()).collect(to_list())

    assert actual == [3, 2, 1]


@pytest.mark.asyncio
async def test_reversed_before_chaining_affects_only_earlier_segment() -> None:
    outset = [("a", 1), ("a", 2), ("b", 1)]

    actual = (
        await Stream.of(outset).sorted(comparing(lambda x: x[0]).reversed().then_comparing(lambda x: x[1])).collect(to_list())
    )

    assert actual == [("b", 1), ("a", 1), ("a", 2)]


@pytest.mark.asyncio
async def test_reversed_after_chaining_flips_both_segments() -> None:
    outset = [("a", 1), ("a", 2), ("b", 1)]

    actual = (
        await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1]).reversed()).collect(to_list())
    )

    assert actual == [("b", 1), ("a", 2), ("a", 1)]


@pytest.mark.asyncio
async def test_double_reversal_restores_original_ordering() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x["v"]).reversed().reversed()).collect(to_list())

    assert actual == [{"v": 1}, {"v": 2}, {"v": 3}]


@pytest.mark.asyncio
async def test_reversed_preserves_encounter_order_for_equivalent_elements() -> None:
    outset = [("a", 1), ("b", 1), ("c", 0)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[1]).reversed()).collect(to_list())

    assert actual == [("a", 1), ("b", 1), ("c", 0)]


# --- 4.3 Immutability ---------------------------------------------------------


@pytest.mark.asyncio
async def test_composing_leaves_original_comparator_unchanged() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]
    base = comparing(lambda x: x[0])
    base.then_comparing(lambda x: x[1])

    actual = await Stream.of(outset).sorted(base).collect(to_list())

    assert actual == [("a", 2), ("a", 1), ("b", 1)]


@pytest.mark.asyncio
async def test_two_compositions_of_one_comparator_are_independent() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]
    base = comparing(lambda x: x[0])

    by_second = base.then_comparing(lambda x: x[1])
    reversed_base = base.reversed()

    assert await Stream.of(outset).sorted(by_second).collect(to_list()) == [("a", 1), ("a", 2), ("b", 1)]
    assert await Stream.of(outset).sorted(reversed_base).collect(to_list()) == [("b", 1), ("a", 2), ("a", 1)]


# --- 4.4 Sync/async -----------------------------------------------------------


@pytest.mark.asyncio
async def test_all_sync_all_async_and_mixed_chains_agree() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    async def async_first(x: tuple) -> str:
        await asyncio.sleep(0)
        return x[0]

    async def async_second(x: tuple) -> int:
        await asyncio.sleep(0)
        return x[1]

    all_sync = comparing(lambda x: x[0]).then_comparing(lambda x: x[1])
    all_async = comparing(async_first).then_comparing(async_second)
    mixed = comparing(lambda x: x[0]).then_comparing(async_second)

    expected = [("a", 1), ("a", 2), ("b", 1)]
    assert await Stream.of(outset).sorted(all_sync).collect(to_list()) == expected
    assert await Stream.of(outset).sorted(all_async).collect(to_list()) == expected
    assert await Stream.of(outset).sorted(mixed).collect(to_list()) == expected


@pytest.mark.asyncio
async def test_async_chain_works_with_min_max_min_by_max_by() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    async def key1(x: tuple) -> str:
        return x[0]

    async def key2(x: tuple) -> int:
        return x[1]

    cmp = comparing(key1).then_comparing(key2)

    assert await Stream.of(outset).min(cmp) == ("a", 1)
    assert await Stream.of(outset).max(cmp) == ("b", 1)
    assert await Stream.of(outset).collect(min_by(cmp)) == ("a", 1)
    assert await Stream.of(outset).collect(max_by(cmp)) == ("b", 1)


# --- 4.5 Extraction counts -----------------------------------------------------


@pytest.mark.asyncio
async def test_each_of_k_extractors_invoked_exactly_n_times() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1), ("c", 0)]
    first_calls: list[str] = []
    second_calls: list[int] = []

    def first(x: tuple) -> str:
        first_calls.append(x[0])
        return x[0]

    def second(x: tuple) -> int:
        second_calls.append(x[1])
        return x[1]

    await Stream.of(outset).sorted(comparing(first).then_comparing(second)).collect(to_list())

    assert len(first_calls) == len(outset)
    assert len(second_calls) == len(outset)


@pytest.mark.asyncio
async def test_direct_call_on_mixed_sync_async_descending_chain() -> None:
    async def second(x: tuple) -> int:
        return x[1]

    cmp = comparing(lambda x: x[0]).then_comparing(second).reversed()

    tie_sign = await cmp(("a", 1), ("a", 2))
    distinct_sign = await cmp(("a", 1), ("b", 1))

    assert tie_sign > 0
    assert distinct_sign > 0


def test_direct_call_leaves_later_extractor_uninvoked_when_first_key_decides() -> None:
    calls: list[int] = []

    def second(x: tuple) -> int:
        calls.append(x[1])
        return x[1]

    cmp = comparing(lambda x: x[0]).then_comparing(second)

    sign = cmp(("a", 1), ("b", 1))

    assert sign < 0
    assert calls == []


# --- 4.6 Eagerness --------------------------------------------------------------


@pytest.mark.asyncio
async def test_later_extractor_error_propagates_even_when_first_keys_distinct() -> None:
    outset = [("a", 1), ("b", 2), ("c", 3)]

    def failing_second(x: tuple) -> int:
        if x[0] == "b":
            raise ValueError("boom")
        return x[1]

    with pytest.raises(ValueError, match="boom"):
        await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(failing_second)).collect(to_list())


# --- 4.7 Concurrency across segments --------------------------------------------


@pytest.mark.asyncio
async def test_k_async_columns_do_not_serialize() -> None:
    outset = list(range(20))
    delay = 0.05

    async def key1(x: int) -> int:
        await asyncio.sleep(delay)
        return x % 5

    async def key2(x: int) -> int:
        await asyncio.sleep(delay)
        return x

    async def key3(x: int) -> int:
        await asyncio.sleep(delay)
        return -x

    cmp = comparing(key1).then_comparing(key2).then_comparing(key3)

    start = time.monotonic()
    await Stream.of(outset).sorted(cmp).collect(to_list())
    elapsed = time.monotonic() - start

    assert elapsed < delay * 3


# --- 4.8 Both paths agree --------------------------------------------------------


@pytest.mark.asyncio
async def test_min_equals_first_element_of_sorted_result_for_chained_comparator() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1), ("c", 0)]
    cmp = comparing(lambda x: x[0]).then_comparing(lambda x: x[1]).reversed()

    sorted_result = await Stream.of(outset).sorted(cmp).collect(to_list())
    minimum = await Stream.of(outset).min(cmp)

    assert minimum == sorted_result[0]


# --- 4.9 Key typing ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_incomparable_keys_within_one_segment_raise_type_error() -> None:
    outset = [(1, "x"), ("a", "y"), (2, "z")]

    with pytest.raises(TypeError):
        await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1])).collect(to_list())


@pytest.mark.asyncio
async def test_earlier_segment_distinguishing_every_pair_does_not_excuse_a_later_one() -> None:
    outset = [(1, "x"), (2, 1), (3, "y")]

    with pytest.raises(TypeError):
        await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1])).collect(to_list())


@pytest.mark.asyncio
async def test_segments_may_produce_unrelated_key_types() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1])).collect(to_list())

    assert actual == [("a", 1), ("a", 2), ("b", 1)]


# --- 4.10 reverse=True stacked with reversed() ------------------------------------


@pytest.mark.asyncio
async def test_sorted_reverse_true_stacked_on_reversed_chain_flips_ties_too() -> None:
    outset = [("a", 1), ("b", 1), ("c", 0)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[1]).reversed(), reverse=True).collect(to_list())

    # reversed() (comparator negation) orders [("a", 1), ("b", 1), ("c", 0)] -
    # ties keep encounter order; sorted()'s reverse=True then flips the whole
    # buffer, which also flips the tie.
    assert actual == [("c", 0), ("b", 1), ("a", 1)]

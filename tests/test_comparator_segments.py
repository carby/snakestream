import asyncio
import functools
import operator

import pytest

from snakestream import Stream
from snakestream.collectors import max_by, min_by, to_list
from snakestream.comparator import _is_comparator_arity, comparing, nulls_first, nulls_last
from snakestream.exception import StreamBuildException

# --- 2.1 Arity classification -----------------------------------------------


def _record_second(x: tuple) -> int:
    return x[1]


class _TwoArgComparator:
    def __call__(self, a: tuple, b: tuple) -> int:
        return (a[0] > b[0]) - (a[0] < b[0])


def _starred(*_args: object) -> int:
    return 0


@pytest.mark.asyncio
async def test_one_argument_callable_is_a_key_extractor() -> None:
    outset = [("b", 2), ("a", 1)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(_record_second)).collect(to_list())

    assert actual == [("a", 1), ("b", 2)]


@pytest.mark.asyncio
async def test_two_argument_callable_is_a_comparator() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    actual = (
        await Stream.of(outset)
        .sorted(comparing(lambda x: x[0]).then_comparing(lambda a, b: (a[1] > b[1]) - (a[1] < b[1])))
        .collect(to_list())
    )

    assert actual == [("a", 1), ("a", 2), ("b", 1)]


@pytest.mark.asyncio
async def test_callable_object_with_two_arg_call_is_a_comparator() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[1]).then_comparing(_TwoArgComparator())).collect(to_list())

    assert actual == [("a", 1), ("b", 1), ("a", 2)]


@pytest.mark.asyncio
async def test_functools_partial_resolves_to_one_arg_extractor() -> None:
    def two(fixed: int, x: tuple) -> int:
        return x[fixed]

    outset = [("b", 1), ("a", 2), ("a", 1)]
    partial_extractor = functools.partial(two, 1)

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(partial_extractor)).collect(to_list())

    assert actual == [("a", 1), ("a", 2), ("b", 1)]


@pytest.mark.asyncio
async def test_attrgetter_resolves_to_one_arg_extractor() -> None:
    class Rec:  # noqa: PLW1641 - equality-only helper, never hashed
        def __init__(self, x: int) -> None:
            self.x = x

        def __eq__(self, other: object) -> bool:
            return isinstance(other, Rec) and self.x == other.x

        def __repr__(self) -> str:
            return f"Rec({self.x})"

    outset = [Rec(3), Rec(1), Rec(2)]

    actual = await Stream.of(outset).sorted(comparing(operator.attrgetter("x"))).collect(to_list())

    assert actual == [Rec(1), Rec(2), Rec(3)]


@pytest.mark.asyncio
async def test_c_builtin_resolves_to_one_arg_extractor() -> None:
    outset = ["ccc", "a", "bb"]

    actual = await Stream.of(outset).sorted(comparing(len)).collect(to_list())

    assert actual == ["a", "bb", "ccc"]


@pytest.mark.asyncio
async def test_starred_args_is_indeterminate_and_defaults_to_key_extractor() -> None:
    outset = [3, 1, 2]

    # _starred always returns 0 as a "key" - every element becomes equivalent,
    # so sorting is a stability check: encounter order is preserved.
    actual = await Stream.of(outset).sorted(comparing(lambda x: 0).then_comparing(_starred)).collect(to_list())

    assert actual == [3, 1, 2]


def test_is_comparator_arity_returns_false_when_signature_cannot_be_determined() -> None:
    assert _is_comparator_arity(object()) is False


def test_is_comparator_arity_ignores_keyword_only_parameters() -> None:
    def two_positional_and_keyword_only(a: int, b: int, *, c: int = 0) -> int:
        return (a > b) - (a < b)

    assert _is_comparator_arity(two_positional_and_keyword_only) is True


def test_key_based_comparator_is_spliced_rather_than_classified_by_arity() -> None:
    def first(x: tuple) -> str:
        return x[0]

    def second(x: tuple) -> int:
        return x[1]

    tail = comparing(second).reversed()
    spliced = comparing(first).then_comparing(tail)

    assert spliced.segments == ((first, False), (second, True))


# --- 2.2 Bare comparator accepted as a tie-break ----------------------------


@pytest.mark.asyncio
async def test_supplied_comparator_breaks_ties() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(cmp_second)).collect(to_list())

    assert actual == [("a", 1), ("a", 2), ("b", 1)]


@pytest.mark.asyncio
async def test_earlier_ordering_wins_where_decisive_over_supplied_comparator() -> None:
    outset = [("b", 9), ("a", 1), ("c", 5)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(cmp_second)).collect(to_list())

    assert actual == [("a", 1), ("b", 9), ("c", 5)]


@pytest.mark.asyncio
async def test_supplied_comparator_consulted_by_every_comparator_consuming_operation() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    cmp = comparing(lambda x: x[0]).then_comparing(cmp_second)

    assert await Stream.of(outset).sorted(cmp).collect(to_list()) == [("a", 1), ("a", 2), ("b", 1)]
    assert await Stream.of(outset).min(cmp) == ("a", 1)
    assert await Stream.of(outset).max(cmp) == ("b", 1)
    assert await Stream.of(outset).collect(min_by(cmp)) == ("a", 1)
    assert await Stream.of(outset).collect(max_by(cmp)) == ("b", 1)


@pytest.mark.asyncio
async def test_supplied_comparator_can_be_chained_onto_further() -> None:
    outset = [("a", 1, 2), ("a", 1, 1), ("a", 1, 3)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = (
        await Stream.of(outset)
        .sorted(comparing(lambda x: x[0]).then_comparing(cmp_second).then_comparing(lambda x: x[2]))
        .collect(to_list())
    )

    assert actual == [("a", 1, 1), ("a", 1, 2), ("a", 1, 3)]


# --- 2.3 Two-argument comparing()/then_comparing() --------------------------


@pytest.mark.asyncio
async def test_comparing_with_key_comparator_orders_by_supplied_ordering() -> None:
    outset = [{"v": 1}, {"v": 2}, {"v": 3}]

    def reverse_ints(a: int, b: int) -> int:
        return (a < b) - (a > b)

    actual = await Stream.of(outset).sorted(comparing(lambda x: x["v"], reverse_ints)).collect(to_list())

    assert actual == [{"v": 3}, {"v": 2}, {"v": 1}]


@pytest.mark.asyncio
async def test_then_comparing_two_argument_form_orders_identically_to_bare_comparator() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    def reverse_ints(a: int, b: int) -> int:
        return (a < b) - (a > b)

    actual = (
        await Stream.of(outset)
        .sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1], reverse_ints))
        .collect(to_list())
    )

    assert actual == [("a", 2), ("a", 1), ("b", 1)]


@pytest.mark.asyncio
async def test_keys_with_no_natural_ordering_are_orderable_via_supplied_comparator() -> None:
    class Unorderable:
        def __init__(self, v: int) -> None:
            self.v = v

    outset = [{"k": Unorderable(3)}, {"k": Unorderable(1)}, {"k": Unorderable(2)}]

    def by_v(a: Unorderable, b: Unorderable) -> int:
        return (a.v > b.v) - (a.v < b.v)

    actual = await Stream.of(outset).sorted(comparing(lambda x: x["k"], by_v)).collect(to_list())

    assert [e["k"].v for e in actual] == [1, 2, 3]


# --- 2.4 Async comparator rejected at construction --------------------------


def test_async_bare_comparator_rejected_at_construction() -> None:
    async def async_cmp(a: object, b: object) -> int:
        return 0

    with pytest.raises(StreamBuildException):
        comparing(lambda x: x).then_comparing(async_cmp)


def test_async_key_comparator_rejected_at_construction_via_comparing() -> None:
    async def async_cmp(a: object, b: object) -> int:
        return 0

    with pytest.raises(StreamBuildException):
        comparing(lambda x: x, async_cmp)


def test_async_key_comparator_rejected_at_construction_via_then_comparing() -> None:
    async def async_cmp(a: object, b: object) -> int:
        return 0

    with pytest.raises(StreamBuildException):
        comparing(lambda x: x).then_comparing(lambda x: x, async_cmp)


def test_error_names_supported_alternatives() -> None:
    async def async_cmp(a: object, b: object) -> int:
        return 0

    with pytest.raises(StreamBuildException, match="key extractor") as exc_info:
        comparing(lambda x: x, async_cmp)
    assert "sorted()" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_key_extractor_with_sync_key_comparator_is_accepted() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    async def key(x: dict) -> int:
        await asyncio.sleep(0)
        return x["v"]

    def reverse_ints(a: int, b: int) -> int:
        return (a < b) - (a > b)

    actual = await Stream.of(outset).sorted(comparing(key, reverse_ints)).collect(to_list())

    assert actual == [{"v": 3}, {"v": 2}, {"v": 1}]


# --- 3.1 / 3.2 Sorting path: direction lanes and tolerant column ------------


@pytest.mark.asyncio
async def test_single_comparator_segment_sorts_correctly() -> None:
    outset = [3, 1, 2]

    def natural(a: int, b: int) -> int:
        return (a > b) - (a < b)

    actual = await Stream.of(outset).sorted(comparing(lambda x: x).then_comparing(natural)).collect(to_list())

    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_comparator_segment_plain_ascending_lane() -> None:
    outset = [("a", 3), ("a", 1), ("a", 2)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(cmp_second)).collect(to_list())

    assert actual == [("a", 1), ("a", 2), ("a", 3)]


@pytest.mark.asyncio
async def test_comparator_segment_under_reverse_true() -> None:
    outset = [("a", 3), ("a", 1), ("a", 2)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = (
        await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(cmp_second), reverse=True).collect(to_list())
    )

    assert actual == [("a", 3), ("a", 2), ("a", 1)]


@pytest.mark.asyncio
async def test_comparator_segment_descending_in_mixed_chain() -> None:
    outset = [("a", 1, 3), ("a", 1, 1), ("a", 1, 2)]

    def cmp_third(a: tuple, b: tuple) -> int:
        return (a[2] > b[2]) - (a[2] < b[2])

    actual = (
        await Stream.of(outset)
        .sorted(comparing(lambda x: x[0]).then_comparing(lambda x: x[1]).then_comparing(cmp_third).reversed())
        .collect(to_list())
    )

    # everything reversed: first two keys are all-equal (no effect), third
    # (comparator) segment reversed - so [1,2,3] -> [3,2,1] on the third field
    assert [x[2] for x in actual] == [3, 2, 1]


@pytest.mark.asyncio
async def test_comparator_segment_as_second_component_of_tuple_key() -> None:
    outset = [("b", 2), ("a", 3), ("a", 1)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(cmp_second)).collect(to_list())

    assert actual == [("a", 1), ("a", 3), ("b", 2)]


# --- 3.3 Coroutine-lying comparator names the async rejection ---------------


class _CoroutineReturningComparator:
    """A plain `def __call__` that returns a coroutine - classifies as sync
    via is_async_callable, so only the segment wrapper's own coroutine check
    (Decision 3) catches it."""

    def __call__(self, a: object, b: object) -> object:
        async def _inner() -> int:
            return 0

        return _inner()


@pytest.mark.asyncio
async def test_coroutine_lying_comparator_names_async_rejection() -> None:
    outset = [1, 2, 3]

    with pytest.raises(StreamBuildException, match="synchronous"):
        # first segment ties every pair, forcing the comparator segment to be
        # the one actually consulted rather than short-circuited past
        await (
            Stream.of(outset).sorted(comparing(lambda x: 0).then_comparing(_CoroutineReturningComparator())).collect(to_list())
        )


# --- 4.1 Direct-comparison path agrees with sorted() ------------------------


@pytest.mark.asyncio
async def test_min_max_min_by_max_by_agree_with_sorted_for_comparator_segment() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1), ("c", 0)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    cmp = comparing(lambda x: x[0]).then_comparing(cmp_second)

    sorted_result = await Stream.of(outset).sorted(cmp).collect(to_list())
    assert await Stream.of(outset).min(cmp) == sorted_result[0]
    assert await Stream.of(outset).max(cmp) == sorted_result[-1]
    assert await Stream.of(outset).collect(min_by(cmp)) == sorted_result[0]
    assert await Stream.of(outset).collect(max_by(cmp)) == sorted_result[-1]


# --- 4.2 Bool contract on both paths -----------------------------------------


@pytest.mark.asyncio
async def test_bool_returning_supplied_comparator_raises_type_error_via_sorted() -> None:
    outset = [1, 2, 3]

    def bool_cmp(a: int, b: int) -> bool:
        return a > b

    with pytest.raises(TypeError):
        await Stream.of(outset).sorted(comparing(lambda x: 0).then_comparing(bool_cmp)).collect(to_list())


def test_bool_returning_supplied_comparator_raises_type_error_via_direct_call() -> None:
    def bool_cmp(a: int, b: int) -> bool:
        return a > b

    cmp = comparing(lambda x: 0).then_comparing(bool_cmp)

    with pytest.raises(TypeError):
        cmp(1, 2)


@pytest.mark.asyncio
async def test_bool_returning_key_comparator_raises_type_error_via_sorted() -> None:
    outset = [1, 2, 3]

    def bool_cmp(a: int, b: int) -> bool:
        return a > b

    with pytest.raises(TypeError):
        await Stream.of(outset).sorted(comparing(lambda x: x, bool_cmp)).collect(to_list())


def test_bool_returning_key_comparator_raises_type_error_via_direct_call() -> None:
    def bool_cmp(a: int, b: int) -> bool:
        return a > b

    cmp = comparing(lambda x: x, bool_cmp)

    with pytest.raises(TypeError):
        cmp(1, 2)


def test_direct_call_two_argument_comparator_segment_with_one_side_null() -> None:
    def by_int(a: int, b: int) -> int:
        return (a > b) - (a < b)

    cmp = nulls_first(comparing(lambda x: x, by_int))

    assert cmp(None, 3) < 0
    assert cmp(3, None) > 0


@pytest.mark.asyncio
async def test_direct_call_async_two_argument_comparator_segment() -> None:
    async def key(x: int) -> int:
        return x

    def by_int(a: int, b: int) -> int:
        return (a > b) - (a < b)

    cmp = comparing(key, by_int)

    assert await cmp(1, 2) < 0
    assert await cmp(2, 1) > 0


@pytest.mark.asyncio
async def test_direct_call_async_two_argument_comparator_segment_null_tolerant() -> None:
    async def key(x: int) -> int:
        return x

    def by_int(a: int, b: int) -> int:
        return (a > b) - (a < b)

    cmp = nulls_first(comparing(key, by_int))

    assert await cmp(None, 3) < 0
    assert await cmp(3, None) > 0
    assert await cmp(None, None) == 0


@pytest.mark.asyncio
async def test_direct_call_async_bool_returning_key_comparator_raises_type_error() -> None:
    async def key(x: int) -> int:
        return x

    def bool_cmp(a: int, b: int) -> bool:
        return a > b

    cmp = comparing(key, bool_cmp)

    with pytest.raises(TypeError):
        await cmp(1, 2)


@pytest.mark.asyncio
async def test_direct_call_async_bare_comparator_segment() -> None:
    async def key(x: tuple) -> str:
        return x[0]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    cmp = comparing(key).then_comparing(cmp_second)

    assert await cmp(("a", 1), ("a", 2)) < 0
    assert await cmp(("a", 1), ("b", 1)) < 0


# --- 5.1 Reversal composes ----------------------------------------------------


@pytest.mark.asyncio
async def test_reversed_after_comparator_segment_negates_it() -> None:
    outset = [1, 3, 2]

    def natural(a: int, b: int) -> int:
        return (a > b) - (a < b)

    actual = await Stream.of(outset).sorted(comparing(lambda x: x).then_comparing(natural).reversed()).collect(to_list())

    assert actual == [3, 2, 1]


@pytest.mark.asyncio
async def test_reversed_before_chaining_flips_only_earlier_ordering() -> None:
    outset = [("a", 1), ("a", 2), ("b", 1)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).reversed().then_comparing(cmp_second)).collect(to_list())

    assert actual == [("b", 1), ("a", 1), ("a", 2)]


# --- 5.2 Null tolerance composes ----------------------------------------------


@pytest.mark.asyncio
async def test_null_tolerant_comparator_segment_places_none_and_never_invokes_comparator() -> None:
    outset = [{"v": 2}, None, {"v": 1}]
    calls: list[tuple] = []

    def natural(a: dict, b: dict) -> int:
        calls.append((a, b))
        return (a["v"] > b["v"]) - (a["v"] < b["v"])

    # a constant first segment ties every pair, so the comparator segment is
    # the one that actually orders the null-tolerant chain
    cmp = nulls_first(comparing(lambda x: 0).then_comparing(natural))
    actual = await Stream.of(outset).sorted(cmp).collect(to_list())

    assert actual == [None, {"v": 1}, {"v": 2}]
    assert all(a is not None and b is not None for a, b in calls)


@pytest.mark.asyncio
async def test_null_tolerant_comparator_segment_nulls_last() -> None:
    outset = [{"v": 2}, None, {"v": 1}]

    def natural(a: dict, b: dict) -> int:
        return (a["v"] > b["v"]) - (a["v"] < b["v"])

    cmp = nulls_last(comparing(lambda x: 0).then_comparing(natural))
    actual = await Stream.of(outset).sorted(cmp).collect(to_list())

    assert actual == [{"v": 1}, {"v": 2}, None]


# --- 5.3 nulls_first/nulls_last(comparator) recognised as a comparator ------


@pytest.mark.asyncio
async def test_nulls_first_wrapped_comparator_recognised_by_then_comparing() -> None:
    # nulls_first()/nulls_last() over a bare comparator has a two-argument
    # __call__, so it must classify as a comparator (Decision 4) rather than
    # be misread as a one-argument key extractor and die on argument count -
    # no None element is needed to exercise that classification.
    outset = [("a", 3), ("a", 1), ("a", 2)]

    def natural(a: int, b: int) -> int:
        return (a > b) - (a < b)

    def to_key(x: tuple) -> int:
        return x[1]

    wrapped = nulls_first(lambda a, b: natural(to_key(a), to_key(b)))
    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(wrapped)).collect(to_list())

    assert actual == [("a", 1), ("a", 2), ("a", 3)]


@pytest.mark.asyncio
async def test_nulls_last_wrapped_comparator_recognised_by_then_comparing() -> None:
    outset = [("a", 3), ("a", 1), ("a", 2)]

    def natural(a: int, b: int) -> int:
        return (a > b) - (a < b)

    def to_key(x: tuple) -> int:
        return x[1]

    wrapped = nulls_last(lambda a, b: natural(to_key(a), to_key(b)))
    actual = await Stream.of(outset).sorted(comparing(lambda x: x[0]).then_comparing(wrapped)).collect(to_list())

    assert actual == [("a", 1), ("a", 2), ("a", 3)]


# --- 5.4 Stability -------------------------------------------------------------


@pytest.mark.asyncio
async def test_comparator_segment_chain_is_stable_sequentially() -> None:
    outset = [("a", 1, "x"), ("b", 1, "y"), ("c", 0, "z")]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = await Stream.of(outset).sorted(comparing(lambda x: x[1]).then_comparing(cmp_second)).collect(to_list())

    assert actual == [("c", 0, "z"), ("a", 1, "x"), ("b", 1, "y")]


@pytest.mark.asyncio
async def test_comparator_segment_chain_is_stable_under_parallel() -> None:
    async def source() -> object:
        for x, y, z in [("a", 1, "x"), ("b", 1, "y"), ("c", 0, "z")]:
            await asyncio.sleep(0)
            yield (x, y, z)

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    actual = (
        await Stream.of(source()).parallel().sorted(comparing(lambda x: x[1]).then_comparing(cmp_second)).collect(to_list())
    )

    assert actual == [("c", 0, "z"), ("a", 1, "x"), ("b", 1, "y")]


# --- 5.5 Fast path and __call__ agree across shapes --------------------------


def _sign(cmp: object, a: object, b: object) -> int:
    r = cmp(a, b)  # type: ignore[operator]
    assert isinstance(r, int)
    return r


@pytest.mark.asyncio
async def test_fast_path_and_call_agree_bare_comparator_segment() -> None:
    outset = [("b", 1), ("a", 2), ("a", 1)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    cmp = comparing(lambda x: x[0]).then_comparing(cmp_second)

    fast = await Stream.of(outset).sorted(cmp).collect(to_list())
    slow = sorted(outset, key=functools.cmp_to_key(lambda a, b: _sign(cmp, a, b)))

    assert fast == slow


@pytest.mark.asyncio
async def test_fast_path_and_call_agree_two_argument_form() -> None:
    outset = [{"v": 3}, {"v": 1}, {"v": 2}]

    def reverse_ints(a: int, b: int) -> int:
        return (a < b) - (a > b)

    cmp = comparing(lambda x: x["v"], reverse_ints)

    fast = await Stream.of(outset).sorted(cmp).collect(to_list())
    slow = sorted(outset, key=functools.cmp_to_key(lambda a, b: _sign(cmp, a, b)))

    assert fast == slow


@pytest.mark.asyncio
async def test_fast_path_and_call_agree_reversed_before_and_after_chaining() -> None:
    outset = [("a", 1), ("a", 2), ("b", 1)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    before = comparing(lambda x: x[0]).reversed().then_comparing(cmp_second)
    after = comparing(lambda x: x[0]).then_comparing(cmp_second).reversed()

    for cmp in (before, after):
        fast = await Stream.of(outset).sorted(cmp).collect(to_list())
        slow = sorted(outset, key=functools.cmp_to_key(lambda a, b, c=cmp: _sign(c, a, b)))
        assert fast == slow


@pytest.mark.asyncio
async def test_fast_path_and_call_agree_mixed_directions() -> None:
    outset = [("a", 1, 3), ("a", 1, 1), ("a", 1, 2), ("b", 0, 0)]

    def cmp_third(a: tuple, b: tuple) -> int:
        return (a[2] > b[2]) - (a[2] < b[2])

    cmp = comparing(lambda x: x[0]).then_comparing(lambda x: x[1]).then_comparing(cmp_third).reversed()

    fast = await Stream.of(outset).sorted(cmp).collect(to_list())
    slow = sorted(outset, key=functools.cmp_to_key(lambda a, b: _sign(cmp, a, b)))

    assert fast == slow


@pytest.mark.asyncio
async def test_fast_path_and_call_agree_null_tolerant() -> None:
    outset = [{"v": 2}, None, {"v": 1}, {"v": 2}]

    def natural(a: dict, b: dict) -> int:
        return (a["v"] > b["v"]) - (a["v"] < b["v"])

    cmp = nulls_first(comparing(lambda x: 0).then_comparing(natural))

    fast = await Stream.of(outset).sorted(cmp).collect(to_list())

    def call_sign(a: object, b: object) -> int:
        r = cmp(a, b)
        assert isinstance(r, int)
        return r

    slow = sorted(outset, key=functools.cmp_to_key(call_sign))

    assert fast == slow


@pytest.mark.asyncio
async def test_fast_path_and_call_agree_on_ties() -> None:
    outset = [("a", 1), ("b", 1), ("c", 0)]

    def cmp_second(a: tuple, b: tuple) -> int:
        return (a[1] > b[1]) - (a[1] < b[1])

    cmp = comparing(lambda x: x[1]).then_comparing(cmp_second)

    fast = await Stream.of(outset).sorted(cmp).collect(to_list())
    slow = sorted(outset, key=functools.cmp_to_key(lambda a, b: _sign(cmp, a, b)))

    assert fast == slow

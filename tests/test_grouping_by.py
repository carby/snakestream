import asyncio
from collections import OrderedDict

import pytest

from snakestream.collector import Characteristics
from snakestream.exception import StreamBuildException
from snakestream.collectors import counting, grouping_by, joining, mapping, to_list, to_set
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_grouping_by_no_downstream_buckets_into_lists() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2))

    # then
    assert result == {1: [1, 3, 5], 0: [2, 4]}


@pytest.mark.asyncio
async def test_grouping_by_empty_stream_returns_empty_dict() -> None:
    # when
    result = await Stream.of([]).collect(grouping_by(lambda x: x))

    # then
    assert result == {}


@pytest.mark.asyncio
async def test_grouping_by_only_produced_keys_present() -> None:
    # when
    result = await Stream.of([1, 1, 1]).collect(grouping_by(lambda x: x))

    # then
    assert result == {1: [1, 1, 1]}


@pytest.mark.asyncio
async def test_grouping_by_async_classifier_is_awaited() -> None:
    async def async_classifier(x: int) -> int:
        await asyncio.sleep(0.01)
        return x % 2

    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(async_classifier))

    # then
    assert result == {1: [1, 3, 5], 0: [2, 4]}


@pytest.mark.asyncio
async def test_grouping_by_with_counting_downstream() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, counting()))

    # then
    assert result == {1: 3, 0: 2}


@pytest.mark.asyncio
async def test_grouping_by_with_joining_downstream() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc", "dd"]).collect(grouping_by(len, joining(", ")))

    # then
    assert result == {1: "a", 2: "bb, dd", 3: "ccc"}


@pytest.mark.asyncio
async def test_grouping_by_only_present_keys_get_downstream_reduced_entry() -> None:
    # when
    result = await Stream.of(["a", "bb", "bbb"]).collect(grouping_by(len, counting()))

    # then
    assert result == {1: 1, 2: 1, 3: 1}
    assert 4 not in result


def test_grouping_by_reports_unordered_with_an_unordered_downstream() -> None:
    assert Characteristics.UNORDERED in grouping_by(len, to_set()).characteristics


def test_grouping_by_does_not_report_unordered_with_an_ordered_downstream() -> None:
    assert Characteristics.UNORDERED not in grouping_by(len, to_list()).characteristics


def test_grouping_by_default_downstream_is_ordered() -> None:
    # the default collects each group into a list, which observes order
    assert Characteristics.UNORDERED not in grouping_by(len).characteristics


def test_grouping_by_derivation_composes_through_nesting() -> None:
    # derived through the adapter to the innermost downstream
    assert Characteristics.UNORDERED in grouping_by(len, mapping(str, to_set())).characteristics


@pytest.mark.asyncio
async def test_grouping_by_into_a_set_collects_equal_in_either_order() -> None:
    # given the same elements in two orders
    forward = [0, 8, 16, 24, 32]
    backward = list(reversed(forward))

    # when
    one = await Stream.of(forward).collect(grouping_by(lambda n: n % 3, to_set()))
    other = await Stream.of(backward).collect(grouping_by(lambda n: n % 3, to_set()))

    # then the declared characteristic is true of the behaviour
    assert one == other


@pytest.mark.asyncio
async def test_grouping_by_with_a_map_factory_returns_the_callers_type() -> None:
    # given the 3-arg form, whose second argument chooses the result container
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, OrderedDict, counting()))

    # then the caller's mapping reaches the caller intact, not copied into a dict
    assert isinstance(result, OrderedDict)
    assert result == {1: 3, 0: 2}


@pytest.mark.asyncio
async def test_grouping_by_map_factory_survives_a_downstream_finisher() -> None:
    # given a downstream that has a finisher, which is where a rebuild into
    # dict would have destroyed the caller's type
    result = await Stream.of(["a", "bb", "ccc", "dd"]).collect(grouping_by(len, OrderedDict, joining(", ")))

    # then each key's finished value is in the mapping, and it is still an OrderedDict
    assert isinstance(result, OrderedDict)
    assert result == {1: "a", 2: "bb, dd", 3: "ccc"}


@pytest.mark.asyncio
async def test_grouping_by_calls_its_map_factory_once_per_collection() -> None:
    # given one collector instance reused across two collections
    collector = grouping_by(lambda x: x % 2, OrderedDict, to_list())

    # when
    first = await Stream.of([1, 2]).collect(collector)
    second = await Stream.of([3]).collect(collector)

    # then each collection got its own mapping
    assert first is not second
    assert first == {1: [1], 0: [2]}
    assert second == {1: [3]}


@pytest.mark.asyncio
async def test_grouping_by_with_a_map_factory_over_an_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(grouping_by(lambda x: x, OrderedDict, to_list()))

    # then the caller's type survives even with no groups to put in it
    assert isinstance(result, OrderedDict)
    assert result == {}


@pytest.mark.asyncio
async def test_grouping_by_awaits_an_async_map_factory() -> None:
    # given a factory that has to be awaited before it yields a container
    async def make() -> OrderedDict[int, list[int]]:
        await asyncio.sleep(0)
        return OrderedDict()

    # when
    result = await Stream.of([1, 2, 3]).collect(grouping_by(lambda x: x % 2, make, to_list()))

    # then
    assert isinstance(result, OrderedDict)
    assert result == {1: [1, 3], 0: [2]}


@pytest.mark.asyncio
async def test_grouping_by_with_a_map_factory_rejects_non_collector_downstream() -> None:
    # given the check runs after the arity branch, so the 3-arg form gets it too
    async def not_a_collector(composition):
        return [x async for x in composition]

    with pytest.raises(StreamBuildException):
        grouping_by(lambda x: x, OrderedDict, not_a_collector)


@pytest.mark.asyncio
async def test_grouping_by_two_argument_call_still_binds_downstream() -> None:
    """The regression pair for arity dispatch: Java puts map_factory second, and
    a two-argument call must still read its second argument as the downstream."""
    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, counting()))

    # then the Collector went to downstream, not to map_factory
    assert result == {1: 3, 0: 2}
    assert type(result) is dict


@pytest.mark.asyncio
async def test_grouping_by_one_argument_call_is_unchanged() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2))

    # then
    assert result == {1: [1, 3, 5], 0: [2, 4]}
    assert type(result) is dict


def test_grouping_by_with_a_map_factory_clears_the_mark() -> None:
    # given a container whose equality is order-sensitive, which is what the
    # shipped derivation rests on dict *not* being
    assert Characteristics.UNORDERED not in grouping_by(len, OrderedDict, to_set()).characteristics


def test_grouping_by_clears_the_mark_even_for_dict() -> None:
    """The exclusion follows from map_factory being supplied at all, not from
    the type it produces - deciding from the type would mean running a
    per-collection supplier early, or whitelisting `map_factory is dict`."""
    assert Characteristics.UNORDERED not in grouping_by(len, dict, to_set()).characteristics

    # and the two-argument form, which supplies no factory, still declares it
    assert Characteristics.UNORDERED in grouping_by(len, to_set()).characteristics

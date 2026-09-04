import asyncio

import pytest

from snakestream.collectors import to_list
from snakestream.spliterator import BATCH_SIZE, Characteristics, Spliterator
from snakestream.stream import Stream


# --- spliterator() exposes the composed pipeline without consuming it ------


@pytest.mark.asyncio
async def test_spliterator_returns_without_consuming() -> None:
    pulled = []

    async def source():
        for i in [1, 2, 3]:
            pulled.append(i)
            yield i

    sp = Stream.of(source()).map(lambda x: x).spliterator()

    assert isinstance(sp, Spliterator)
    assert pulled == []


@pytest.mark.asyncio
async def test_traversing_a_spliterator_matches_collect() -> None:
    chain = lambda: Stream.of([1, 2, 3, 4]).map(lambda x: x * 2).filter(lambda x: x > 2)  # noqa: E731

    sp = chain().spliterator()
    seen = []
    await sp.for_each_remaining(seen.append)
    from_collect = await chain().collect(to_list())

    assert seen == from_collect == [4, 6, 8]


@pytest.mark.asyncio
async def test_spliterator_does_not_consume_or_mutate_chain() -> None:
    stream = Stream.of([1, 2, 3]).map(lambda x: x * 2)
    chain_len_before = len(stream._chain)

    stream.spliterator()

    assert len(stream._chain) == chain_len_before


# --- try_advance -------------------------------------------------------


@pytest.mark.asyncio
async def test_try_advance_invokes_action_once_and_returns_true() -> None:
    sp = Stream.of([1, 2, 3]).spliterator()
    seen = []

    advanced = await sp.try_advance(seen.append)

    assert advanced is True
    assert seen == [1]


@pytest.mark.asyncio
async def test_try_advance_on_exhausted_spliterator_returns_false() -> None:
    sp = Stream.of([]).spliterator()
    seen = []

    advanced = await sp.try_advance(seen.append)

    assert advanced is False
    assert seen == []


@pytest.mark.asyncio
async def test_try_advance_accepts_an_async_action() -> None:
    sp = Stream.of([1]).spliterator()
    seen = []

    async def action(x):
        seen.append(x)

    advanced = await sp.try_advance(action)

    assert advanced is True
    assert seen == [1]


@pytest.mark.asyncio
async def test_try_advance_on_an_unsized_source_leaves_size_unknown() -> None:
    async def gen():
        yield 1
        yield 2

    sp = Stream.of(gen()).spliterator()
    seen = []

    advanced = await sp.try_advance(seen.append)

    assert advanced is True
    assert seen == [1]
    assert sp.estimate_size() is None


# --- try_split -----------------------------------------------------------


@pytest.mark.asyncio
async def test_a_split_covers_a_contiguous_prefix() -> None:
    sp = Stream.of(list(range(10))).spliterator()

    split = await sp.try_split()
    assert split is not None

    prefix = []
    await split.for_each_remaining(prefix.append)
    remainder = []
    await sp.for_each_remaining(remainder.append)

    assert prefix + remainder == list(range(10))
    assert not (set(prefix) & set(remainder))


@pytest.mark.asyncio
async def test_splits_and_the_remainder_reconstitute_the_stream() -> None:
    source = list(range(50))
    sp = Stream.of(source).spliterator()

    splits = []
    while (split := await sp.try_split()) is not None:
        splits.append(split)

    result = []
    for s in splits:
        await s.for_each_remaining(result.append)
    await sp.for_each_remaining(result.append)

    assert result == source


@pytest.mark.asyncio
async def test_splitting_terminates() -> None:
    sp = Stream.of(list(range(5))).spliterator()

    async def loop_until_none():
        count = 0
        while (await sp.try_split()) is not None:
            count += 1
            if count > 1000:  # pragma: no cover - only reached on a real hang
                raise AssertionError("try_split() never returned None")
        return count

    # a real hang here blocks the event loop forever, so bound it with a
    # timeout rather than trusting the loop guard alone to fail fast
    await asyncio.wait_for(loop_until_none(), timeout=5)


@pytest.mark.asyncio
async def test_a_split_stops_at_the_batch_size_leaving_a_remainder() -> None:
    source = list(range(BATCH_SIZE + 5))
    sp = Stream.of(source).spliterator()

    split = await sp.try_split()

    assert split is not None
    assert split.estimate_size() == BATCH_SIZE
    assert sp.estimate_size() == 5


@pytest.mark.asyncio
async def test_an_unsized_source_is_split_by_draining_a_batch() -> None:
    async def gen():
        for i in range(5):
            yield i

    sp = Stream.of(gen()).spliterator()

    split = await sp.try_split()

    assert split is not None
    drained = []
    await split.for_each_remaining(drained.append)
    assert drained == [0, 1, 2, 3, 4]
    # the batch drained everything an unsized generator had, so nothing
    # remains on the original spliterator
    assert await sp.try_advance(lambda _: None) is False


# --- estimate_size ---------------------------------------------------------


@pytest.mark.asyncio
async def test_a_sized_source_reports_its_length_without_pulling() -> None:
    sp = Stream.of([1, 2, 3]).spliterator()

    assert sp.estimate_size() == 3


@pytest.mark.asyncio
async def test_an_unsized_source_reports_the_unknown_value() -> None:
    async def gen():
        yield 1
        yield 2

    sp = Stream.of(gen()).spliterator()

    assert sp.estimate_size() is None


@pytest.mark.asyncio
async def test_a_cardinality_changing_op_clears_the_size_hint() -> None:
    sp = Stream.of([1, 2, 3, 4]).filter(lambda x: x % 2 == 0).spliterator()

    assert sp.estimate_size() is None


# --- characteristics ---------------------------------------------------


@pytest.mark.asyncio
async def test_an_ordered_streams_spliterator_reports_ordered() -> None:
    sp = Stream.of([1, 2, 3]).spliterator()

    assert Characteristics.ORDERED in sp.characteristics()


@pytest.mark.asyncio
async def test_an_unordered_streams_spliterator_does_not_report_ordered() -> None:
    sp = Stream.of([1, 2, 3]).unordered().spliterator()

    assert Characteristics.ORDERED not in sp.characteristics()


@pytest.mark.asyncio
async def test_a_split_reports_characteristics_consistent_with_its_parent() -> None:
    sp = Stream.of(list(range(10))).spliterator()
    parent_characteristics = sp.characteristics()

    split = await sp.try_split()

    assert split is not None
    assert split.characteristics() == parent_characteristics


@pytest.mark.asyncio
async def test_an_unsized_streams_spliterator_does_not_report_sized() -> None:
    async def gen():
        yield 1

    sp = Stream.of(gen()).spliterator()

    assert Characteristics.SIZED not in sp.characteristics()


# --- for_each_remaining --------------------------------------------------


@pytest.mark.asyncio
async def test_for_each_remaining_consumes_only_what_is_left() -> None:
    sp = Stream.of([1, 2, 3, 4]).spliterator()
    first = []
    await sp.try_advance(first.append)

    rest = []
    await sp.for_each_remaining(rest.append)

    assert first == [1]
    assert rest == [2, 3, 4]
    assert await sp.try_advance(lambda _: None) is False


@pytest.mark.asyncio
async def test_for_each_remaining_accepts_an_async_action() -> None:
    sp = Stream.of([1, 2, 3]).spliterator()
    seen = []

    async def action(x):
        seen.append(x)

    await sp.for_each_remaining(action)

    assert seen == [1, 2, 3]


@pytest.mark.asyncio
async def test_for_each_remaining_awaits_a_plain_def_returning_a_coroutine() -> None:
    # is_async_callable() classifies a plain `def` as sync even when it
    # returns a coroutine (an async-def __call__ is the case it does catch);
    # the one-time isawaitable() safety net inside for_each_remaining's loop
    # is what still awaits it, matching callable_dispatch.py's canonical shape
    sp = Stream.of([1, 2, 3]).spliterator()
    seen = []

    async def _record(x):
        seen.append(x)

    def action(x):
        return _record(x)

    await sp.for_each_remaining(action)

    assert seen == [1, 2, 3]

    assert seen == [1, 2, 3]

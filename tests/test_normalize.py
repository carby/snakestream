# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

import pytest

from snakestream import Stream
from snakestream.collectors import to_list


class NextOnlyIterator:
    """A sync iterator implementing only __next__ -- deliberately no __iter__,
    so `for i in source` would raise TypeError and only next() can drive it."""

    def __init__(self, values):
        self.values = list(values)
        self.pulled = 0

    def __next__(self):
        if self.pulled >= len(self.values):
            raise StopIteration
        value = self.values[self.pulled]
        self.pulled += 1
        return value


def test_next_only_iterator_really_has_no_iter() -> None:
    # guards the tests below from silently drifting onto the __iter__ path
    source = NextOnlyIterator([1, 2, 3])

    assert hasattr(source, "__next__")
    assert not hasattr(source, "__iter__")


@pytest.mark.asyncio
async def test_next_only_source_spreads_into_elements() -> None:
    # when
    it = await Stream(NextOnlyIterator([1, 2, 3])).collect(to_list())

    # then
    assert it == [1, 2, 3]


@pytest.mark.asyncio
async def test_exhausted_next_only_source_yields_nothing() -> None:
    # given a source that raises StopIteration on its very first advance
    source = NextOnlyIterator([])

    # when
    it = await Stream(source).collect(to_list())

    # then
    assert it == []


@pytest.mark.asyncio
async def test_next_only_source_composes_through_intermediate_ops() -> None:
    # given
    values = [1, 2, 3, 4, 5]

    # when
    from_iterator = await Stream(NextOnlyIterator(values)).map(lambda x: x * 2).filter(lambda x: x > 4).collect(to_list())
    from_list = await Stream(values).map(lambda x: x * 2).filter(lambda x: x > 4).collect(to_list())

    # then
    assert from_iterator == from_list == [6, 8, 10]


@pytest.mark.asyncio
async def test_next_only_source_is_consumed_lazily() -> None:
    # given
    source = NextOnlyIterator([1, 2, 3, 4, 5])

    # when
    it = await Stream(source).limit(2).collect(to_list())

    # then the source was advanced only as far as limit(2) needed, not drained
    assert it == [1, 2]
    assert source.pulled == 2


@pytest.mark.asyncio
async def test_plain_iterable_still_takes_the_iter_path() -> None:
    # a list is iterable but not an iterator -- next(list) is a TypeError, so
    # this pins that the __iter__ arm still handles it
    assert not hasattr([1, 2, 3], "__next__")

    # when
    it = await Stream([1, 2, 3]).collect(to_list())

    # then
    assert it == [1, 2, 3]


@pytest.mark.asyncio
async def test_scalar_with_neither_dunder_is_one_element() -> None:
    # given
    scalar = object()

    # when
    it = await Stream(scalar).collect(to_list())

    # then
    assert it == [scalar]


class FalsyAsyncIterable:
    """An async iterable that is falsy -- __len__ returning 0 makes bool() of
    it False, which a truthiness test in Stream.__init__ would read as "not an
    async source" and silently divert onto the scalar path."""

    def __init__(self, values):
        self.values = iter(values)

    def __len__(self):
        return 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.values)
        except StopIteration:
            raise StopAsyncIteration from None


def test_falsy_async_iterable_really_is_falsy() -> None:
    # guards the test below from passing for the wrong reason
    assert not bool(FalsyAsyncIterable([1, 2, 3]))


@pytest.mark.asyncio
async def test_falsy_async_source_is_still_iterated() -> None:
    # given
    source = FalsyAsyncIterable([1, 2, 3])

    # when
    it = await Stream(source).collect(to_list())

    # then
    assert it == [1, 2, 3]


def test_falsy_async_source_is_not_sized() -> None:
    # _estimate_size() asks isinstance, not _accept(): a falsy AsyncIterable
    # is an async source and so reports no size hint, and its __len__ of 0 is
    # never read
    assert Stream(FalsyAsyncIterable([1, 2, 3]))._size_hint is None


def test_stream_source_is_composed_exactly_once(monkeypatch) -> None:
    # _accept() unwraps a Stream source by composing it (iterator()), so any
    # caller treating _accept() as a predicate would compose a second time and
    # throw the result away -- _estimate_size() asks isinstance for that reason
    compositions = []
    original = Stream.iterator

    def counting_iterator(self):
        compositions.append(self)
        return original(self)

    monkeypatch.setattr(Stream, "iterator", counting_iterator)

    # when
    Stream(Stream([1, 2, 3]))

    # then
    assert len(compositions) == 1

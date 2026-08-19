"""Covers the terminal-sinks capability: terminals driven as TerminalSinks,
short-circuiting terminals requesting cancellation upstream, the ordered drive,
and terminals on a ParallelStream."""

import asyncio

import pytest

from snakestream import Stream


# --- reduce() edge cases the push rewrite could silently change -------------


@pytest.mark.asyncio
async def test_reduce_no_identity_empty_stream_returns_none() -> None:
    # when
    it = await Stream.of([]).reduce(lambda a, b: a + b)

    # then
    assert it is None


@pytest.mark.asyncio
async def test_reduce_no_identity_single_element_never_calls_accumulator() -> None:
    # given
    calls = []

    def accumulator(a, b):
        calls.append((a, b))
        return a + b

    # when
    it = await Stream.of([7]).reduce(accumulator)

    # then: the lone element seeds the fold and is returned as-is
    assert it == 7
    assert calls == []


@pytest.mark.asyncio
async def test_reduce_with_identity_empty_stream_returns_identity() -> None:
    # when
    it = await Stream.of([]).reduce(42, lambda a, b: a + b)

    # then
    assert it == 42


@pytest.mark.asyncio
async def test_reduce_with_falsy_identity_is_not_mistaken_for_unseeded() -> None:
    # when
    it = await Stream.of([1, 2, 3]).reduce(0, lambda a, b: a + b)

    # then
    assert it == 6


@pytest.mark.asyncio
async def test_reduce_no_identity_async_accumulator() -> None:
    # given
    async def accumulator(a, b):
        await asyncio.sleep(0)
        return a + b

    # when
    it = await Stream.of([1, 2, 3, 4]).reduce(accumulator)

    # then
    assert it == 10


# --- cancellation originating at a terminal --------------------------------


@pytest.mark.asyncio
async def test_any_match_stops_pulling_after_the_match() -> None:
    # given
    seen = []

    # when
    it = await Stream.of([1, 2, 3, 4]).peek(seen.append).any_match(lambda n: n == 1)

    # then
    assert it is True
    assert seen == [1]


@pytest.mark.asyncio
async def test_find_first_stops_pulling_after_the_first_element() -> None:
    # given
    seen = []

    # when
    it = await Stream.of([1, 2, 3, 4]).peek(seen.append).find_first()

    # then
    assert it == 1
    assert seen == [1]


@pytest.mark.asyncio
async def test_find_any_stops_pulling_after_the_first_element() -> None:
    # given
    seen = []

    # when
    it = await Stream.of([1, 2, 3, 4]).peek(seen.append).find_any()

    # then
    assert it == 1
    assert seen == [1]


@pytest.mark.asyncio
async def test_all_match_stops_pulling_at_the_first_failure() -> None:
    # given
    seen = []

    # when
    it = await Stream.of([1, 2, 3, 4]).peek(seen.append).all_match(lambda n: n < 2)

    # then
    assert it is False
    assert seen == [1, 2]


@pytest.mark.asyncio
async def test_none_match_stops_pulling_at_the_first_match() -> None:
    # given
    seen = []

    # when
    it = await Stream.of([1, 2, 3, 4]).peek(seen.append).none_match(lambda n: n == 2)

    # then
    assert it is False
    assert seen == [1, 2]


@pytest.mark.asyncio
async def test_non_short_circuiting_terminals_pull_everything() -> None:
    # given
    for_count = []
    for_each = []
    for_reduce = []
    for_min = []

    # when
    count = await Stream.of([1, 2, 3, 4]).peek(for_count.append).count()
    await Stream.of([1, 2, 3, 4]).peek(for_each.append).for_each(lambda n: None)
    await Stream.of([1, 2, 3, 4]).peek(for_reduce.append).reduce(0, lambda a, b: a + b)
    await Stream.of([1, 2, 3, 4]).peek(for_min.append).min(lambda a, b: a - b)

    # then
    assert count == 4
    assert for_count == [1, 2, 3, 4]
    assert for_each == [1, 2, 3, 4]
    assert for_reduce == [1, 2, 3, 4]
    assert for_min == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_short_circuiting_terminal_still_runs_end_on_a_buffering_op() -> None:
    # given: sorted() emits everything from end(), so a terminal that cancels
    # during that flush must still have end() propagate through the chain
    seen = []

    # when
    it = await Stream.of([4, 1, 3, 2]).sorted().peek(seen.append).find_first()

    # then
    assert it == 1
    assert seen == [1]


# --- cancellation reaching flat_map's inner loop ---------------------------


@pytest.mark.asyncio
async def test_any_match_stops_flat_map_mid_expansion() -> None:
    # given
    cleaned_up = []

    async def tracked_inner(n: int):
        try:
            for i in range(n):
                yield i
        finally:
            cleaned_up.append(n)

    def mapper(n: int) -> Stream:
        return Stream(tracked_inner(n))

    # when
    it = await Stream.of([5]).flat_map(mapper).any_match(lambda n: n == 0)

    # then: the answer is settled on the inner stream's first element, and the
    # abandoned inner generator is closed
    assert it is True
    assert cleaned_up == [5]


@pytest.mark.asyncio
async def test_find_first_takes_exactly_one_inner_element() -> None:
    # given
    seen = []
    cleaned_up = []

    async def tracked_inner(n: int):
        try:
            for i in range(n):
                seen.append((n, i))
                yield i
        finally:
            cleaned_up.append(n)

    def mapper(n: int) -> Stream:
        return Stream(tracked_inner(n))

    # when
    it = await Stream.of([5, 6]).flat_map(mapper).find_first()

    # then: one element out of the first inner stream, no second outer element
    assert it == 0
    assert seen == [(5, 0)]
    assert cleaned_up == [5]


# --- the ordered drive -----------------------------------------------------

# Same jumbled-source-with-positional-delay setup as tests/test_find_first.py
# and tests/test_for_each_ordered.py.
values = [4, 1, 7, 2, 8, 3, 6, 5]
delay_by_position = {value: (len(values) - position) * 0.02 for position, value in enumerate(values)}


async def _delay_by_position(n: int) -> int:
    await asyncio.sleep(delay_by_position[n])
    return n


@pytest.mark.asyncio
async def test_for_each_ordered_stays_in_source_order_on_a_parallel_stream() -> None:
    # given
    seen = []

    # when
    await Stream.of(values).parallel().map(_delay_by_position).for_each_ordered(seen.append)

    # then
    assert seen == values


@pytest.mark.asyncio
async def test_ordered_parallel_find_first_returns_the_true_first_element() -> None:
    # when: the first element carries the longest delay, so a racing drive
    # would surface a later one first
    it = await Stream.of(values).parallel().map(_delay_by_position).find_first()

    # then
    assert it == values[0]


@pytest.mark.asyncio
async def test_unordered_parallel_find_first_races() -> None:
    # when
    it = await Stream.of(values).parallel().unordered().map(_delay_by_position).find_first()

    # then: whatever arrives first, but not the longest-delayed first element
    assert it in values
    assert it != values[0]


# --- terminals on a ParallelStream -----------------------------------------


@pytest.mark.asyncio
async def test_parallel_count_matches_sequential() -> None:
    # when
    it = await Stream.of(list(range(50))).parallel().map(lambda n: n * 2).count()

    # then
    assert it == 50


@pytest.mark.asyncio
async def test_parallel_reduce_sees_every_element_once() -> None:
    # when
    it = await Stream.of(list(range(50))).parallel().reduce(0, lambda a, b: a + b)

    # then
    assert it == sum(range(50))


@pytest.mark.asyncio
async def test_parallel_for_each_sees_every_element_once() -> None:
    # given
    seen = []

    # when
    await Stream.of(list(range(50))).parallel().for_each(seen.append)

    # then
    assert sorted(seen) == list(range(50))


@pytest.mark.asyncio
async def test_parallel_any_match_short_circuits_and_tears_down_cleanly(recwarn) -> None:
    # given
    async def slow(n: int) -> int:
        await asyncio.sleep(0.01)
        return n

    # when
    it = await Stream.of(list(range(50))).parallel().map(slow).any_match(lambda n: n >= 0)

    # then: settled on the first arrival, with the abandoned racing branches
    # cancelled and gathered rather than left to warn
    assert it is True
    await asyncio.sleep(0.05)
    assert [w for w in recwarn if issubclass(w.category, RuntimeWarning)] == []


@pytest.mark.asyncio
async def test_parallel_min_max_match_sequential() -> None:
    # given
    def comparator(a, b):
        return a - b

    # when
    smallest = await Stream.of([4, 1, 7, 2]).parallel().min(comparator)
    largest = await Stream.of([4, 1, 7, 2]).parallel().max(comparator)

    # then
    assert smallest == 1
    assert largest == 7


# --- consumed-stream checks still fire -------------------------------------


@pytest.mark.asyncio
async def test_terminals_still_reject_a_superseded_stream() -> None:
    from snakestream.exception import IllegalStateException

    # given
    stream = Stream.of([1, 2, 3])
    stream.map(lambda n: n)

    # when / then
    with pytest.raises(IllegalStateException):
        await stream.count()


# --- the short-circuit guards, exercised directly ---------------------------
#
# Every op that pushes more than once without returning to the driving loop
# (sorted, flat_map) checks cancellation between pushes, so nothing in the
# library currently pushes past a settled terminal. These guards keep the
# terminals correct on their own rather than resting on that invariant, so
# they are pinned directly.


@pytest.mark.asyncio
async def test_find_sink_keeps_the_first_element_if_pushed_past_cancellation() -> None:
    from snakestream.terminals import _FindSink

    # given
    sink = _FindSink()
    await sink.begin({})

    # when
    await sink.accept(1)
    assert sink.cancellation_requested() is True
    await sink.accept(2)
    await sink.end()

    # then
    assert sink.result() == 1


@pytest.mark.asyncio
async def test_match_sink_keeps_its_answer_if_pushed_past_cancellation() -> None:
    from snakestream.terminals import _MatchSink

    # given
    calls = []

    def predicate(n):
        calls.append(n)
        return n > 0

    sink = _MatchSink(predicate, short_circuit_on=True, default=False)
    await sink.begin({})

    # when
    await sink.accept(1)
    assert sink.cancellation_requested() is True
    await sink.accept(-1)
    await sink.end()

    # then: the answer stands and the predicate never ran a second time
    assert sink.result() is True
    assert calls == [1]

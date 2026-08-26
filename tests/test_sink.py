import pytest

from snakestream.sink import (
    Box,
    GeneratorBridgeSink,
    IntermediateSink,
    Op,
    StatefulOp,
    StatefulSink,
    StatelessOp,
    TerminalSink,
)


class _RecordingTerminalSink(TerminalSink):
    def _create_container(self) -> list:
        return []

    async def accept(self, element) -> None:
        self._container.append(element)


class _CountingOp(Op):
    """A stateful op: shares a [begin_count, end_count] pair via the state
    map so tests can assert lifecycle ordering across a chain."""

    def __init__(self, log: list) -> None:
        self._log = log

    def link(self, downstream):
        return _CountingSink(downstream, self, self._log)


class _CountingSink(IntermediateSink):
    def __init__(self, downstream, op, log: list) -> None:
        super().__init__(downstream)
        self._op = op
        self._log = log

    async def begin(self, state_map) -> None:
        self._log.append(("begin", self._op))
        await super().begin(state_map)

    async def accept(self, element) -> None:
        self._log.append(("accept", self._op, element))
        await self.downstream.accept(element)

    async def end(self) -> None:
        self._log.append(("end", self._op))
        await super().end()


class _PassThroughOp(Op):
    def link(self, downstream):
        return _PassThroughSink(downstream)


class _PassThroughSink(IntermediateSink):
    async def accept(self, element) -> None:
        await self.downstream.accept(element)


class _DoublingFlatSink(IntermediateSink):
    """Pushes zero, one, or many elements per accept, depending on value."""

    async def accept(self, element) -> None:
        if element == "skip":
            return
        if isinstance(element, list):
            for e in element:
                await self.downstream.accept(e)
            return
        await self.downstream.accept(element)


class _BufferingSink(IntermediateSink):
    """Pushes nothing from accept(); pushes everything from end()."""

    def __init__(self, downstream) -> None:
        super().__init__(downstream)
        self._buffer: list = []

    async def accept(self, element) -> None:
        self._buffer.append(element)

    async def end(self) -> None:
        for e in self._buffer:
            await self.downstream.accept(e)
        await super().end()


class _TallyingOp(Op):
    def make_shared_state(self) -> list:
        return [0]

    def link(self, downstream):
        return _TallyingSink(downstream, self)


class _TallyingSink(IntermediateSink):
    def __init__(self, downstream, op) -> None:
        super().__init__(downstream)
        self._op = op
        self._state: list | None = None

    async def begin(self, state_map) -> None:
        self._state = state_map.get(self._op, [0])
        await super().begin(state_map)

    async def accept(self, element) -> None:
        self._state[0] += 1
        await self.downstream.accept(element)


class _CappingOp(Op):
    def __init__(self, cap: int) -> None:
        self._cap = cap

    def link(self, downstream):
        return _CappingSink(downstream, self._cap)


class _CappingSink(IntermediateSink):
    def __init__(self, downstream, cap: int) -> None:
        super().__init__(downstream)
        self._cap = cap
        self._count = 0
        self._cancelled = False

    async def accept(self, element) -> None:
        if self._count >= self._cap:
            self._cancelled = True
            return
        self._count += 1
        if self._count >= self._cap:
            self._cancelled = True
        await self.downstream.accept(element)

    def cancellation_requested(self) -> bool:
        return self._cancelled or super().cancellation_requested()


async def _drive(head, source, state_map=None) -> None:
    await head.begin(state_map if state_map is not None else {})
    # mirrors _copy_into(): a chain already cancelled at begin() must
    # not be given a single element
    if not head.cancellation_requested():
        for item in source:
            await head.accept(item)
            if head.cancellation_requested():
                break
    await head.end()


# --- Lifecycle ordering -----------------------------------------------------


@pytest.mark.asyncio
async def test_begin_and_end_propagate_exactly_once_through_the_chain() -> None:
    log: list = []
    ops = [_CountingOp(log), _CountingOp(log), _CountingOp(log)]
    terminal = _RecordingTerminalSink()
    head = terminal
    for op in reversed(ops):
        head = op.link(head)

    await _drive(head, [1, 2, 3])

    begins = [e for e in log if e[0] == "begin"]
    ends = [e for e in log if e[0] == "end"]
    assert len(begins) == 3
    assert len(ends) == 3
    assert {op for _, op in begins} == set(ops)
    assert {op for _, op in ends} == set(ops)
    assert terminal.result() == [1, 2, 3]


@pytest.mark.asyncio
async def test_begin_precedes_every_accept_and_end_follows_every_accept() -> None:
    log: list = []
    op = _CountingOp(log)
    head = op.link(_RecordingTerminalSink())

    await _drive(head, [1, 2, 3])

    assert log[0][0] == "begin"
    assert log[-1][0] == "end"
    accepts = [e for e in log if e[0] == "accept"]
    assert [e[2] for e in accepts] == [1, 2, 3]


@pytest.mark.asyncio
async def test_begin_and_end_still_run_on_empty_source() -> None:
    log: list = []
    op = _CountingOp(log)
    head = op.link(_RecordingTerminalSink())

    await _drive(head, [])

    assert [e[0] for e in log] == ["begin", "end"]


# --- Zero / one / many pushes per accept, and pushing from end() -----------


@pytest.mark.asyncio
async def test_a_sink_may_push_zero_one_or_many_elements_per_accept() -> None:
    terminal = _RecordingTerminalSink()
    head = _DoublingFlatSink(terminal)

    await _drive(head, ["skip", "a", ["b", "c"]])

    assert terminal.result() == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_a_sink_may_push_elements_from_end_rather_than_accept() -> None:
    terminal = _RecordingTerminalSink()
    head = _BufferingSink(terminal)

    await _drive(head, [1, 2, 3])

    assert terminal.result() == [1, 2, 3]


# --- Shared state via begin(state_map) --------------------------------------


@pytest.mark.asyncio
async def test_stateful_sink_uses_state_supplied_in_the_map() -> None:
    op = _TallyingOp()
    sink = op.link(_RecordingTerminalSink())
    shared = [10]
    state_map = {op: shared}

    await _drive(sink, [1, 2], state_map)

    assert shared == [12]


@pytest.mark.asyncio
async def test_stateful_sink_falls_back_to_fresh_local_state() -> None:
    op = _TallyingOp()
    sink = op.link(_RecordingTerminalSink())

    # no entry for op in the state map
    await _drive(sink, [1, 2], {})

    assert sink._state == [2]


@pytest.mark.asyncio
async def test_two_chains_from_one_op_share_one_state_instance_via_shared_map() -> None:
    op = _TallyingOp()
    state_map = {op: op.make_shared_state()}
    sink_a = op.link(_RecordingTerminalSink())
    sink_b = op.link(_RecordingTerminalSink())

    await _drive(sink_a, [1], state_map)
    await _drive(sink_b, [1, 1], state_map)

    assert state_map[op] == [3]


# --- The StatefulOp/StatefulSink bases --------------------------------------


class _CountingStatefulSink(StatefulSink):
    async def accept(self, element) -> None:
        self._state.value += 1
        await self.downstream.accept(element)


class _CountingStatefulOp(StatefulOp):
    _sink_cls = _CountingStatefulSink

    def make_shared_state(self) -> Box:
        return Box(0)


@pytest.mark.asyncio
async def test_fallback_state_comes_from_the_ops_own_factory() -> None:
    op = _CountingStatefulOp()
    sink = op.link(_RecordingTerminalSink())

    # no entry for op in the state map
    await _drive(sink, [1, 2], {})

    fresh = op.make_shared_state()
    assert type(sink._state) is type(fresh)
    assert sink._state.value == 2

    # ...and the fallback is this sink's own, not shared with any other
    other = op.link(_RecordingTerminalSink())
    await _drive(other, [1], {})
    assert other._state is not sink._state
    assert sink._state.value == 2


@pytest.mark.asyncio
async def test_stateful_base_sink_uses_the_state_supplied_in_the_map() -> None:
    op = _CountingStatefulOp()
    sink = op.link(_RecordingTerminalSink())
    shared = Box(10)

    await _drive(sink, [1, 2], {op: shared})

    assert sink._state is shared
    assert shared.value == 12


@pytest.mark.asyncio
async def test_two_stateful_base_sinks_from_one_op_share_one_counter() -> None:
    op = _CountingStatefulOp()
    state_map = {op: op.make_shared_state()}
    sink_a = op.link(_RecordingTerminalSink())
    sink_b = op.link(_RecordingTerminalSink())

    await _drive(sink_a, [1], state_map)
    await _drive(sink_b, [1, 1], state_map)

    assert state_map[op].value == 3


def test_box_holds_the_value_it_is_given_and_instances_are_independent() -> None:
    first = Box(0)
    second = Box(0)

    assert first.value == 0
    assert second.value == 0

    first.value += 1

    assert first.value == 1
    assert second.value == 0
    assert Box(7).value == 7


def test_stateless_op_hands_its_args_to_its_sink() -> None:
    class _ArgsSink(IntermediateSink):
        def __init__(self, downstream, *args) -> None:
            super().__init__(downstream)
            self.args = args

        async def accept(self, element) -> None:
            await self.downstream.accept(element)

    class _ArgsOp(StatelessOp):
        _sink_cls = _ArgsSink

    terminal = _RecordingTerminalSink()
    sink = _ArgsOp("a", 2).link(terminal)

    assert sink.args == ("a", 2)
    assert sink.downstream is terminal
    assert _ArgsOp("a", 2).make_shared_state() is None


def test_stateful_op_hands_itself_then_its_args_to_its_sink() -> None:
    class _ArgsSink(StatefulSink):
        def __init__(self, downstream, op, *args) -> None:
            super().__init__(downstream, op)
            self.args = args

        async def accept(self, element) -> None:
            await self.downstream.accept(element)

    class _ArgsOp(StatefulOp):
        _sink_cls = _ArgsSink

        def make_shared_state(self) -> Box:
            return Box(0)

    op = _ArgsOp("a", 2)
    sink = op.link(_RecordingTerminalSink())

    assert sink._op is op
    assert sink.args == ("a", 2)


# --- Cancellation -------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_from_a_mid_chain_sink_is_visible_at_the_head() -> None:
    terminal = _RecordingTerminalSink()
    capping = _CappingOp(2).link(terminal)
    head = _PassThroughSink(capping)

    await head.begin({})
    assert head.cancellation_requested() is False
    await head.accept(1)
    assert head.cancellation_requested() is False
    await head.accept(2)
    assert head.cancellation_requested() is True


@pytest.mark.asyncio
async def test_driving_loop_stops_pulling_once_cancellation_is_requested() -> None:
    terminal = _RecordingTerminalSink()
    head = _CappingOp(2).link(terminal)
    pulled = []

    def source():
        for i in [1, 2, 3, 4, 5]:
            pulled.append(i)
            yield i

    await _drive(head, source())

    assert pulled == [1, 2]
    assert terminal.result() == [1, 2]


@pytest.mark.asyncio
async def test_end_still_runs_after_cancellation() -> None:
    log: list = []
    counting = _CountingOp(log)
    terminal = _RecordingTerminalSink()
    head = counting.link(_CappingOp(1).link(terminal))

    await _drive(head, [1, 2, 3])

    assert ("end", counting) in log


# --- Terminal sink result() -------------------------------------------------


@pytest.mark.asyncio
async def test_terminal_sink_yields_accumulated_result_after_end() -> None:
    terminal = _RecordingTerminalSink()
    await _drive(terminal, [1, 2, 3])
    assert terminal.result() == [1, 2, 3]


@pytest.mark.asyncio
async def test_terminal_sink_over_empty_source_returns_empty_container() -> None:
    terminal = _RecordingTerminalSink()
    await _drive(terminal, [])
    assert terminal.result() == []


# --- Generator bridge ---------------------------------------------------


@pytest.mark.asyncio
async def test_generator_bridge_buffers_and_is_cleared_in_place() -> None:
    # the driving loop reads .buffer and clears it in place rather than being
    # handed a fresh list per element
    bridge = GeneratorBridgeSink()
    await bridge.begin({})
    await bridge.accept(1)
    await bridge.accept(2)
    assert bridge.buffer == [1, 2]
    bridge.buffer.clear()
    assert bridge.buffer == []
    await bridge.accept(3)
    await bridge.end()
    assert bridge.buffer == [3]


@pytest.mark.asyncio
async def test_generator_bridge_buffer_identity_is_stable_across_clears() -> None:
    # clearing in place must not rebind the buffer: the driving loop holds the
    # bridge, not the list, but accept() appends to whatever _container is
    bridge = GeneratorBridgeSink()
    await bridge.begin({})
    held = bridge.buffer
    await bridge.accept(1)
    bridge.buffer.clear()
    await bridge.accept(2)
    assert held is bridge.buffer
    assert bridge.buffer == [2]


@pytest.mark.asyncio
async def test_generator_bridge_begin_gives_a_fresh_buffer() -> None:
    # a second composition must not see the first's leftovers
    bridge = GeneratorBridgeSink()
    await bridge.begin({})
    await bridge.accept(1)
    await bridge.begin({})
    assert bridge.buffer == []


@pytest.mark.asyncio
async def test_generator_bridge_over_empty_source() -> None:
    bridge = GeneratorBridgeSink()
    await bridge.begin({})
    await bridge.end()
    assert bridge.buffer == []


# --- Short-circuiting terminal sink -----------------------------------------


class _FirstOnlyTerminalSink(TerminalSink):
    """A terminal whose answer is settled by the first element: it reports
    cancellation from that point on."""

    def __init__(self) -> None:
        super().__init__()
        self._cancelled = False

    def _create_container(self) -> None:
        return None

    async def accept(self, element) -> None:
        if self._cancelled:
            return
        self._container = element
        self._cancelled = True

    def cancellation_requested(self) -> bool:
        return self._cancelled


@pytest.mark.asyncio
async def test_terminal_cancellation_is_visible_at_the_head_of_a_chain() -> None:
    terminal = _FirstOnlyTerminalSink()
    head = _PassThroughOp().link(_PassThroughOp().link(terminal))

    assert head.cancellation_requested() is False
    await head.begin({})
    await head.accept(1)

    assert head.cancellation_requested() is True


@pytest.mark.asyncio
async def test_terminal_cancellation_stops_the_driving_loop_and_still_finishes() -> None:
    terminal = _FirstOnlyTerminalSink()
    log: list = []
    counting = _CountingOp(log)
    head = counting.link(_PassThroughOp().link(terminal))
    pulled = []

    def source():
        for i in [1, 2, 3]:
            pulled.append(i)
            yield i

    await _drive(head, source())

    assert pulled == [1]
    assert ("end", counting) in log
    assert terminal.result() == 1


class _CancelledFromBeginOp(Op):
    """An op whose sink is cancelled from the moment it begins - the shape
    limit(0) has."""

    def link(self, downstream):
        return _CancelledFromBeginSink(downstream)


class _CancelledFromBeginSink(IntermediateSink):
    def __init__(self, downstream) -> None:
        super().__init__(downstream)
        self.accepted: list = []

    async def accept(self, element) -> None:
        self.accepted.append(element)
        await self.downstream.accept(element)

    def cancellation_requested(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_a_chain_cancelled_at_begin_is_given_no_elements_but_still_ends() -> None:
    # given a chain whose head reports cancellation immediately after begin()
    log: list = []
    counting = _CountingOp(log)
    terminal = _RecordingTerminalSink()
    head = _CancelledFromBeginOp().link(counting.link(terminal))
    pulled = []

    def source():
        for i in [1, 2, 3]:
            pulled.append(i)
            yield i

    # when
    await _drive(head, source())

    # then: nothing was pulled and no accept() ran anywhere in the chain
    assert pulled == []
    assert terminal.result() == []
    assert [entry for entry in log if entry[0] == "accept"] == []
    # but the lifecycle still completed
    assert ("begin", counting) in log
    assert ("end", counting) in log


@pytest.mark.asyncio
async def test_real_driving_loop_honours_cancellation_reported_at_begin() -> None:
    # given: the same shape driven by the real _copy_into() rather than by
    # this module's test double
    from snakestream.collectors import to_list
    from snakestream.stream import Stream

    pulled = []

    def source():
        for i in [1, 2, 3]:
            pulled.append(i)
            yield i

    stream = Stream.of(source())
    stream._chain = [_CancelledFromBeginOp()]

    # when
    result = await stream.collect(to_list())

    # then
    assert result == []
    assert pulled == []

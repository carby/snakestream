import pytest

from snakestream.sink import GeneratorBridgeSink, IntermediateSink, Op, TerminalSink


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


class _StatefulOp(Op):
    def make_shared_state(self) -> list:
        return [0]

    def link(self, downstream):
        return _StatefulSink(downstream, self)


class _StatefulSink(IntermediateSink):
    def __init__(self, downstream, op) -> None:
        super().__init__(downstream)
        self._op = op
        self._state: list | None = None

    async def begin(self, state_map) -> None:
        self._state = state_map[self._op] if self._op in state_map else [0]
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
    op = _StatefulOp()
    sink = op.link(_RecordingTerminalSink())
    shared = [10]
    state_map = {op: shared}

    await _drive(sink, [1, 2], state_map)

    assert shared == [12]


@pytest.mark.asyncio
async def test_stateful_sink_falls_back_to_fresh_local_state() -> None:
    op = _StatefulOp()
    sink = op.link(_RecordingTerminalSink())

    # no entry for op in the state map
    await _drive(sink, [1, 2], {})

    assert sink._state == [2]


@pytest.mark.asyncio
async def test_two_chains_from_one_op_share_one_state_instance_via_shared_map() -> None:
    op = _StatefulOp()
    state_map = {op: op.make_shared_state()}
    sink_a = op.link(_RecordingTerminalSink())
    sink_b = op.link(_RecordingTerminalSink())

    await _drive(sink_a, [1], state_map)
    await _drive(sink_b, [1, 1], state_map)

    assert state_map[op] == [3]


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
async def test_generator_bridge_drain_and_result() -> None:
    bridge = GeneratorBridgeSink()
    await bridge.begin({})
    await bridge.accept(1)
    await bridge.accept(2)
    assert bridge.drain() == [1, 2]
    assert bridge.drain() == []
    await bridge.accept(3)
    await bridge.end()
    assert bridge.drain() == [3]


@pytest.mark.asyncio
async def test_generator_bridge_over_empty_source() -> None:
    bridge = GeneratorBridgeSink()
    await bridge.begin({})
    await bridge.end()
    assert bridge.drain() == []

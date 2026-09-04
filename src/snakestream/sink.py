"""The Op/Sink pair: an Op sits in a stream's chain and builds the Sink that
does the per-element work once it is linked into a chain. A Sink implements
one push protocol - begin(state_map), accept(element), end() - plus a
synchronous cancellation_requested() query a driving loop polls to stop
early. IntermediateSink, StatefulSink, TerminalSink and GeneratorBridgeSink
are the shapes that protocol comes in; ops.py builds one Op/Sink pair per
intermediate operation on top of them. The encounter-order vocabulary an Op's
ClassVars below declare themselves in lives in ordering.py."""

from __future__ import annotations

import re

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar
from collections.abc import Callable

from snakestream.callable_dispatch import maybe_await
from snakestream.ordering import Ordering
from snakestream.type import StateMap, T

# Sentinel for "no value yet": distinguishes an unseeded reduction/accumulation
# from one seeded with a legitimately falsy identity. Lives here rather than in
# terminals.py or collector.py because both need it and neither may import the
# other.
UNSET = object()


def unseeded(container: Any) -> Any:
    """The rule stated once: an accumulation that never saw an element
    finishes as None. A function rather than five inlined comparisons because
    it is the only mechanism that reaches both terminals.py's sinks (through
    UnseededSink below) and collectors.py's closures, which are dataclass
    boxes rather than sinks and so cannot share a base class with them - see
    design Decision 3 of collapse-unseeded-accumulation-rule."""
    return None if container is UNSET else container


@dataclass(slots=True)
class Box:
    """A mutable single-value box. Lets a fixed accumulator function rebind a
    scalar accumulation by mutating this in place, since it cannot rebind a
    local of its caller's."""

    value: Any = None


class Sink[T](ABC):
    """Push-based op protocol: begin(state_map) / accept(element) / end(),
    plus a synchronous cancellation_requested() query."""

    @abstractmethod
    async def begin(self, state_map: StateMap) -> None: ...

    @abstractmethod
    async def accept(self, element: T) -> None: ...

    @abstractmethod
    async def end(self) -> None: ...

    def cancellation_requested(self) -> bool:
        return False


class Op(ABC):
    """The op half of the op/sink pair: an intermediate operation as held in a
    stream's chain. It carries the arguments the user passed and builds the
    Sink that does the per-element work, once per sink chain it is linked into.

    Two pieces of protocol beyond link(), each with a default that most ops
    take unchanged:

    make_shared_state() returns one fresh instance of the state this op's sinks
    share when several chains are built from the same op list (see the
    parallel executor, execution.py), or None for a stateless op. None means
    "no shared state", so an op that does need state returns a container — a
    set, a list, a counter object — never None.

    ordering declares what this op does to encounter order. PRESERVE is right
    for every op that neither reorders nor imposes an order — filter, map,
    flat_map, peek, distinct, limit, skip — which is why it is the default and
    why only UnorderedOp and SortedOp state it. It is a ClassVar because it
    is a property of the operation, not of the arguments the user passed to it:
    every sort sets ordering, whatever comparator it was given.

    order_sensitive declares whether this op's *result* depends on where an
    element sits in the stream, where ordering says what the op does *to* the
    characteristic. limit, skip and distinct are the three that set it: which
    elements they select is a question about position, so on an ordered
    pipeline they cannot be answered by a racing branch that sees only its own
    share of the source. A sort needs no flag — it already declares
    Ordering.SET, and setting an order is itself a claim over the whole
    stream. Also a ClassVar, and for the same reason as ordering."""

    ordering: ClassVar[Ordering] = Ordering.PRESERVE
    order_sensitive: ClassVar[bool] = False

    @abstractmethod
    def link(self, downstream: Sink[Any]) -> Sink[Any]: ...

    def make_shared_state(self) -> Any:
        return None

    def __repr__(self) -> str:
        """The operation's name as a caller wrote it: `FlatMapOp` -> flat_map.

        Derived from the class name rather than declared per op, so an op added
        later renders without anyone having to remember to name it. It lives
        here because it is a property of an Op; Stream.__repr__ knows only how
        to format a list of them. Does not strip a leading underscore: every
        Op subclass is bare per the internal-name-visibility rule, so an
        underscored one here would be violating that rule, and rendering it
        with the underscore is the correct failure - not something this
        should paper over."""
        name = type(self).__name__.removesuffix("Op")
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class _ArgsOp(Op):
    """Shared base for StatelessOp and StatefulOp: holds the arguments the op
    was constructed with and the sink class link() builds from them. Neither
    field expresses anything about shared state — that distinction is
    entirely in each subclass's link()."""

    _sink_cls: ClassVar[Callable[..., Sink[Any]]]

    def __init__(self, *args: Any) -> None:
        self._args = args


class StatelessOp(_ArgsOp):
    """An Op that holds the arguments it was constructed with and hands them to
    its sink class, in that order, after the downstream.

    Stateless here means no *shared* state — nothing that has to cross the
    parallel executor's concurrently-running batches. A sink may still buffer
    locally: `sorted` holds the whole stream in its sink and is still a
    StatelessOp, because that buffer belongs to one sink and is never shared
    with another."""

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return self._sink_cls(downstream, *self._args)


class StatefulOp(_ArgsOp):
    """An Op whose sinks share state across the chains built from it (see the
    parallel executor). Like StatelessOp, but link() passes the op itself as
    the sink's second argument, so the sink can key the state map by it.

    A subclass sets _sink_cls and overrides make_shared_state() to declare what
    that state is — the only place that shape is stated, since StatefulSink
    also falls back to that factory when the map holds no entry."""

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return self._sink_cls(downstream, self, *self._args)


class IntermediateSink(Sink[T]):
    """Base for sinks that hold exactly one downstream sink and push results
    to it. begin()/end() propagate down the chain by default; a subclass that
    pushes elements from end() (e.g. a buffering sink) must push them before
    calling super().end()."""

    def __init__(self, downstream: Sink[Any]) -> None:
        self.downstream = downstream

    async def begin(self, state_map: StateMap) -> None:
        await self.downstream.begin(state_map)

    async def end(self) -> None:
        await self.downstream.end()

    def cancellation_requested(self) -> bool:
        return self.downstream.cancellation_requested()


class StatefulSink(IntermediateSink[T]):
    """Base for sinks whose state may be shared with the other sinks built from
    the same op. begin() resolves that state once: the entry the state map
    holds for this sink's op, or — when the map has none — a fresh instance
    from the op's own make_shared_state(), so shared and local state are always
    the same shape.

    self._state is only meaningful from begin() onwards, which the protocol
    guarantees runs before the first accept()."""

    def __init__(self, downstream: Sink[Any], op: Op) -> None:
        super().__init__(downstream)
        self._op = op
        self._state: Any = None

    async def begin(self, state_map: StateMap) -> None:
        shared = state_map.get(self._op)
        self._state = self._op.make_shared_state() if shared is None else shared
        await super().begin(state_map)


class TerminalSink(Sink[T]):
    """Base for sinks with no downstream: begin() creates an accumulation
    container, accept() accumulates into it, end() finishes it into the value
    exposed via result().

    _create_container() and _finish() may each return an awaitable instead of
    a value: begin() and end() route both through maybe_await. Three sites
    depend on this and read like a missing await until this contract is
    traced - CollectorSink._create_container() returns a possibly-async
    supplier's result un-awaited, and grouping_by()'s and partitioning_by()'s
    _finish are *sync* functions returning the un-awaited coroutine of
    _finish_groups().

    A terminal whose answer is settled before the source runs out may override
    cancellation_requested() to report True from that point on, exactly as a
    short-circuiting intermediate sink does. Sitting at the end of the chain,
    that report travels up through every IntermediateSink to the head, so the
    driving loop stops pulling. Such a sink still receives end(), and its
    result() is the value that was fixed at the point it cancelled."""

    def __init__(self) -> None:
        self._container: Any = None
        self._result: Any = None

    @abstractmethod
    def _create_container(self) -> Any: ...

    async def begin(self, state_map: StateMap) -> None:
        self._container = await maybe_await(self._create_container)

    def _finish(self, container: Any) -> Any:
        return container

    async def end(self) -> None:
        self._result = await maybe_await(self._finish, self._container)

    def result(self) -> Any:
        return self._result


class UnseededSink(TerminalSink[T]):
    """A terminal that starts with no value: _create_container() is UNSET and
    _finish() applies the rule unseeded() states. Not folded into
    TerminalSink's own default - see design Decision 1 of
    collapse-unseeded-accumulation-rule for why: most TerminalSink subclasses
    can never hold UNSET, and a universal default would assert the rule on
    all of them regardless."""

    def _create_container(self) -> Any:
        return UNSET

    def _finish(self, container: Any) -> Any:
        return unseeded(container)


class GeneratorBridgeSink(TerminalSink[T]):
    """Occupies the terminal seat so a pushed chain can be exposed as an
    AsyncGenerator: buffers pushed elements for the driving loop to yield.

    The driving loop reads `buffer` directly and clears it in place rather than
    calling a drain() that hands back a fresh list - that ran once per element,
    on the hot path. Clearing after the yields is safe because nothing can push
    into a bridge whose driving loop is suspended: that loop is the only thing
    driving accept(), and each batch's per-element chain has its own bridge
    (execution.py's _run_element())."""

    def __init__(self) -> None:
        super().__init__()
        # a plain attribute, not a property: the driving loop reads it twice
        # per element, and a descriptor call there would give back most of
        # what dropping the per-element allocation buys
        self.buffer: list[T] = []

    def _create_container(self) -> list[T]:
        self.buffer = []
        return self.buffer

    async def accept(self, element: T) -> None:
        self._container.append(element)

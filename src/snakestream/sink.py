"""The Op/Sink pair: an Op sits in a stream's chain and builds the Sink that
does the per-element work once it is linked into a chain. A Sink implements
one push protocol - begin(state_map), accept(element), end() - plus a
synchronous cancellation_requested() query a driving loop polls to stop
early. IntermediateSink, StatefulSink, TerminalSink and GeneratorBridgeSink
are the shapes that protocol comes in; ops.py builds one Op/Sink pair per
intermediate operation on top of them."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic
from collections.abc import Callable

from snakestream.callable_dispatch import _maybe_await
from snakestream.type import StateMap, T

# Sentinel for "no value yet": distinguishes an unseeded reduction/accumulation
# from one seeded with a legitimately falsy identity. Lives here rather than in
# terminals.py or collector.py because both need it and neither may import the
# other.
_UNSET = object()


class Box:
    """A mutable single-value box. Lets a fixed accumulator function rebind a
    scalar accumulation by mutating this in place, since it cannot rebind a
    local of its caller's."""

    __slots__ = ("value",)

    def __init__(self, value: Any = None) -> None:
        self.value = value


class Counter(Box):
    """A mutable integer box. An op's shared count travels through the state
    map as one of these, so every sink built from that op increments the same
    instance."""

    def __init__(self, value: int = 0) -> None:
        super().__init__(value)


class Sink(ABC, Generic[T]):
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

    make_shared_state() returns one fresh instance of the state this op's sinks
    share when several chains are built from the same op list (see
    RACING), or None for a stateless op. None means "no shared state",
    so an op that does need state returns a container — a set, a list, a
    counter object — never None."""

    @abstractmethod
    def link(self, downstream: Sink[Any]) -> Sink[Any]: ...

    def make_shared_state(self) -> Any:
        return None


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

    Stateless here means no *shared* state — nothing that has to cross
    RACING's racing branches. A sink may still buffer locally: `sorted`
    holds the whole stream in its sink and is still a StatelessOp, because that
    buffer belongs to one sink and is never shared with another."""

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return self._sink_cls(downstream, *self._args)


class StatefulOp(_ArgsOp):
    """An Op whose sinks share state across the chains built from it (see
    RACING). Like StatelessOp, but link() passes the op itself as the
    sink's second argument, so the sink can key the state map by it.

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
        self._container = await _maybe_await(self._create_container)

    def _finish(self, container: Any) -> Any:
        return container

    async def end(self) -> None:
        self._result = await _maybe_await(self._finish, self._container)

    def result(self) -> Any:
        return self._result


class GeneratorBridgeSink(TerminalSink[T]):
    """Occupies the terminal seat so a pushed chain can be exposed as an
    AsyncGenerator: buffers pushed elements for the driving loop to yield.

    The driving loop reads `buffer` directly and clears it in place rather than
    calling a drain() that hands back a fresh list - that ran once per element,
    on the hot path. Clearing after the yields is safe because nothing can push
    into a bridge whose driving loop is suspended: that loop is the only thing
    driving accept(), and each RACING branch has its own bridge."""

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

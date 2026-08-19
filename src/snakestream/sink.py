from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic

from snakestream.type import StateMap, T


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
    ParallelStream), or None for a stateless op. None means "no shared state",
    so an op that does need state returns a container — a set, a list, a
    counter object — never None."""

    @abstractmethod
    def link(self, downstream: Sink[Any]) -> Sink[Any]: ...

    def make_shared_state(self) -> Any:
        return None


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


class TerminalSink(Sink[T]):
    """Base for sinks with no downstream: begin() creates an accumulation
    container, accept() accumulates into it, end() finishes it into the value
    exposed via result()."""

    def __init__(self) -> None:
        self._container: Any = None
        self._result: Any = None

    @abstractmethod
    def _create_container(self) -> Any: ...

    async def begin(self, state_map: StateMap) -> None:
        self._container = self._create_container()

    def _finish(self, container: Any) -> Any:
        return container

    async def end(self) -> None:
        self._result = self._finish(self._container)

    def result(self) -> Any:
        return self._result


class GeneratorBridgeSink(TerminalSink[T]):
    """Occupies the terminal seat so a pushed chain can be exposed as an
    AsyncGenerator: buffers pushed elements for the driving loop to drain and
    yield."""

    def _create_container(self) -> list[T]:
        return []

    async def accept(self, element: T) -> None:
        self._container.append(element)

    def drain(self) -> list[T]:
        drained = self._container
        self._container = []
        return drained

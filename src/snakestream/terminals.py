from __future__ import annotations

from inspect import isawaitable
from typing import Any, cast
from collections.abc import Awaitable

from snakestream.callable_dispatch import AsyncDispatch
from snakestream.comparator import is_new_extremum
from snakestream.sink import TerminalSink, _UNSET
from snakestream.type import (
    T,
    Accumulator,
    Comparator,
    Consumer,
    Predicate,
)


class _CountSink(TerminalSink[T]):
    """A plain int, not a Box: this sink owns its container exclusively,
    so it can rebind it the way _ReduceSink rebinds its accumulation. The
    counting() collector genuinely needs the Box, because its
    accumulator is a free function that has to mutate a container it was
    handed."""

    def _create_container(self) -> int:
        return 0

    async def accept(self, element: Any) -> None:
        self._container += 1


class _ForEachSink(AsyncDispatch, TerminalSink[T]):
    def __init__(self, consumer: Consumer) -> None:
        super().__init__()
        self._init_dispatch(consumer)

    def _create_container(self) -> None:
        return None

    async def accept(self, element: Any) -> None:
        r = self._fn(element)
        if self._is_async:
            await cast("Awaitable[None]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                await r


class _ReduceSink(AsyncDispatch, TerminalSink[T]):
    """Folds every element into an accumulated value. An identity of _UNSET
    means the no-identity overload: the first element seeds the fold instead,
    and an empty source finishes as None.

    That seeding rule is implemented twice, here and in collector.py's
    reducing(), which is deliberate and measured rather than an oversight:
    routing Stream.reduce() through reducing() cost +70% per element, because
    the collector form reaches its callables through _classify_step and a
    supplier-made box where this sink has them inline on itself. Keep the two
    in step by hand - a change to the _UNSET-seed rule or the
    empty-finishes-as-None rule belongs in both. See the collapse-terminal-
    collector-duplication change for the figures."""

    def __init__(self, identity: Any, accumulator: Accumulator) -> None:
        super().__init__()
        self._identity = identity
        self._init_dispatch(accumulator)

    def _create_container(self) -> Any:
        return self._identity

    async def accept(self, element: Any) -> None:
        if self._container is _UNSET:
            self._container = element
            return
        r = self._fn(self._container, element)
        if self._is_async:
            r = await cast("Awaitable[Any]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                r = await r
        self._container = r

    def _finish(self, container: Any) -> Any:
        return None if container is _UNSET else container


class _MinMaxSink(AsyncDispatch, TerminalSink[T]):
    def __init__(self, comparator: Comparator, asc: bool) -> None:
        super().__init__()
        self._asc = asc
        self._init_dispatch(comparator)

    def _create_container(self) -> Any:
        return _UNSET

    async def accept(self, element: Any) -> None:
        if self._container is _UNSET:
            self._container = element
            return

        sign = self._fn(element, self._container)
        if self._is_async:
            sign = await cast("Awaitable[int]", sign)
        elif not self._checked:
            self._checked = True
            if isawaitable(sign):
                self._is_async = True
                sign = await sign
        if is_new_extremum(cast(int, sign), self._asc):
            self._container = element

    def _finish(self, container: Any) -> Any:
        return None if container is _UNSET else container


class _FindSink(TerminalSink[T]):
    """Keeps the first element it is given and asks the chain to stop. Backs
    both find_first() and find_any() on a sequential Stream, which are the same
    operation there: the drive is already in encounter order."""

    def __init__(self) -> None:
        super().__init__()
        self._cancelled = False

    def _create_container(self) -> Any:
        return _UNSET

    async def accept(self, element: Any) -> None:
        # Keep the first and ignore the rest: a sink that pushes from end()
        # (sorted) flushes its whole buffer in one go, so cancelling is not
        # enough to guarantee no further accept() lands here.
        if self._cancelled:
            return
        self._container = element
        self._cancelled = True

    def cancellation_requested(self) -> bool:
        return self._cancelled

    def _finish(self, container: Any) -> Any:
        return None if container is _UNSET else container


class _MatchSink(AsyncDispatch, TerminalSink[T]):
    """Backs all_match/any_match/none_match. short_circuit_on is the predicate
    result that settles the answer; default is the answer for a source that
    never produces it (including an empty one)."""

    def __init__(self, predicate: Predicate, short_circuit_on: bool, default: bool) -> None:
        super().__init__()
        self._short_circuit_on = short_circuit_on
        self._default = default
        self._init_dispatch(predicate)
        # short-circuit state, not dispatch state: it belongs to this sink
        self._cancelled = False

    def _create_container(self) -> bool:
        return self._default

    async def accept(self, element: Any) -> None:
        # Once settled the answer cannot change, and the predicate must not run
        # again: a sink pushing from end() can still deliver elements after
        # cancellation was requested.
        if self._cancelled:
            return
        r = self._fn(element)
        if self._is_async:
            r = await cast("Awaitable[bool]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                r = await r
        if bool(r) is self._short_circuit_on:
            self._container = self._short_circuit_on
            self._cancelled = True

    def cancellation_requested(self) -> bool:
        return self._cancelled

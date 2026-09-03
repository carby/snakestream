from __future__ import annotations

from inspect import isawaitable
from typing import Any, cast
from collections.abc import Awaitable

from snakestream.callable_dispatch import AsyncDispatch
from snakestream.comparator import is_new_extremum
from snakestream.sink import UNSET, TerminalSink, UnseededSink
from snakestream.type import (
    T,
    Accumulator,
    Comparator,
    Consumer,
    Predicate,
)


class CountSink(TerminalSink[T]):
    """A plain int, not a Box: this sink owns its container exclusively,
    so it can rebind it the way ReduceSink rebinds its accumulation. The
    counting() collector genuinely needs the Box, because its
    accumulator is a free function that has to mutate a container it was
    handed."""

    def _create_container(self) -> int:
        return 0

    async def accept(self, element: Any) -> None:
        self._container += 1


class ForEachSink(AsyncDispatch, TerminalSink[T]):
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


class ReduceSink(AsyncDispatch, UnseededSink[T]):
    """Folds every element into an accumulated value. An identity of UNSET
    means the no-identity overload: the first element seeds the fold instead,
    and an empty source finishes as None.

    The UNSET-seed rule is implemented twice, here and in collector.py's
    reducing(), which is deliberate and measured rather than an oversight:
    routing Stream.reduce() through reducing() cost +70% per element, because
    the collector form reaches its callables through classify_step and a
    supplier-made box where this sink has them inline on itself. Keep the two
    in step by hand - a change to that seed rule belongs in both. See the
    collapse-terminal-collector-duplication change for the figures."""

    def __init__(self, identity: Any, accumulator: Accumulator) -> None:
        super().__init__()
        self._identity = identity
        self._init_dispatch(accumulator)

    def _create_container(self) -> Any:
        return self._identity

    async def accept(self, element: Any) -> None:
        if self._container is UNSET:
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


class MinMaxSink(AsyncDispatch, UnseededSink[T]):
    def __init__(self, comparator: Comparator, asc: bool) -> None:
        super().__init__()
        self._asc = asc
        self._init_dispatch(comparator)

    async def accept(self, element: Any) -> None:
        if self._container is UNSET:
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


class FindSink(UnseededSink[T]):
    """Keeps the first element it is given and asks the chain to stop. Backs
    both find_first() and find_any() on a sequential Stream, which are the same
    operation there: the drive is already in encounter order."""

    def __init__(self) -> None:
        super().__init__()
        self._cancelled = False

    async def accept(self, element: Any) -> None:
        # Keep the first and ignore the rest. sink-protocol lets a settled
        # sink meet its no-corruption requirement either way - by being
        # guaranteed no further push, or by ignoring what arrives - and this
        # takes the second. It is belt-and-braces, not a gap being covered:
        # every op that pushes more than once without returning to the driving
        # loop already checks cancellation between pushes (_SortedSink.end(),
        # _FlatMapSink.accept()), so nothing in the library reaches this guard
        # today. Guarding here is what keeps that a property of the ops rather
        # than a correctness debt this sink is owed.
        if self._cancelled:
            return
        self._container = element
        self._cancelled = True

    def cancellation_requested(self) -> bool:
        return self._cancelled


class MatchSink(AsyncDispatch, TerminalSink[T]):
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
        # again. Same posture as FindSink.accept(), which carries the reasoning:
        # sink-protocol's second disjunct, taken as belt-and-braces rather than
        # to cover a push the ops layer actually makes.
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

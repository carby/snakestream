from __future__ import annotations

from inspect import isawaitable
from typing import Any, cast
from collections.abc import Awaitable

from snakestream.callable_dispatch import is_async_callable
from snakestream.sink import Counter, TerminalSink
from snakestream.sort import check_comparator_result_type
from snakestream.type import (
    T,
    Accumulator,
    BiConsumer,
    Comparator,
    Consumer,
    Predicate,
)


# Sentinel for "no value yet": distinguishes an unseeded reduction from one
# seeded with a legitimately falsy identity. Lives here rather than in
# stream.py because the sinks that need it may not import stream.py.
_UNSET = object()


class _CountSink(TerminalSink[T]):
    def _create_container(self) -> Counter:
        return Counter()

    async def accept(self, element: Any) -> None:
        self._container.value += 1

    def _finish(self, container: Counter) -> int:
        return container.value


class _ForEachSink(TerminalSink[T]):
    def __init__(self, consumer: Consumer) -> None:
        super().__init__()
        self._consumer = consumer
        self._is_async = is_async_callable(consumer)
        self._checked = False

    def _create_container(self) -> None:
        return None

    async def accept(self, element: Any) -> None:
        r = self._consumer(element)
        if self._is_async:
            await cast("Awaitable[None]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                await r

    def _finish(self, container: Any) -> None:
        return None


class _ReduceSink(TerminalSink[T]):
    """Folds every element into an accumulated value. An identity of _UNSET
    means the no-identity overload: the first element seeds the fold instead,
    and an empty source finishes as None."""

    def __init__(self, identity: Any, accumulator: Accumulator) -> None:
        super().__init__()
        self._identity = identity
        self._accumulator = accumulator
        self._is_async = is_async_callable(accumulator)
        self._checked = False

    def _create_container(self) -> Any:
        return self._identity

    async def accept(self, element: Any) -> None:
        if self._container is _UNSET:
            self._container = element
            return
        r = self._accumulator(self._container, element)
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


class _MinMaxSink(TerminalSink[T]):
    def __init__(self, comparator: Comparator, asc: bool) -> None:
        super().__init__()
        self._comparator = comparator
        self._asc = asc
        self._is_async = is_async_callable(comparator)
        self._checked = False

    def _create_container(self) -> Any:
        return _UNSET

    async def accept(self, element: Any) -> None:
        if self._container is _UNSET:
            self._container = element
            return

        # comparator(element, found): negative if element orders before found,
        # positive if after. found (the earlier element) is kept on a tie.
        sign = self._comparator(element, self._container)
        if self._is_async:
            sign = await cast("Awaitable[int]", sign)
        elif not self._checked:
            self._checked = True
            if isawaitable(sign):
                self._is_async = True
                sign = await sign
        sign = cast(int, sign)
        check_comparator_result_type(sign)

        if self._asc:
            is_new_extreme = sign < 0
        else:
            is_new_extreme = sign > 0
        if is_new_extreme:
            self._container = element

    def _finish(self, container: Any) -> Any:
        return None if container is _UNSET else container


class _MutableReductionSink(TerminalSink[T]):
    """collect(supplier, accumulator, combiner)'s terminal. The supplier is
    called once per composition by the caller, so this sink is handed the
    already-built container rather than building it itself."""

    def __init__(self, container: Any, accumulator: BiConsumer) -> None:
        super().__init__()
        self._supplied = container
        self._accumulator = accumulator
        self._is_async = is_async_callable(accumulator)
        self._checked = False

    def _create_container(self) -> Any:
        return self._supplied

    async def accept(self, element: Any) -> None:
        r = self._accumulator(self._container, element)
        if self._is_async:
            await cast("Awaitable[None]", r)
        elif not self._checked:
            self._checked = True
            if isawaitable(r):
                self._is_async = True
                await r


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


class _MatchSink(TerminalSink[T]):
    """Backs all_match/any_match/none_match. short_circuit_on is the predicate
    result that settles the answer; default is the answer for a source that
    never produces it (including an empty one)."""

    def __init__(self, predicate: Predicate, short_circuit_on: bool, default: bool) -> None:
        super().__init__()
        self._predicate = predicate
        self._short_circuit_on = short_circuit_on
        self._default = default
        self._is_async = is_async_callable(predicate)
        self._checked = False
        self._cancelled = False

    def _create_container(self) -> bool:
        return self._default

    async def accept(self, element: Any) -> None:
        # Once settled the answer cannot change, and the predicate must not run
        # again: a sink pushing from end() can still deliver elements after
        # cancellation was requested.
        if self._cancelled:
            return
        r = self._predicate(element)
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
